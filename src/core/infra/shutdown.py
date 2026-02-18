"""
Shutdown and signal handling module.

Handles graceful shutdown, signal handling, and resource cleanup.
"""

import asyncio
import os
import signal
import threading
from typing import Any, Optional

from loguru import logger

from src.core.exceptions import ShutdownTimeoutError

# Graceful shutdown timeout in seconds (configurable via env)
try:
    SHUTDOWN_TIMEOUT = max(5, min(int(os.getenv("SHUTDOWN_TIMEOUT", "30")), 300))
except (ValueError, TypeError):
    SHUTDOWN_TIMEOUT = 30


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


def setup_signal_handlers():
    """
    Setup graceful shutdown handlers with timeout.

    Signals the shutdown event to allow running tasks to complete gracefully.
    If tasks don't complete within timeout, forces exit.
    """

    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        shutdown_event = get_shutdown_event()
        if shutdown_event and not shutdown_event.is_set():
            shutdown_event.set()
            logger.info("Shutdown event set, waiting for active operations to complete...")
        else:
            logger.warning("Second signal received, attempting fast cleanup before exit...")
            try:
                loop = asyncio.get_running_loop()
                # Running loop exists — schedule cleanup and let it complete
                # before forcing exit
                cleanup_task = loop.create_task(fast_emergency_cleanup())

                def _on_cleanup_done(task):
                    logger.warning("Emergency cleanup completed, forcing exit")
                    os._exit(0)

                cleanup_task.add_done_callback(_on_cleanup_done)
                # Stop the loop so it processes remaining tasks and exits
                loop.call_soon(loop.stop)
            except RuntimeError:
                # No running loop - run cleanup synchronously
                try:
                    asyncio.run(fast_emergency_cleanup())
                except Exception as e:
                    logger.error(f"Emergency cleanup failed: {e}")
                logger.warning("Forcing exit after emergency cleanup")
                os._exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)


async def fast_emergency_cleanup() -> None:
    """
    Fast emergency cleanup on second signal.

    Only attempts to close database connection to prevent corruption.
    Uses a very short timeout (5 seconds).
    """
    logger.warning("Executing fast emergency cleanup...")

    # Try to close DatabaseFactory instance (used by web mode)
    try:
        from src.models.db_factory import DatabaseFactory

        await asyncio.wait_for(DatabaseFactory.close_instance(), timeout=5)
        logger.info("DatabaseFactory instance closed")
    except asyncio.TimeoutError:
        logger.error("DatabaseFactory close timed out after 5s")
    except Exception as e:
        logger.error(f"Error closing DatabaseFactory: {e}")

    logger.info("Fast emergency cleanup complete")


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


async def force_cleanup_critical_resources(
    db: Optional["Database"] = None,  # type: ignore  # noqa: F821
) -> None:
    """
    Force cleanup of critical resources during shutdown timeout.

    This is a last-resort cleanup when graceful shutdown times out.
    Only cleans up the most critical resources to prevent data loss.

    Args:
        db: Database instance to close
    """
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
    db: Optional["Database"] = None,  # type: ignore  # noqa: F821
    notifier: Optional["NotificationService"] = None,  # type: ignore  # noqa: F821
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


async def safe_shutdown_cleanup(
    db: Optional["Database"] = None,  # type: ignore  # noqa: F821
    db_owned: bool = False,
    cleanup_service: Any = None,
    cleanup_task: Any = None,
    shutdown_event: Optional[asyncio.Event] = None,
) -> None:
    """
    Safely cleanup resources during shutdown with timeout protection.

    This function wraps all cleanup operations in try/except blocks with timeouts
    to prevent shutdown hangs or crashes.

    Args:
        db: Database instance to close
        db_owned: Whether we own the database instance (only close if True)
        cleanup_service: CleanupService instance to stop
        cleanup_task: Cleanup task to cancel
        shutdown_event: Shutdown event to clear
    """

    # Stop cleanup service
    if cleanup_service is not None:
        try:
            cleanup_service.stop()
            logger.info("Cleanup service stopped")
        except Exception as e:
            logger.error(f"Error stopping cleanup service: {e}")

    # Cancel cleanup task
    if cleanup_task:
        try:
            cleanup_task.cancel()
            await cleanup_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error cancelling cleanup task: {e}")

    # Cleanup OTP service
    try:
        from src.services.otp_manager.otp_webhook import get_otp_service

        otp_service = get_otp_service()
        await asyncio.wait_for(otp_service.stop_cleanup_scheduler(), timeout=5)
        logger.info("OTP service cleanup completed")
    except asyncio.TimeoutError:
        logger.warning("OTP service cleanup timed out after 5s")
    except Exception as e:
        logger.error(f"Error cleaning up OTP service: {e}")

    # Close database with timeout protection
    if db_owned and db:
        try:
            await asyncio.wait_for(db.close(), timeout=10)
            logger.info("Database closed successfully")
        except asyncio.TimeoutError:
            logger.error("Database close timed out after 10s")
        except Exception as e:
            logger.error(f"Error closing database: {e}")

    # Clear global shutdown event
    if shutdown_event is not None:
        try:
            set_shutdown_event(None)
        except Exception as e:
            logger.error(f"Error clearing shutdown event: {e}")
