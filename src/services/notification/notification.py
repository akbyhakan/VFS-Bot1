"""Notification system with Telegram and Email support.

This module re-exports all public names from the modular notification sub-packages
for backward compatibility. New code should import directly from:
- src.services.notification.base (ABC, configs)
- src.services.notification.channels (TelegramChannel, EmailChannel, WebSocketChannel)
- src.services.notification.service (NotificationService)
"""

from .base import (
    EmailConfig,
    NotificationChannel,
    NotificationConfig,
    NotificationPriority,
    TelegramConfig,
)
from .channels.email import EmailChannel
from .channels.telegram import TelegramChannel
from .channels.websocket import WebSocketChannel
from .service import NotificationService

__all__ = [
    "NotificationPriority",
    "TelegramConfig",
    "EmailConfig",
    "NotificationConfig",
    "NotificationChannel",
    "TelegramChannel",
    "EmailChannel",
    "WebSocketChannel",
    "NotificationService",
]
