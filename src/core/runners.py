"""
Application runner modes.

Handles different run modes: bot-only, web-only, and both.
"""

import asyncio
import os
from typing import Optional

from loguru import logger

from src.core.bot_controller import BotController
from src.core.exceptions import ShutdownTimeoutError
from src.models.database import Database
from src.services.bot import VFSBot
from src.services.notification import NotificationService

from .shutdown import (
    graceful_shutdown_with_timeout,
    safe_shutdown_cleanup,
    set_shutdown_event,
)


async def run_bot_mode(config: dict, db: Optional[Database] = None) -> None:
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
        logger.info("Database backup service started (pg_dump)")
    except Exception as e:
        logger.warning(f"Failed to start backup service (non-critical): {e}")

    # Initialize notifier to None so it's available in finally block if initialization fails
    notifier = None
    try:
        # Initialize notification service
        notifier = NotificationService(config.get("notifications", {}))

        # Initialize and start bot with shutdown event
        bot = VFSBot(config, db, notifier, shutdown_event=shutdown_event)

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

    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Bot stopped by user")
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
            try:
                loop = asyncio.get_running_loop()
                await graceful_shutdown_with_timeout(loop, db, notifier)
            except ShutdownTimeoutError as e:
                logger.error(f"Shutdown timeout: {e}")
                # Continue with cleanup anyway
            except Exception as e:
                logger.error(f"Error during graceful shutdown: {e}")

        # Safe cleanup of all resources
        await safe_shutdown_cleanup(
            db=db,
            db_owned=db_owned,
            shutdown_event=shutdown_event,
        )


async def run_web_mode(
    config: dict, start_cleanup: bool = True, db: Optional[Database] = None, skip_shutdown: bool = False
) -> None:
    """
    Run bot with web dashboard.

    Args:
        config: Configuration dictionary
        start_cleanup: Whether to start the cleanup service (default True)
        db: Optional shared database instance
        skip_shutdown: Whether to skip graceful shutdown and full cleanup,
            delegating it to the caller (used by run_both_mode). Default False.
    """
    logger.info("Starting VFS-Bot with web dashboard...")

    import uvicorn

    from src.services.cleanup_service import CleanupService
    from web.app import app

    # Initialize database if not provided
    db_owned = db is None
    if db_owned:
        from src.models.db_factory import DatabaseFactory
        db = await DatabaseFactory.ensure_connected()

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

        # Run uvicorn server with configurable host and port
        host = os.getenv("UVICORN_HOST", "127.0.0.1")
        port = int(os.getenv("UVICORN_PORT", "8000"))
        config_uvicorn = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config_uvicorn)
        await server.serve()
    finally:
        if not skip_shutdown:
            # Full shutdown path (standalone web mode)
            try:
                loop = asyncio.get_running_loop()
                await graceful_shutdown_with_timeout(loop, db, None)
            except ShutdownTimeoutError as e:
                logger.error(f"Shutdown timeout: {e}")
            except Exception as e:
                logger.error(f"Error during graceful shutdown: {e}")

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


async def run_both_mode(config: dict) -> None:
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

    # Get and configure BotController singleton
    controller = await BotController.get_instance()
    await controller.configure(config, db, notifier)

    try:
        # Start the bot via controller
        logger.info("Starting bot via BotController...")
        start_result = await controller.start_bot()
        if start_result["status"] != "success":
            logger.error(f"Failed to start bot: {start_result['message']}")
            raise RuntimeError(
                f"Critical: Unable to start bot in both mode - {start_result['message']}"
            )

        # Run web mode (with cleanup service enabled, skip its shutdown)
        web_task = asyncio.create_task(run_web_mode(config, start_cleanup=True, db=db, skip_shutdown=True))

        # Wait for web task to complete
        await web_task

    except Exception as e:
        logger.error(f"Error in combined mode: {e}", exc_info=True)
        raise
    finally:
        # Stop the bot via controller
        logger.info("Stopping bot via BotController...")
        try:
            await controller.stop_bot()
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")

        # Graceful shutdown with timeout protection
        try:
            loop = asyncio.get_running_loop()
            await graceful_shutdown_with_timeout(loop, db, notifier)
        except ShutdownTimeoutError as e:
            logger.error(f"Shutdown timeout: {e}")
            # Continue with cleanup anyway
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")

        # Safe cleanup - close shared database
        await safe_shutdown_cleanup(db=db, db_owned=True)
        logger.info("Combined mode shutdown complete")
