"""Unified Telegram client wrapper for VFS-Bot."""

from typing import Optional

from loguru import logger

from src.services.notification.telegram_safety import safe_telegram_call
from src.core.infra.retry import get_telegram_retry


class TelegramClient:
    """Unified Telegram client wrapper using python-telegram-bot library."""

    # Telegram API message limits
    TELEGRAM_MESSAGE_LIMIT = 4096
    TELEGRAM_CAPTION_LIMIT = 1024

    def __init__(self, bot_token: str):
        """
        Initialize Telegram client.

        Args:
            bot_token: Telegram bot token

        Raises:
            ImportError: If python-telegram-bot is not installed
            Exception: If bot initialization fails (e.g., invalid token)
        """
        try:
            from telegram import Bot
        except ImportError as e:
            logger.error("python-telegram-bot not installed")
            raise ImportError("python-telegram-bot library is required") from e

        try:
            self._bot = Bot(token=bot_token)
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            raise

    @staticmethod
    def escape_markdown(text: str) -> str:
        """
        Escape Telegram Markdown special characters.

        Args:
            text: Text to escape

        Returns:
            Escaped text safe for Markdown parse_mode
        """
        # Escape Markdown special characters: * _ ` [ ] ( )
        special_chars = ["*", "_", "`", "[", "]", "(", ")"]
        for char in special_chars:
            text = text.replace(char, "\\" + char)
        return text

    @staticmethod
    def split_message(text: str, max_length: Optional[int] = None) -> list:
        """
        Split a message into chunks that fit within the max_length limit.

        Tries to split at newlines first, then at spaces to avoid breaking words.

        Args:
            text: Text to split
            max_length: Maximum length per chunk (defaults to TELEGRAM_MESSAGE_LIMIT)

        Returns:
            List of text chunks, each <= max_length
        """
        if max_length is None:
            max_length = TelegramClient.TELEGRAM_MESSAGE_LIMIT

        if len(text) <= max_length:
            return [text]

        chunks = []
        remaining = text

        while remaining:
            if len(remaining) <= max_length:
                chunks.append(remaining)
                break

            # Try to find a newline to split at
            split_pos = remaining.rfind("\n", 0, max_length)

            # If no newline found, try to split at a space
            if split_pos == -1:
                split_pos = remaining.rfind(" ", 0, max_length)

            # If no space found either, force split at max_length
            if split_pos == -1:
                split_pos = max_length
                chunks.append(remaining[:split_pos])
                remaining = remaining[split_pos:]
            else:
                # Split at newline or space, skip the delimiter
                chunks.append(remaining[:split_pos])
                remaining = remaining[split_pos + 1 :]

        return chunks

    @get_telegram_retry()
    @safe_telegram_call("send message")
    async def send_message(self, chat_id: str, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a text message via Telegram with automatic message splitting.

        Args:
            chat_id: Telegram chat ID
            text: Message text
            parse_mode: Parse mode for message formatting (default: "Markdown")

        Returns:
            True if successful, False otherwise
        """
        # Split message if it exceeds Telegram's limit
        message_chunks = self.split_message(text, self.TELEGRAM_MESSAGE_LIMIT)

        # Send all chunks
        for chunk in message_chunks:
            await self._bot.send_message(chat_id=chat_id, text=chunk, parse_mode=parse_mode)

        logger.debug(f"Telegram message sent successfully ({len(message_chunks)} chunk(s))")
        return True

    @get_telegram_retry()
    @safe_telegram_call("send photo")
    async def send_photo(
        self,
        chat_id: str,
        photo_path: str,
        caption: Optional[str] = None,
        parse_mode: str = "Markdown",
    ) -> bool:
        """
        Send a photo via Telegram with optional caption.

        Args:
            chat_id: Telegram chat ID
            photo_path: Path to photo file
            caption: Optional caption for the photo
            parse_mode: Parse mode for caption formatting (default: "Markdown")

        Returns:
            True if successful, False otherwise
        """
        from pathlib import Path

        photo_file = Path(photo_path)
        if not photo_file.exists():
            logger.warning(f"Photo file not found: {photo_path}")
            return False

        # Truncate caption if it exceeds limit
        final_caption = caption
        if caption and len(caption) > self.TELEGRAM_CAPTION_LIMIT:
            logger.warning(f"Caption exceeds {self.TELEGRAM_CAPTION_LIMIT} chars, truncating")
            final_caption = caption[: self.TELEGRAM_CAPTION_LIMIT - 3] + "..."

        with open(photo_file, "rb") as photo:
            await self._bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=final_caption,
                parse_mode=parse_mode if final_caption else None,
            )

        logger.debug("Telegram photo sent successfully")
        return True
