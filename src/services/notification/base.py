"""Base notification types: ABC, config re-exports, and type aliases."""

from abc import ABC, abstractmethod
from typing import Literal

from src.core.config.config_models import (
    NotificationConfig,
    TelegramConfig,
)

NotificationPriority = Literal["low", "normal", "high"]

# Re-export for backward compatibility - all existing imports from base will continue to work
__all__ = [
    "TelegramConfig",
    "NotificationConfig",
    "NotificationPriority",
    "NotificationChannel",
]


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
