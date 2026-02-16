"""Notification subsystem - Telegram, Email, and alert services.

This module provides notification and alerting capabilities for VFS-Bot,
including Telegram messaging, email notifications, and multi-channel alerts.

Public API:
- NotificationService: Multi-channel notification service
- NotificationConfig: Notification service configuration
- TelegramConfig: Telegram channel configuration
- EmailConfig: Email channel configuration
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
from .notification import (
    EmailChannel,
    EmailConfig,
    NotificationChannel,
    NotificationConfig,
    NotificationService,
    TelegramChannel,
    TelegramConfig,
    WebSocketChannel,
)
from .telegram_client import TelegramClient

__all__ = [
    "NotificationService",
    "NotificationConfig",
    "TelegramConfig",
    "EmailConfig",
    "NotificationChannel",
    "TelegramChannel",
    "EmailChannel",
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
