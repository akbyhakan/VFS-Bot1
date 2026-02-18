"""Notification system with Telegram support.

This module re-exports all public names from the modular notification sub-packages
for backward compatibility. New code should import directly from:
- src.services.notification.base (ABC, configs)
- src.services.notification.channels (TelegramChannel, WebSocketChannel)
- src.services.notification.service (NotificationService)
"""

from .base import (
    NotificationChannel,
    NotificationConfig,
    NotificationPriority,
    TelegramConfig,
)
from .channels.telegram import TelegramChannel
from .channels.websocket import WebSocketChannel
from .service import NotificationService

__all__ = [
    "NotificationPriority",
    "TelegramConfig",
    "NotificationConfig",
    "NotificationChannel",
    "TelegramChannel",
    "WebSocketChannel",
    "NotificationService",
]
