"""
Bot controller singleton for managing VFSBot lifecycle.

This controller provides a central point for starting, stopping, and managing
the VFSBot instance from web dashboard endpoints.
"""

import asyncio
import threading
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from loguru import logger

from src.constants import Delays

if TYPE_CHECKING:
    from src.models.database import Database
    from src.services.bot.vfs_bot import VFSBot
    from src.services.notification.notification import NotificationService


class BotController:
    """
    Singleton controller for managing VFSBot lifecycle.

    Provides thread-safe access to bot control operations from web endpoints.
    """

    _instance: Optional["BotController"] = None
    _init_lock = threading.Lock()  # Thread-safe guard for singleton creation

    def __init__(self):
        """Initialize bot controller (use get_instance() instead)."""
        self._config: Optional[Dict[str, Any]] = None
        self._db: Optional["Database"] = None
        self._notifier: Optional["NotificationService"] = None
        self._bot: Optional["VFSBot"] = None
        self._bot_task: Optional[asyncio.Task] = None
        self._shutdown_event: Optional[asyncio.Event] = None
        self._starting = False
        self._configured = False
        self._async_lock = asyncio.Lock()  # Instance-level async lock
        self._bot_factory: Optional[Callable] = None

    @classmethod
    async def get_instance(cls) -> "BotController":
        """
        Get singleton instance of BotController.

        Uses threading.Lock for thread-safe instance creation (synchronous operation).
        Async operations within the instance use instance-level asyncio.Lock to
        synchronize async operations.

        Returns:
            BotController instance
        """
        if cls._instance is None:
            # Synchronous lock is correct here - instance creation is synchronous
            # and we need thread-safety across multiple threads
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    async def reset_instance(cls) -> None:
        """
        Reset singleton instance (for testing).

        Stops any running bot and clears the singleton.
        Uses threading.Lock to ensure thread-safe reset across multiple threads.
        The lock is only held during instance nullification; stop_bot() is called
        before acquiring the lock to avoid blocking.
        """
        # Get instance reference before acquiring lock
        instance = cls._instance

        # Stop bot outside the lock to avoid blocking
        if instance is not None:
            try:
                await instance.stop_bot()
            except Exception as e:
                logger.error(f"Error stopping bot during reset: {e}")

        # Only hold lock during instance nullification (fast operation)
        with cls._init_lock:
            cls._instance = None

    async def configure(
        self,
        config: Dict[str, Any],
        db: "Database",
        notifier: "NotificationService",
        bot_factory: Optional[Callable] = None,
    ) -> None:
        """
        Configure the bot controller with dependencies.

        Args:
            config: Bot configuration dictionary
            db: Database instance
            notifier: Notification service instance
            bot_factory: Optional factory function to create VFSBot instances (avoids circular imports)
        """
        async with self._async_lock:
            self._config = config
            self._db = db
            self._notifier = notifier
            self._bot_factory = bot_factory
            self._configured = True
            logger.info("BotController configured with dependencies")

    async def start_bot(self) -> Dict[str, str]:
        """
        Start the bot.

        Returns:
            Status dictionary with result
        """
        async with self._async_lock:
            # Check if configured
            if not self._configured:
                logger.error("BotController not configured")
                return {
                    "status": "error",
                    "message": "Bot controller not configured. Please restart the application.",
                }

            # Check if already starting
            if self._starting:
                logger.warning("Bot is already starting")
                return {"status": "error", "message": "Bot is already starting"}

            # Check if already running
            if self.is_running:
                logger.warning("Bot is already running")
                return {"status": "error", "message": "Bot is already running"}

            try:
                self._starting = True
                logger.info("Starting bot via BotController...")

                # Create shutdown event
                self._shutdown_event = asyncio.Event()

                # Create VFSBot instance using factory or fallback to lazy import
                if self._bot_factory:
                    self._bot = self._bot_factory(
                        self._config, self._db, self._notifier, shutdown_event=self._shutdown_event
                    )
                else:
                    # Fallback to lazy import for backwards compatibility
                    from src.services.bot.vfs_bot import VFSBot

                    assert self._config is not None
                    assert self._db is not None
                    assert self._notifier is not None
                    self._bot = VFSBot(
                        self._config,  # type: ignore[arg-type]
                        self._db, self._notifier, shutdown_event=self._shutdown_event
                    )

                # Initialize selector health monitoring if enabled
                assert self._bot is not None
                if self._config and self._config.get("selector_health_check", {}).get("enabled", True):
                    try:
                        from src.selector import CountryAwareSelectorManager, SelectorHealthCheck

                        selector_manager = CountryAwareSelectorManager()
                        self._bot.health_checker = SelectorHealthCheck(
                            selector_manager,
                            self._notifier,
                            check_interval=self._config.get("selector_health_check", {}).get(
                                "interval", 3600
                            ),
                        )
                        logger.info("Selector health monitoring initialized")
                    except Exception as e:
                        logger.warning(f"Failed to initialize selector health monitoring: {e}")
                        self._bot.health_checker = None
                else:
                    self._bot.health_checker = None

                # Start bot as background task
                self._bot_task = asyncio.create_task(
                    self._run_bot(), name="vfs_bot_controller_task"
                )

                logger.info("Bot started successfully via BotController")
                return {"status": "success", "message": "Bot started"}

            except Exception as e:
                logger.error(f"Failed to start bot: {e}", exc_info=True)
                self._bot = None
                self._bot_task = None
                self._shutdown_event = None
                return {"status": "error", "message": f"Failed to start bot: {str(e)}"}
            finally:
                self._starting = False

    async def _run_bot(self) -> None:
        """Internal method to run the bot."""
        # Capture bot reference early to avoid race with stop_bot()
        bot = self._bot
        if bot is None:
            logger.error("Bot not initialized")
            return
        try:
            await bot.start()
        except asyncio.CancelledError:
            logger.info("Bot task was cancelled")
        except Exception as e:
            logger.error(f"Bot error: {e}", exc_info=True)
        finally:
            # Cleanup without lock to prevent deadlock
            # Reference cleanup is handled by stop_bot() under lock
            # Only cleanup bot resources here, don't modify controller state
            if bot:
                try:
                    await bot.cleanup()
                except Exception as e:
                    logger.error(f"Error during bot cleanup: {e}")

    async def stop_bot(self) -> Dict[str, str]:
        """
        Stop the bot.

        Returns:
            Status dictionary with result
        """
        bot_task = None
        async with self._async_lock:
            if not self.is_running:
                logger.warning("Bot is not running")
                return {"status": "error", "message": "Bot is not running"}

            try:
                logger.info("Stopping bot via BotController...")

                # Set shutdown event
                if self._shutdown_event:
                    self._shutdown_event.set()

                # Stop the bot
                if self._bot:
                    await self._bot.stop()

                # Get local reference to the task
                bot_task = self._bot_task

                # Clean up controller state
                self._bot = None
                self._bot_task = None
                self._shutdown_event = None

            except Exception as e:
                logger.error(f"Failed to stop bot: {e}", exc_info=True)
                return {"status": "error", "message": f"Failed to stop bot: {str(e)}"}

        # Await task completion outside the lock to prevent deadlock
        if bot_task and not bot_task.done():
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass

        logger.info("Bot stopped successfully via BotController")
        return {"status": "success", "message": "Bot stopped"}

    async def restart_bot(self) -> Dict[str, str]:
        """
        Restart the bot.

        Returns:
            Status dictionary with result
        """
        logger.info("Restarting bot via BotController...")

        # Stop the bot
        stop_result = await self.stop_bot()
        if stop_result["status"] == "error" and "not running" not in stop_result["message"]:
            return stop_result

        # Small delay
        await asyncio.sleep(Delays.RESTART_DELAY)

        # Start the bot
        start_result = await self.start_bot()
        return start_result

    async def trigger_check_now(self) -> Dict[str, str]:
        """
        Trigger an immediate slot check.

        This method interrupts the bot's sleep cycle and triggers an immediate
        check by setting the trigger event that the bot's main loop monitors.

        Returns:
            Status dictionary with result
        """
        async with self._async_lock:
            if not self.is_running:
                logger.warning("Cannot trigger check: bot is not running")
                return {"status": "error", "message": "Bot is not running"}

            try:
                if self._bot is not None:
                    self._bot.trigger_immediate_check()
                logger.info("Manual check triggered via BotController - bot will check immediately")
                return {"status": "success", "message": "Manual check triggered"}
            except AttributeError:
                logger.error("Bot reference lost during trigger attempt")
                return {"status": "error", "message": "Bot is no longer available"}

    async def update_cooldown(self, cooldown_seconds: int) -> Dict[str, Any]:
        """
        Update the account pool cooldown duration at runtime.

        Args:
            cooldown_seconds: New cooldown duration in seconds

        Returns:
            Status dictionary with result
        """
        async with self._async_lock:
            if self._bot and self._bot.account_pool:
                self._bot.account_pool.cooldown_seconds = cooldown_seconds
                logger.info(f"Cooldown updated to {cooldown_seconds}s via dashboard")
                return {"status": "success", "cooldown_seconds": cooldown_seconds}
            return {"status": "error", "message": "Bot not running or account pool not initialized"}

    def get_cooldown_settings(self) -> Dict[str, int]:
        """
        Get current cooldown settings.

        Returns:
            Dictionary with cooldown settings
        """
        from src.constants import AccountPoolConfig

        # If bot is running, get from account pool, otherwise use default
        if self._bot and self._bot.account_pool:
            cooldown_seconds = self._bot.account_pool.cooldown_seconds
        else:
            cooldown_seconds = AccountPoolConfig.COOLDOWN_SECONDS

        return {
            "cooldown_seconds": cooldown_seconds,
            "cooldown_minutes": round(cooldown_seconds / 60),  # Round to nearest minute
            "quarantine_minutes": AccountPoolConfig.QUARANTINE_SECONDS // 60,
            "max_failures": AccountPoolConfig.MAX_FAILURES,
        }

    def get_status(self) -> Dict[str, Any]:
        """
        Get current bot status.

        Returns:
            Status dictionary with bot state
        """
        if not self._configured:
            return {
                "status": "not_configured",
                "running": False,
                "message": "Bot controller not configured",
            }

        if self._starting:
            return {"status": "starting", "running": False, "message": "Bot is starting"}

        if self.is_running:
            return {"status": "running", "running": True, "message": "Bot is running"}

        return {"status": "stopped", "running": False, "message": "Bot is stopped"}

    @property
    def is_running(self) -> bool:
        """
        Check if bot is currently running.

        Returns:
            True if bot is running, False otherwise
        """
        return (
            self._bot is not None
            and self._bot.running
            and self._bot_task is not None
            and not self._bot_task.done()
        )
