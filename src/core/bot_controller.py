"""
Bot controller singleton for managing VFSBot lifecycle.

This controller provides a central point for starting, stopping, and managing
the VFSBot instance from web dashboard endpoints.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from src.models.database import Database
    from src.services.bot.vfs_bot import VFSBot
    from src.services.notification import NotificationService

logger = logging.getLogger(__name__)


class BotController:
    """
    Singleton controller for managing VFSBot lifecycle.
    
    Provides thread-safe access to bot control operations from web endpoints.
    """

    _instance: Optional["BotController"] = None
    _lock = asyncio.Lock()

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

    @classmethod
    async def get_instance(cls) -> "BotController":
        """
        Get singleton instance of BotController.
        
        Returns:
            BotController instance
        """
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    async def reset_instance(cls) -> None:
        """
        Reset singleton instance (for testing).
        
        Stops any running bot and clears the singleton.
        """
        async with cls._lock:
            if cls._instance is not None:
                try:
                    await cls._instance.stop_bot()
                except Exception as e:
                    logger.error(f"Error stopping bot during reset: {e}")
                cls._instance = None

    async def configure(
        self, config: Dict[str, Any], db: "Database", notifier: "NotificationService"
    ) -> None:
        """
        Configure the bot controller with dependencies.
        
        Args:
            config: Bot configuration dictionary
            db: Database instance
            notifier: Notification service instance
        """
        async with self._lock:
            self._config = config
            self._db = db
            self._notifier = notifier
            self._configured = True
            logger.info("BotController configured with dependencies")

    async def start_bot(self) -> Dict[str, str]:
        """
        Start the bot.
        
        Returns:
            Status dictionary with result
        """
        async with self._lock:
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

                # Import here to avoid circular dependency
                from src.services.bot.vfs_bot import VFSBot

                # Create shutdown event
                self._shutdown_event = asyncio.Event()

                # Create VFSBot instance
                self._bot = VFSBot(self._config, self._db, self._notifier, self._shutdown_event)

                # Initialize selector health monitoring if enabled
                if self._config.get("selector_health_check", {}).get("enabled", True):
                    try:
                        from src.utils.selector_watcher import SelectorHealthCheck
                        from src.utils.selectors import CountryAwareSelectorManager

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
        try:
            await self._bot.start()
        except Exception as e:
            logger.error(f"Bot error: {e}", exc_info=True)
        finally:
            # Clean up
            if self._bot:
                try:
                    await self._bot.cleanup()
                except Exception as e:
                    logger.error(f"Error during bot cleanup: {e}")
            self._bot = None
            self._bot_task = None

    async def stop_bot(self) -> Dict[str, str]:
        """
        Stop the bot.
        
        Returns:
            Status dictionary with result
        """
        async with self._lock:
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

                # Cancel the task
                if self._bot_task and not self._bot_task.done():
                    self._bot_task.cancel()
                    try:
                        await self._bot_task
                    except asyncio.CancelledError:
                        pass

                # Clean up references
                self._bot = None
                self._bot_task = None
                self._shutdown_event = None

                logger.info("Bot stopped successfully via BotController")
                return {"status": "success", "message": "Bot stopped"}

            except Exception as e:
                logger.error(f"Failed to stop bot: {e}", exc_info=True)
                return {"status": "error", "message": f"Failed to stop bot: {str(e)}"}

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
        await asyncio.sleep(2)

        # Start the bot
        start_result = await self.start_bot()
        return start_result

    async def trigger_check_now(self) -> Dict[str, str]:
        """
        Trigger an immediate slot check.
        
        Note: The current implementation logs the trigger request but does not
        interrupt the bot's sleep cycle. A full implementation would require
        adding a trigger event to VFSBot's main loop to immediately wake up
        and perform a check.
        
        Returns:
            Status dictionary with result
        """
        if not self.is_running:
            logger.warning("Cannot trigger check: bot is not running")
            return {"status": "error", "message": "Bot is not running"}

        # Log the trigger request - a full implementation would set an event
        # that the bot loop monitors to immediately perform a check
        logger.info("Manual check triggered via BotController")
        return {"status": "success", "message": "Manual check triggered"}

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
