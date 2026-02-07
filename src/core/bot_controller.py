"""
Bot controller singleton for managing VFSBot instance lifecycle.

This module provides thread-safe access to the VFSBot instance and coordinates
bot control operations between the web dashboard and the bot runtime.
"""

import asyncio
import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BotController:
    """
    Thread-safe singleton controller for VFSBot instance management.
    
    This controller bridges the web dashboard and bot runtime, ensuring
    that dashboard control actions (start/stop/restart) actually affect
    the real VFSBot instance rather than just updating state dictionaries.
    """
    
    _instance: Optional["BotController"] = None
    _lock: threading.Lock = threading.Lock()
    
    def __new__(cls) -> "BotController":
        """
        Singleton pattern implementation.
        
        Returns:
            Single BotController instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the bot controller."""
        # Prevent re-initialization
        if self._initialized:
            return
            
        self._bot = None
        self._bot_task: Optional[asyncio.Task] = None
        self._shutdown_event: Optional[asyncio.Event] = None
        self._state_lock = threading.Lock()
        self._initialized = True
        logger.info("BotController initialized")
    
    def register_bot(
        self, 
        bot: Any, 
        bot_task: Optional[asyncio.Task] = None,
        shutdown_event: Optional[asyncio.Event] = None
    ) -> None:
        """
        Register the VFSBot instance with the controller.
        
        Args:
            bot: VFSBot instance
            bot_task: Optional task running the bot
            shutdown_event: Optional shutdown event for graceful shutdown
        """
        with self._state_lock:
            self._bot = bot
            self._bot_task = bot_task
            self._shutdown_event = shutdown_event
            logger.info("VFSBot instance registered with BotController")
    
    def get_bot(self) -> Optional[Any]:
        """
        Get the registered VFSBot instance.
        
        Returns:
            VFSBot instance or None if not registered
        """
        with self._state_lock:
            return self._bot
    
    def is_running(self) -> bool:
        """
        Check if the bot is currently running.
        
        Returns:
            True if bot is running, False otherwise
        """
        with self._state_lock:
            if self._bot is None:
                return False
            return getattr(self._bot, 'running', False)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current bot status.
        
        Returns:
            Dictionary containing bot status information
        """
        with self._state_lock:
            if self._bot is None:
                return {
                    'registered': False,
                    'running': False,
                    'status': 'not_initialized'
                }
            
            return {
                'registered': True,
                'running': getattr(self._bot, 'running', False),
                'status': 'running' if getattr(self._bot, 'running', False) else 'stopped'
            }
    
    async def start_bot(self) -> Dict[str, str]:
        """
        Start the bot if it's registered and not already running.
        
        Returns:
            Dictionary with status and message
        """
        with self._state_lock:
            if self._bot is None:
                logger.warning("Cannot start bot: No bot instance registered")
                return {
                    'status': 'error',
                    'message': 'Bot not initialized. Start in combined mode.'
                }
            
            if getattr(self._bot, 'running', False):
                return {
                    'status': 'error',
                    'message': 'Bot is already running'
                }
            
            bot = self._bot
        
        # Start bot outside the lock to avoid blocking
        try:
            # Set running flag
            bot.running = True
            logger.info("Bot started via BotController")
            
            # Sync state to bot_state dict for UI updates
            await self._sync_state_to_dict(running=True, status='running')
            
            return {
                'status': 'success',
                'message': 'Bot started successfully'
            }
        except Exception as e:
            logger.error(f"Error starting bot: {e}", exc_info=True)
            bot.running = False
            await self._sync_state_to_dict(running=False, status='error')
            return {
                'status': 'error',
                'message': f'Failed to start bot: {str(e)}'
            }
    
    async def stop_bot(self) -> Dict[str, str]:
        """
        Stop the bot if it's registered and running.
        
        Returns:
            Dictionary with status and message
        """
        with self._state_lock:
            if self._bot is None:
                logger.warning("Cannot stop bot: No bot instance registered")
                return {
                    'status': 'error',
                    'message': 'Bot not initialized'
                }
            
            if not getattr(self._bot, 'running', False):
                return {
                    'status': 'error',
                    'message': 'Bot is not running'
                }
            
            bot = self._bot
            shutdown_event = self._shutdown_event
        
        # Stop bot outside the lock
        try:
            # Set running flag to False to stop the bot loop
            bot.running = False
            
            # Signal shutdown event if available
            if shutdown_event and not shutdown_event.is_set():
                shutdown_event.set()
            
            logger.info("Bot stopped via BotController")
            
            # Sync state to bot_state dict for UI updates
            await self._sync_state_to_dict(running=False, status='stopped')
            
            return {
                'status': 'success',
                'message': 'Bot stopped successfully'
            }
        except Exception as e:
            logger.error(f"Error stopping bot: {e}", exc_info=True)
            await self._sync_state_to_dict(running=False, status='error')
            return {
                'status': 'error',
                'message': f'Failed to stop bot: {str(e)}'
            }
    
    async def restart_bot(self) -> Dict[str, str]:
        """
        Restart the bot (stop then start).
        
        Returns:
            Dictionary with status and message
        """
        with self._state_lock:
            if self._bot is None:
                logger.warning("Cannot restart bot: No bot instance registered")
                return {
                    'status': 'error',
                    'message': 'Bot not initialized'
                }
        
        # Update state to restarting
        await self._sync_state_to_dict(running=False, status='restarting')
        
        # Stop the bot
        stop_result = await self.stop_bot()
        if stop_result['status'] == 'error' and 'not running' not in stop_result['message']:
            return stop_result
        
        # Small delay to ensure clean shutdown
        await asyncio.sleep(2)
        
        # Start the bot
        start_result = await self.start_bot()
        if start_result['status'] == 'success':
            logger.info("Bot restarted successfully via BotController")
            return {
                'status': 'success',
                'message': 'Bot restarted successfully'
            }
        
        return start_result
    
    async def _sync_state_to_dict(self, running: bool, status: str) -> None:
        """
        Synchronize bot state to the ThreadSafeBotState dict for UI updates.
        
        Args:
            running: Whether the bot is running
            status: Bot status string
        """
        try:
            # Import here to avoid circular dependency
            from web.dependencies import bot_state, broadcast_message
            
            bot_state['running'] = running
            bot_state['status'] = status
            
            # Broadcast state update to WebSocket clients
            await broadcast_message({
                'type': 'status',
                'data': {
                    'running': running,
                    'status': status,
                    'message': f'Bot {status}'
                }
            })
        except Exception as e:
            logger.warning(f"Failed to sync state to bot_state dict: {e}")
    
    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset the singleton instance (for testing purposes only).
        
        Warning: This should only be used in tests.
        """
        with cls._lock:
            cls._instance = None
