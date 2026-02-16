"""Base notification types: ABC, config dataclasses, and type aliases."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

NotificationPriority = Literal["low", "normal", "high"]


@dataclass
class TelegramConfig:
    """Telegram notification configuration."""

    enabled: bool = False
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None

    def __repr__(self) -> str:
        """Return repr with masked bot_token."""
        if self.bot_token:
            masked_token = "'***'"
        else:
            masked_token = "None"
        return f"TelegramConfig(enabled={self.enabled}, bot_token={masked_token}, chat_id='{self.chat_id}')"


@dataclass
class EmailConfig:
    """Email notification configuration."""

    enabled: bool = False
    sender: Optional[str] = None
    password: Optional[str] = None
    receiver: Optional[str] = None
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587

    def __repr__(self) -> str:
        """Return repr with masked password."""
        if self.password:
            masked_password = "'***'"
        else:
            masked_password = "None"
        return (
            f"EmailConfig(enabled={self.enabled}, sender={repr(self.sender)}, "
            f"password={masked_password}, receiver={repr(self.receiver)}, "
            f"smtp_server={repr(self.smtp_server)}, smtp_port={self.smtp_port})"
        )


@dataclass
class NotificationConfig:
    """Notification service configuration."""

    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    timezone: str = "Europe/Istanbul"

    def __repr__(self) -> str:
        """Return repr with masked sensitive fields in nested configs."""
        return (
            f"NotificationConfig(telegram={repr(self.telegram)}, "
            f"email={repr(self.email)}, timezone='{self.timezone}')"
        )

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "NotificationConfig":
        """
        Create NotificationConfig from dictionary (backward compatibility).

        Args:
            config_dict: Configuration dictionary

        Returns:
            NotificationConfig instance
        """
        telegram_data = config_dict.get("telegram", {})
        telegram_config = TelegramConfig(
            enabled=telegram_data.get("enabled", False),
            bot_token=telegram_data.get("bot_token"),
            chat_id=telegram_data.get("chat_id"),
        )

        email_data = config_dict.get("email", {})
        email_config = EmailConfig(
            enabled=email_data.get("enabled", False),
            sender=email_data.get("sender"),
            password=email_data.get("password"),
            receiver=email_data.get("receiver"),
            smtp_server=email_data.get("smtp_server", "smtp.gmail.com"),
            smtp_port=email_data.get("smtp_port", 587),
        )

        return cls(
            telegram=telegram_config,
            email=email_config,
            timezone=config_dict.get("timezone", "Europe/Istanbul"),
        )


class NotificationChannel(ABC):
    """Abstract base class for notification channels."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Get channel name."""
        pass

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """Check if channel is enabled."""
        pass

    @abstractmethod
    async def send(self, title: str, message: str) -> bool:
        """
        Send notification through this channel.

        Args:
            title: Notification title
            message: Notification message

        Returns:
            True if successful
        """
        pass
