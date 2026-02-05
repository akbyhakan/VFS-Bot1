"""Alert service for sending critical notifications through multiple channels."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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
    EMAIL = "email"
    WEBHOOK = "webhook"


@dataclass
class AlertConfig:
    """Configuration for alert service."""

    enabled_channels: List[AlertChannel]
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    email_from: Optional[str] = None
    email_to: Optional[List[str]] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
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

        if AlertChannel.EMAIL in self.enabled_channels:
            tasks.append(self._send_email(alert_data))

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

    async def _send_telegram(self, alert_data: Dict[str, Any]) -> bool:
        """Send alert via Telegram."""
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            logger.debug("Telegram not configured, skipping")
            return False

        try:
            import aiohttp

            severity = alert_data["severity"]
            message = alert_data["message"]
            timestamp = alert_data["timestamp"]

            emoji_map = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}

            emoji = emoji_map.get(severity, "📢")
            text = f"{emoji} *ALERT [{severity.upper()}]*\n\n{message}\n\n_Time: {timestamp}_"

            url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": self.config.telegram_chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }

            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.post(url, json=payload, timeout=timeout) as response:
                    if response.status == 200:
                        logger.debug("Alert sent via Telegram")
                        return True
                    else:
                        logger.error(f"Telegram API error: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False

    async def _send_email(self, alert_data: Dict[str, Any]) -> bool:
        """Send alert via email."""
        if not all(
            [
                self.config.email_from,
                self.config.email_to,
                self.config.smtp_host,
                self.config.smtp_port,
            ]
        ):
            logger.debug("Email not configured, skipping")
            return False

        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            import aiosmtplib

            severity = alert_data["severity"]
            message = alert_data["message"]
            timestamp = alert_data["timestamp"]

            msg = MIMEMultipart()
            msg["From"] = self.config.email_from
            email_to = self.config.email_to or []
            msg["To"] = ", ".join(email_to)
            msg["Subject"] = f"[{severity.upper()}] VFS-Bot Alert"

            body = f"""
Alert Severity: {severity.upper()}
Time: {timestamp}

Message:
{message}

---
This is an automated alert from VFS-Bot Alert Service.
"""
            msg.attach(MIMEText(body, "plain"))

            await aiosmtplib.send(
                msg, hostname=self.config.smtp_host, port=self.config.smtp_port, timeout=10
            )

            logger.debug("Alert sent via email")
            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False

    async def _send_webhook(self, alert_data: Dict[str, Any]) -> bool:
        """Send alert via webhook."""
        if not self.config.webhook_url:
            logger.debug("Webhook not configured, skipping")
            return False

        try:
            import aiohttp

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

        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False


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
