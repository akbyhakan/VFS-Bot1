"""
Application runner modes.

Handles different run modes: bot-only, web-only, and both.
"""

import asyncio
import os
from typing import Any, Dict, Optional

from loguru import logger
from typing_extensions import TypedDict

from src.core.bot_controller import BotController
from src.core.exceptions import ShutdownTimeoutError
from src.models.database import Database
from src.services.bot import VFSBot
from src.services.notification.notification import NotificationService

from .shutdown import (
    graceful_shutdown_with_timeout,
    safe_shutdown_cleanup,
    set_shutdown_event,
)


class BotConfigDict(TypedDict, total=False):
    """Type hints for the bot configuration dictionary."""

    vfs: Dict[str, Any]
    bot: Dict[str, Any]
    notifications: Dict[str, Any]
    captcha: Dict[str, Any]
    anti_detection: Dict[str, Any]
    appointments: Dict[str, Any]
    selector_health_check: Dict[str, Any]
    payment: Dict[str, Any]
    mode: str


def parse_safe_port(env_var: str = "UVICORN_PORT", default: int = 8000) -> int:
    """Parse port from environment variable with validation.

    Args:
        env_var: Environment variable name to read
        default: Default port if env var is missing or invalid

    Returns:
        Valid port number (1-65535)
    """
    raw = os.getenv(env_var)
    if raw is None:
        return default
    try:
        port = int(raw)
        if not (1 <= port <= 65535):
            raise ValueError(f"Port must be 1-65535, got: {port}")
        return port
    except ValueError as e:
        logger.warning(f"Invalid {env_var}: {e}. Using default {default}")
        return default


async def _graceful_cleanup(
    db: Optional[Database], notifier: Optional[NotificationService] = None
) -> None:
    """Execute graceful shutdown with timeout protection.

    Args:
        db: Database instance to pass to shutdown handler
        notifier: Optional notification service to pass to shutdown handler
    """
    try:
        loop = asyncio.get_running_loop()
        await graceful_shutdown_with_timeout(loop, db, notifier)
    except ShutdownTimeoutError as e:
        logger.error(f"Shutdown timeout: {e}")
    except Exception as e:
        logger.error(f"Error during graceful shutdown: {e}")


async def run_bot_mode(config: BotConfigDict, db: Optional[Database] = None) -> None:
    """
    Run bot in automated mode.

    Args:
        config: Configuration dictionary
        db: Optional shared database instance
    """
    logger.info("Starting VFS-Bot in automated mode...")

    # Create shutdown event
    shutdown_event = asyncio.Event()
    set_shutdown_event(shutdown_event)

    # Initialize database if not provided
    db_owned = db is None
    if db_owned:
        from src.models.db_factory import DatabaseFactory

        db = await DatabaseFactory.ensure_connected()

    # Database backup service (PostgreSQL)
    backup_service = None
    try:
        from src.utils.db_backup import get_backup_service

        backup_service = get_backup_service()
        await backup_service.start_scheduled_backups()
        logger.info("Database backup service started (pg_dump, encrypted)")
    except Exception as e:
        logger.warning(f"Failed to start backup service (non-critical): {e}")

    # Initialize notifier to None so it's available in finally block if initialization fails
    notifier = None
    try:
        # Initialize notification service
        notifier = NotificationService(config.get("notifications", {}))

        # Initialize and start bot with shutdown event
        assert db is not None, "Database must be initialized before bot"
        bot = VFSBot(config, db, notifier, shutdown_event=shutdown_event)

        # Initialize selector health monitoring (if enabled)
        # Note: The health checker will be started within the bot's browser context
        # when the browser is available. See VFSBot.start() for implementation.
        if config.get("selector_health_check", {}).get("enabled", True):
            from src.selector import CountryAwareSelectorManager, SelectorHealthCheck

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

    except asyncio.CancelledError:
        logger.info("Bot stopped by user (cancelled)")
        shutdown_event.set()
    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)
        shutdown_event.set()
    finally:
        # Stop backup service
        if backup_service:
            try:
                await backup_service.stop_scheduled_backups()
                logger.info("Database backup service stopped")
            except Exception as e:
                logger.error(f"Error stopping backup service: {e}")

        # Graceful shutdown with timeout protection
        if shutdown_event and shutdown_event.is_set():
            await _graceful_cleanup(db, notifier)

        # Safe cleanup of all resources
        await safe_shutdown_cleanup(
            db=db,
            db_owned=db_owned,
            shutdown_event=shutdown_event,
        )


async def run_web_mode(
    config: BotConfigDict,
    start_cleanup: bool = True,
    start_backup: bool = True,
    db: Optional[Database] = None,
    skip_shutdown: bool = False,
) -> None:
    """
    Run bot with web dashboard.

    Args:
        config: Configuration dictionary
        start_cleanup: Whether to start the cleanup service (default True)
        start_backup: Whether to start the backup service (default True)
        db: Optional shared database instance
        skip_shutdown: Whether to skip graceful shutdown and full cleanup,
            delegating it to the caller (used by run_both_mode). Default False.
    """
    logger.info("Starting VFS-Bot with web dashboard...")

    import uvicorn

    from src.services.scheduling.cleanup_service import CleanupService
    from web.app import create_app

    # Initialize database if not provided
    db_owned = db is None
    if db_owned:
        from src.models.db_factory import DatabaseFactory

        db = await DatabaseFactory.ensure_connected()

    # Database backup service (PostgreSQL)
    backup_service = None
    if start_backup:
        try:
            from src.utils.db_backup import get_backup_service

            backup_service = get_backup_service()
            await backup_service.start_scheduled_backups()
            logger.info("Database backup service started (pg_dump, encrypted)")
        except Exception as e:
            logger.warning(f"Failed to start backup service (non-critical): {e}")

    cleanup_service = None  # Initialize to None
    cleanup_task = None
    assert db is not None, "Database must be initialized"
    try:
        # Start cleanup service in background (only if requested)
        if start_cleanup:
            cleanup_service = CleanupService(db, cleanup_days=30)
            cleanup_task = asyncio.create_task(
                cleanup_service.run_periodic_cleanup(interval_hours=24)
            )
            logger.info("Cleanup service started (runs every 24 hours)")

        # Create the app instance
        app = create_app()

        # Run uvicorn server with configurable host and port
        host = os.getenv("UVICORN_HOST", "127.0.0.1")
        port = parse_safe_port()
        config_uvicorn = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config_uvicorn)
        await server.serve()
    finally:
        # Stop backup service
        if backup_service:
            try:
                await backup_service.stop_scheduled_backups()
                logger.info("Database backup service stopped")
            except Exception as e:
                logger.error(f"Error stopping backup service: {e}")

        if not skip_shutdown:
            # Full shutdown path (standalone web mode)
            await _graceful_cleanup(db, None)

            # Safe cleanup of all resources
            await safe_shutdown_cleanup(
                db=db,
                db_owned=db_owned,
                cleanup_service=cleanup_service,
                cleanup_task=cleanup_task,
            )
            logger.info("Web mode shutdown complete")
        else:
            # Delegated shutdown path (called from run_both_mode)
            # Only stop local resources; full cleanup is handled by caller
            if cleanup_task:
                try:
                    cleanup_task.cancel()
                    await cleanup_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error cancelling cleanup task: {e}")
            if cleanup_service is not None:
                try:
                    cleanup_service.stop()
                    logger.info("Cleanup service stopped")
                except Exception as e:
                    logger.error(f"Error stopping cleanup service: {e}")
            logger.info("Web mode exited (shutdown delegated to caller)")


async def run_both_mode(config: BotConfigDict) -> None:
    """
    Run both bot and web dashboard concurrently.

    Args:
        config: Configuration dictionary
    """
    logger.info("Starting VFS-Bot in combined mode (bot + web)...")

    # Initialize shared database instance for both modes
    from src.models.db_factory import DatabaseFactory

    db = await DatabaseFactory.ensure_connected()

    # Initialize notification service
    notifier = NotificationService(config.get("notifications", {}))

    # Database backup service (PostgreSQL) - shared across both modes
    backup_service = None
    try:
        from src.utils.db_backup import get_backup_service

        backup_service = get_backup_service()
        await backup_service.start_scheduled_backups()
        logger.info("Database backup service started (pg_dump, encrypted)")
    except Exception as e:
        logger.warning(f"Failed to start backup service (non-critical): {e}")

    # Get and configure BotController singleton
    controller = await BotController.get_instance()
    await controller.configure(dict(config), db, notifier, bot_factory=VFSBot)

    try:
        # Start the bot via controller
        logger.info("Starting bot via BotController...")
        start_result = await controller.start_bot()
        if start_result.get("status") != "success":
            logger.error(
                f"Bot failed to start: {start_result.get('message', 'unknown error')}. "
                f"Web dashboard will start in degraded mode."
            )
        else:
            logger.info("Bot started successfully via BotController")

        # Run web mode (with cleanup service enabled, skip its shutdown)
        # Web starts regardless of bot status for diagnostics
        web_task = asyncio.create_task(
            run_web_mode(config, start_cleanup=True, start_backup=False, db=db, skip_shutdown=True)
        )

        # Wait for web task to complete
        await web_task

    except Exception as e:
        logger.error(f"Error in combined mode: {e}", exc_info=True)
        raise
    finally:
        # Stop backup service
        if backup_service:
            try:
                await backup_service.stop_scheduled_backups()
                logger.info("Database backup service stopped")
            except Exception as e:
                logger.error(f"Error stopping backup service: {e}")

        # Stop the bot via controller
        logger.info("Stopping bot via BotController...")
        try:
            await controller.stop_bot()
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")

        # Graceful shutdown with timeout protection
        await _graceful_cleanup(db, notifier)

        # Safe cleanup - close shared database
        await safe_shutdown_cleanup(db=db, db_owned=True)
        logger.info("Combined mode shutdown complete")
