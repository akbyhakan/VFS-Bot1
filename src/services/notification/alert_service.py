"""Alert service for sending critical notifications through multiple channels."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp
from loguru import logger

from src.services.notification.telegram_client import TelegramClient
from src.services.notification.telegram_safety import safe_telegram_call


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Alert delivery channels."""

    LOG = "log"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"


@dataclass
class AlertConfig:
    """Configuration for alert service."""

    enabled_channels: List[AlertChannel]
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    webhook_url: Optional[str] = None


class AlertService:
    """Service for sending alerts through multiple channels."""

    def __init__(self, config: AlertConfig):
        """
        Initialize alert service.

        Args:
            config: Alert configuration
        """
        self.config = config
        self.enabled_channels = set(config.enabled_channels)

        # Cache Telegram client instance if enabled
        self._telegram_client = None
        if AlertChannel.TELEGRAM in self.enabled_channels and config.telegram_bot_token:
            try:
                self._telegram_client = TelegramClient(bot_token=config.telegram_bot_token)
            except ImportError:
                logger.warning("python-telegram-bot not installed")
            except Exception as e:
                logger.warning(f"Failed to initialize Telegram client: {e}")

    async def send_alert(
        self,
        message: str,
        severity: AlertSeverity = AlertSeverity.INFO,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send alert through all enabled channels.

        Args:
            message: Alert message
            severity: Alert severity level
            metadata: Additional metadata to include

        Returns:
            True if at least one channel succeeded
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        alert_data = {
            "message": message,
            "severity": severity.value,
            "timestamp": timestamp,
            "metadata": metadata or {},
        }

        tasks = []

        # Always log
        if AlertChannel.LOG in self.enabled_channels:
            tasks.append(self._send_log(alert_data))

        if AlertChannel.TELEGRAM in self.enabled_channels:
            tasks.append(self._send_telegram(alert_data))

        if AlertChannel.WEBHOOK in self.enabled_channels:
            tasks.append(self._send_webhook(alert_data))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Return True if at least one channel succeeded
        return any(r is True for r in results if not isinstance(r, Exception))

    async def _send_log(self, alert_data: Dict[str, Any]) -> bool:
        """Send alert to logging system."""
        severity = alert_data["severity"]
        message = alert_data["message"]

        severity_emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}

        emoji = severity_emoji.get(severity, "📢")
        log_msg = f"{emoji} ALERT [{severity.upper()}]: {message}"

        if severity == "critical":
            logger.critical(log_msg)
        elif severity == "error":
            logger.error(log_msg)
        elif severity == "warning":
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return True

    @safe_telegram_call("alert")
    async def _send_telegram(self, alert_data: Dict[str, Any]) -> bool:
        """Send alert via Telegram."""
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            logger.debug("Telegram not configured, skipping")
            return False

        # Get or create client instance
        if not self._telegram_client:
            self._telegram_client = TelegramClient(bot_token=self.config.telegram_bot_token)

        severity = alert_data["severity"]
        message = alert_data["message"]
        timestamp = alert_data["timestamp"]

        emoji_map = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}

        emoji = emoji_map.get(severity, "📢")
        # Send message with escaped title and footer
        success = await self._telegram_client.format_and_send(
            chat_id=self.config.telegram_chat_id,
            title=f"ALERT [{severity.upper()}]",
            message=message,
            emoji=emoji,
            footer=f"Time: {timestamp}",
        )

        if success:
            logger.debug("Alert sent via Telegram")
        return success

    async def _send_webhook(self, alert_data: Dict[str, Any]) -> bool:
        """Send alert via webhook."""
        if not self.config.webhook_url:
            logger.debug("Webhook not configured, skipping")
            return False

        try:
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.post(
                    self.config.webhook_url, json=alert_data, timeout=timeout
                ) as response:
                    if response.status in (200, 201, 204):
                        logger.debug("Alert sent via webhook")
                        return True
                    else:
                        logger.error(f"Webhook error: {response.status}")
                        return False

        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error sending webhook alert: {e}")
            return False
        except asyncio.TimeoutError as e:
            logger.error(f"Timeout sending webhook alert: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False


async def send_alert_safe(
    alert_service: Optional[Any],
    message: str,
    severity: AlertSeverity = AlertSeverity.ERROR,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Send alert through alert service, silently failing on errors.

    This is a safe wrapper around AlertService.send_alert() that handles
    cases where alert_service is None or when sending fails.

    Args:
        alert_service: AlertService instance (can be None)
        message: Alert message to send
        severity: Alert severity level
        metadata: Optional metadata dictionary
    """
    if not alert_service:
        return
    try:
        await alert_service.send_alert(
            message=message,
            severity=severity,
            metadata=metadata or {},
        )
    except Exception as e:
        logger.debug(f"Alert delivery failed: {e}")


# Global alert service instance
_alert_service: Optional[AlertService] = None


def get_alert_service() -> AlertService:
    """
    Get or create global alert service instance.

    Returns:
        AlertService instance
    """
    global _alert_service

    if _alert_service is None:
        # Default configuration: only logging enabled
        config = AlertConfig(enabled_channels=[AlertChannel.LOG])
        _alert_service = AlertService(config)

    return _alert_service


def configure_alert_service(config: AlertConfig) -> None:
    """
    Configure global alert service.

    Args:
        config: Alert configuration
    """
    global _alert_service
    _alert_service = AlertService(config)


async def send_critical_alert(message: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Convenience function to send critical alert.

    Args:
        message: Alert message
        metadata: Additional metadata

    Returns:
        True if at least one channel succeeded
    """
    service = get_alert_service()
    return await service.send_alert(message, AlertSeverity.CRITICAL, metadata)
