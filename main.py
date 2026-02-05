#!/usr/bin/env python3
"""
VFS-Bot - Automated VFS appointment booking bot.

Main entry point for the application.
"""

import asyncio
import logging
import sys
import os
import argparse
import signal
import threading
from typing import Optional

from src.core.config_loader import load_config
from src.models.database import Database
from src.services.notification import NotificationService

from src.services.bot import VFSBot
from src.core.logger import setup_structured_logging
from src.core.env_validator import EnvValidator
from src.core.config_validator import ConfigValidator
from src.core.monitoring import init_sentry
from src.core.exceptions import ConfigurationError, ShutdownTimeoutError


# Graceful shutdown timeout in seconds (configurable via env)
SHUTDOWN_TIMEOUT = int(os.getenv("SHUTDOWN_TIMEOUT", "30"))


# Global shutdown event for coordinating graceful shutdown - thread-safe singleton
_shutdown_event: Optional[asyncio.Event] = None
_shutdown_lock = threading.Lock()


def get_shutdown_event() -> Optional[asyncio.Event]:
    """Get shutdown event - thread-safe singleton pattern."""
    with _shutdown_lock:
        return _shutdown_event


def set_shutdown_event(event: Optional[asyncio.Event]) -> None:
    """Set shutdown event - thread-safe singleton pattern."""
    global _shutdown_event
    with _shutdown_lock:
        _shutdown_event = event


def validate_environment():
    """Validate all required environment variables at startup."""
    logger = logging.getLogger(__name__)
    env = os.getenv("ENV", "production").lower()

    # Always required
    required_vars = ["ENCRYPTION_KEY"]

    # Required in production
    production_required = [
        "API_SECRET_KEY",
        "API_KEY_SALT",
        "VFS_ENCRYPTION_KEY",
    ]

    missing = [var for var in required_vars if not os.getenv(var)]

    if env == "production":
        missing.extend([var for var in production_required if not os.getenv(var)])

    if missing:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Please check your .env file or environment configuration."
        )

    # Validate minimum lengths
    api_secret = os.getenv("API_SECRET_KEY", "")
    if api_secret and len(api_secret) < 64:
        raise ConfigurationError(
            f"API_SECRET_KEY must be at least 64 characters (current: {len(api_secret)})"
        )

    api_key_salt = os.getenv("API_KEY_SALT", "")
    if api_key_salt and len(api_key_salt) < 32:
        raise ConfigurationError(
            f"API_KEY_SALT must be at least 32 characters (current: {len(api_key_salt)})"
        )

    logger.info("✅ Environment validation passed")


def setup_signal_handlers():
    """
    Setup graceful shutdown handlers with timeout.

    Signals the shutdown event to allow running tasks to complete gracefully.
    If tasks don't complete within timeout, forces exit.
    """
    logger = logging.getLogger(__name__)

    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        shutdown_event = get_shutdown_event()
        if shutdown_event and not shutdown_event.is_set():
            shutdown_event.set()
            logger.info("Shutdown event set, waiting for active operations to complete...")
        else:
            logger.warning("Shutdown already in progress or no active event, forcing exit...")
            sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)


async def graceful_shutdown(
    loop: asyncio.AbstractEventLoop, signal_name: Optional[str] = None, timeout: float = 30.0
) -> None:
    """
    Cancel all running tasks during shutdown.

    Args:
        loop: Event loop
        signal_name: Name of signal that triggered shutdown (optional)
        timeout: Maximum time to wait for tasks to complete (default: 30 seconds)
    """
    logger = logging.getLogger(__name__)
    logger.info(
        f"Initiating graceful shutdown{f' (signal: {signal_name})' if signal_name else ''}..."
    )

    # Get all tasks except current
    tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task()]

    if tasks:
        logger.info(f"Cancelling {len(tasks)} outstanding tasks...")

        for task in tasks:
            task.cancel()

        # Wait for all tasks to be cancelled with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=timeout
            )

            # Log any exceptions
            for task, result in zip(tasks, results):
                if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                    task_name = task.get_name() if hasattr(task, "get_name") else "unknown"
                    logger.error(f"Task {task_name} raised exception during shutdown: {result}")
        except asyncio.TimeoutError:
            logger.warning(
                f"Graceful shutdown timed out after {timeout}s, some tasks may not have completed"
            )

    logger.info("Graceful shutdown complete")


async def force_cleanup_critical_resources(db: Optional[Database] = None) -> None:
    """
    Force cleanup of critical resources during shutdown timeout.

    This is a last-resort cleanup when graceful shutdown times out.
    Only cleans up the most critical resources to prevent data loss.

    Args:
        db: Database instance to close
    """
    logger = logging.getLogger(__name__)
    logger.warning("Forcing cleanup of critical resources...")

    try:
        # Close database connection to prevent corruption
        if db is not None:
            await db.close()
            logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Error during forced database cleanup: {e}")

    logger.info("Critical resource cleanup complete")


async def graceful_shutdown_with_timeout(
    loop: asyncio.AbstractEventLoop,
    db: Optional[Database] = None,
    notifier: Optional[NotificationService] = None,
    signal_name: Optional[str] = None,
) -> None:
    """
    Graceful shutdown with timeout protection.

    If graceful shutdown doesn't complete within SHUTDOWN_TIMEOUT seconds,
    forces cleanup of critical resources and exits.

    Args:
        loop: Event loop
        db: Database instance
        notifier: Notification service instance
        signal_name: Name of signal that triggered shutdown (optional)

    Raises:
        ShutdownTimeoutError: If graceful shutdown times out (raised but caught)
    """
    logger = logging.getLogger(__name__)

    try:
        await asyncio.wait_for(
            graceful_shutdown(loop, signal_name, timeout=SHUTDOWN_TIMEOUT), timeout=SHUTDOWN_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(
            f"Graceful shutdown timed out after {SHUTDOWN_TIMEOUT}s, "
            "forcing cleanup of critical resources"
        )
        await force_cleanup_critical_resources(db)
        # Raise error to signal abnormal shutdown
        raise ShutdownTimeoutError(
            f"Graceful shutdown timed out after {SHUTDOWN_TIMEOUT}s", timeout=SHUTDOWN_TIMEOUT
        )


async def run_bot_mode(config: dict, db: Optional[Database] = None) -> None:
    """
    Run bot in automated mode.

    Args:
        config: Configuration dictionary
        db: Optional shared database instance
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting VFS-Bot in automated mode...")

    # Create shutdown event
    shutdown_event = asyncio.Event()
    set_shutdown_event(shutdown_event)

    # Initialize database if not provided
    db_owned = db is None
    if db_owned:
        db = Database()
        await db.connect()

    try:
        # Initialize notification service
        notifier = NotificationService(config["notifications"])

        # Initialize and start bot with shutdown event
        bot = VFSBot(config, db, notifier, shutdown_event)

        # Initialize selector health monitoring (if enabled)
        # Note: The health checker will be started within the bot's browser context
        # when the browser is available. See VFSBot.start() for implementation.
        if config.get("selector_health_check", {}).get("enabled", True):
            from src.utils.selector_watcher import SelectorHealthCheck
            from src.utils.selectors import CountryAwareSelectorManager

            selector_manager = CountryAwareSelectorManager()
            bot.health_checker = SelectorHealthCheck(
                selector_manager,
                notifier,
                check_interval=config.get("selector_health_check", {}).get("interval", 3600),
            )
            logger.info("Selector health monitoring initialized")
        else:
            bot.health_checker = None

        await bot.start()

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        shutdown_event.set()
        # Wait for graceful shutdown with timeout
        from src.constants import Timeouts

        await asyncio.sleep(Timeouts.GRACEFUL_SHUTDOWN_SECONDS)

        # Cleanup OTP service
        try:
            from src.services.otp_webhook import get_otp_service

            otp_service = get_otp_service()
            await otp_service.stop_cleanup_scheduler()
            logger.info("OTP service cleanup completed")
        except Exception as e:
            logger.error(f"Error cleaning up OTP service: {e}")
    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)
        shutdown_event.set()
    finally:
        # Only close if we own the database instance
        if db_owned and db:
            await db.close()
        # Clear global shutdown event
        set_shutdown_event(None)


async def run_web_mode(
    config: dict, start_cleanup: bool = True, db: Optional[Database] = None
) -> None:
    """
    Run bot with web dashboard.

    Args:
        config: Configuration dictionary
        start_cleanup: Whether to start the cleanup service (default True)
        db: Optional shared database instance
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting VFS-Bot with web dashboard...")

    import uvicorn
    from web.app import app
    from src.services.cleanup_service import CleanupService

    # Initialize database if not provided
    db_owned = db is None
    if db_owned:
        db = Database()
        await db.connect()

    cleanup_service = None  # Initialize to None
    cleanup_task = None
    try:
        # Start cleanup service in background (only if requested)
        if start_cleanup:
            cleanup_service = CleanupService(db, cleanup_days=30)
            cleanup_task = asyncio.create_task(
                cleanup_service.run_periodic_cleanup(interval_hours=24)
            )
            logger.info("Cleanup service started (runs every 24 hours)")

        # Run uvicorn server
        config_uvicorn = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
        server = uvicorn.Server(config_uvicorn)
        await server.serve()
    finally:
        # Stop cleanup service
        if cleanup_service is not None:
            cleanup_service.stop()
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
        # Only close if we own the database instance
        if db_owned and db:
            await db.close()
        logger.info("Web mode shutdown complete")


async def run_both_mode(config: dict) -> None:
    """
    Run both bot and web dashboard concurrently.

    Args:
        config: Configuration dictionary
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting VFS-Bot in combined mode (bot + web)...")

    # Initialize shared database instance for both modes
    db = Database()
    await db.connect()

    try:
        # Create tasks for both modes with shared database
        # (disable cleanup in web task to avoid duplication)
        web_task = asyncio.create_task(run_web_mode(config, start_cleanup=True, db=db))
        bot_task = asyncio.create_task(run_bot_mode(config, db=db))

        # Run both concurrently and handle exceptions
        results = await asyncio.gather(web_task, bot_task, return_exceptions=True)

        # Check for exceptions in results
        for i, result in enumerate(results):
            task_name = "web" if i == 0 else "bot"
            if isinstance(result, Exception):
                logger.error(f"Task '{task_name}' failed with exception: {result}", exc_info=result)
    except Exception as e:
        logger.error(f"Error in combined mode: {e}", exc_info=True)
        raise
    finally:
        # Close shared database
        await db.close()
        logger.info("Combined mode shutdown complete")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="VFS-Bot - Automated appointment booking")
    parser.add_argument(
        "--mode",
        choices=["bot", "web", "both"],
        default="both",
        help="Run mode: bot (automated), web (dashboard only), both (default)",
    )
    parser.add_argument("--config", default="config/config.yaml", help="Path to configuration file")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Setup structured logging
    json_logging = os.getenv("JSON_LOGGING", "true").lower() == "true"
    setup_structured_logging(args.log_level, json_format=json_logging)
    logger = logging.getLogger(__name__)

    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()

    try:
        # Initialize Sentry monitoring
        init_sentry()

        # Validate environment variables
        logger.info("Validating environment variables...")
        validate_environment()
        EnvValidator.validate(strict=True)

        # Load configuration
        logger.info("Loading configuration...")
        config = load_config(args.config)
        logger.info("Configuration loaded successfully")

        # Validate config
        if not ConfigValidator.validate(config):
            logger.error("Invalid configuration, exiting...")
            sys.exit(1)

        # Run in selected mode
        if args.mode == "bot":
            asyncio.run(run_bot_mode(config))
        elif args.mode == "web":
            asyncio.run(run_web_mode(config))
        else:  # both
            asyncio.run(run_both_mode(config))

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        logger.info("Please copy config/config.example.yaml to config/config.yaml and configure it")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
