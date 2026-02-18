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
        return (
            f"TelegramConfig(enabled={self.enabled}, bot_token={masked_token}, "
            f"chat_id='{self.chat_id}')"
        )


@dataclass
class NotificationConfig:
    """Notification service configuration."""

    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    timezone: str = "Europe/Istanbul"

    def __repr__(self) -> str:
        """Return repr with masked sensitive fields in nested configs."""
        return f"NotificationConfig(telegram={repr(self.telegram)}, " f"timezone='{self.timezone}')"

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

        return cls(
            telegram=telegram_config,
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
