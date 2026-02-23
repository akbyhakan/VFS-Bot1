"""Telegram notification channel."""

from typing import Optional

from loguru import logger

from src.services.notification.telegram_client import TelegramClient
from src.services.notification.telegram_safety import safe_telegram_call

from ..base import NotificationChannel, TelegramConfig


class TelegramChannel(NotificationChannel):
    """Telegram notification channel."""

    def __init__(self, config: TelegramConfig):
        """
        Initialize Telegram channel.

        Args:
            config: Telegram configuration
        """
        self._config = config
        self._client: Optional[TelegramClient] = None

        if self._config.enabled and self._config.bot_token_plain:
            try:
                self._client = TelegramClient(bot_token=self._config.bot_token_plain)
            except ImportError:
                logger.warning("python-telegram-bot not installed")
            except Exception as e:
                logger.warning(f"Failed to initialize Telegram client: {e}")

    @property
    def name(self) -> str:
        """Get channel name."""
        return "telegram"

    @property
    def enabled(self) -> bool:
        """Check if channel is enabled."""
        return self._config.enabled

    def _get_or_create_client(self) -> Optional[TelegramClient]:
        """Get cached client or create new one."""
        if self._client is not None:
            return self._client

        if not self._config.bot_token_plain:
            logger.error("Telegram bot_token missing")
            return None

        try:
            self._client = TelegramClient(bot_token=self._config.bot_token_plain)
            return self._client
        except ImportError:
            logger.warning("python-telegram-bot not installed")
            return None
        except Exception as e:
            logger.error(f"Failed to create Telegram client: {e}")
            return None

    @safe_telegram_call("notification")
    async def send(self, title: str, message: str) -> bool:
        """
        Send Telegram notification.

        Args:
            title: Message title
            message: Message content

        Returns:
            True if successful
        """
        if not self._config.chat_id:
            logger.error("Telegram chat_id missing")
            return False

        client = self._get_or_create_client()
        if client is None:
            return False

        success = await client.format_and_send(
            chat_id=self._config.chat_id, title=title, message=message
        )

        if success:
            logger.info("Telegram notification sent successfully")
        return success
