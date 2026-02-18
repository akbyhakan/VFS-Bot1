"""WebSocket notification channel."""

import asyncio
from typing import Any

from loguru import logger

from ..base import NotificationChannel


class WebSocketChannel(NotificationChannel):
    """WebSocket notification channel for real-time notifications."""

    def __init__(self, websocket_manager=None):
        """
        Initialize WebSocket channel.

        Args:
            websocket_manager: WebSocket ConnectionManager instance
        """
        self._manager = websocket_manager

    @property
    def name(self) -> str:
        """Get channel name."""
        return "websocket"

    @property
    def enabled(self) -> bool:
        """Check if channel is enabled."""
        return self._manager is not None

    def set_manager(self, manager: Any) -> None:
        """
        Set WebSocket manager.

        Args:
            manager: WebSocket ConnectionManager instance
        """
        self._manager = manager

    async def send(self, title: str, message: str) -> bool:
        """
        Broadcast notification via WebSocket.

        Args:
            title: Notification title
            message: Notification message

        Returns:
            True if broadcast succeeded
        """
        if not self._manager:
            logger.debug("WebSocket manager not available")
            return False

        try:
            notification_data = {
                "type": "critical_notification",
                "data": {
                    "title": title,
                    "message": message,
                    "timestamp": asyncio.get_running_loop().time(),
                    "priority": "high",
                },
            }

            if hasattr(self._manager, "broadcast"):
                await self._manager.broadcast(notification_data)
                logger.info(f"Notification broadcasted via WebSocket: {title}")
                return True
            else:
                logger.warning("WebSocket manager has no broadcast method")
                return False

        except Exception as e:
            logger.error(f"WebSocket broadcast failed: {e}")
            return False
