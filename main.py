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
from typing import Optional

from src.core.config_loader import load_config
from src.models.database import Database
from src.services.notification import NotificationService
from src.services.bot_service import VFSBot
from src.core.logger import setup_structured_logging
from src.core.env_validator import EnvValidator
from src.core.config_validator import ConfigValidator
from src.core.monitoring import init_sentry


# Global shutdown event for coordinating graceful shutdown
_shutdown_event = None


def setup_signal_handlers():
    """
    Setup graceful shutdown handlers with timeout.
    
    Signals the shutdown event to allow running tasks to complete gracefully.
    If tasks don't complete within timeout, forces exit.
    """
    logger = logging.getLogger(__name__)

    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        global _shutdown_event
        if _shutdown_event and not _shutdown_event.is_set():
            _shutdown_event.set()
            logger.info("Shutdown event set, waiting for active operations to complete...")
        else:
            logger.warning("Shutdown already in progress or no active event, forcing exit...")
            sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)


async def run_bot_mode(config: dict, db: Optional[Database] = None) -> None:
    """
    Run bot in automated mode.

    Args:
        config: Configuration dictionary
        db: Optional shared database instance
    """
    global _shutdown_event
    logger = logging.getLogger(__name__)
    logger.info("Starting VFS-Bot in automated mode...")

    # Create shutdown event
    shutdown_event = asyncio.Event()
    _shutdown_event = shutdown_event

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
            from src.utils.selectors import SelectorManager

            selector_manager = SelectorManager()
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
        from src.constants import Defaults
        await asyncio.sleep(Defaults.GRACEFUL_SHUTDOWN_TIMEOUT)
    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)
        shutdown_event.set()
    finally:
        # Only close if we own the database instance
        if db_owned and db:
            await db.close()
        # Clear global shutdown event
        _shutdown_event = None


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
        if start_cleanup and "cleanup_service" in locals():
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
