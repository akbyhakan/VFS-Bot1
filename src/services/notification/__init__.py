"""Notification subsystem - Telegram and alert services.

This module provides notification and alerting capabilities for VFS-Bot,
including Telegram messaging and multi-channel alerts.

Public API:
- NotificationService: Multi-channel notification service
- NotificationConfig: Notification service configuration
- TelegramConfig: Telegram channel configuration
- NotificationChannel: Abstract base class for notification channels
- TelegramChannel: Telegram notification channel
- WebSocketChannel: WebSocket notification channel
- TelegramClient: Unified Telegram client wrapper
- AlertService: Multi-channel alert service
- AlertConfig: Alert service configuration
- AlertSeverity: Alert severity levels
- AlertChannel: Alert delivery channels
- send_critical_alert: Convenience function for critical alerts
- send_alert_safe: Safe wrapper for sending alerts
- get_alert_service: Get global alert service instance
- configure_alert_service: Configure global alert service
"""

from .alert_service import (
    AlertChannel,
    AlertConfig,
    AlertService,
    AlertSeverity,
    configure_alert_service,
    get_alert_service,
    send_alert_safe,
    send_critical_alert,
)
from .base import (
    NotificationChannel,
    NotificationConfig,
    TelegramConfig,
)
from .channels.telegram import TelegramChannel
from .channels.websocket import WebSocketChannel
from .service import NotificationService
from .telegram_client import TelegramClient

__all__ = [
    "NotificationService",
    "NotificationConfig",
    "TelegramConfig",
    "NotificationChannel",
    "TelegramChannel",
    "WebSocketChannel",
    "TelegramClient",
    "AlertService",
    "AlertConfig",
    "AlertSeverity",
    "AlertChannel",
    "send_critical_alert",
    "send_alert_safe",
    "get_alert_service",
    "configure_alert_service",
]
