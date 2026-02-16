"""NotificationService orchestrator - multi-channel notification service."""

import asyncio
from typing import Any, Dict, List, Optional, Union

from loguru import logger

from src.services.notification.telegram_client import TelegramClient

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


class NotificationService:
    """Multi-channel notification service for VFS-Bot."""

    def __init__(self, config: Union[NotificationConfig, Dict[str, Any]]):
        """
        Initialize notification service.

        Args:
            config: Notification configuration (NotificationConfig or dict for backward compatibility)
        """
        # Convert dict to NotificationConfig for backward compatibility
        if isinstance(config, dict):
            config = NotificationConfig.from_dict(config)

        self.config = config
        self.telegram_enabled = config.telegram.enabled
        self.email_enabled = config.email.enabled
        self._failed_high_priority_count = 0

        # Initialize channels using Strategy Pattern
        self._channels: List[NotificationChannel] = []
        self._telegram_channel: Optional[TelegramChannel] = None
        self._email_channel: Optional[EmailChannel] = None
        self._websocket_channel = WebSocketChannel()

        # Create Telegram channel if enabled
        if config.telegram.enabled:
            self._telegram_channel = TelegramChannel(config.telegram)
            self._channels.append(self._telegram_channel)

        # Create Email channel if enabled
        if config.email.enabled:
            self._email_channel = EmailChannel(config.email)
            self._channels.append(self._email_channel)

        # Legacy compatibility - keep these for backward compatibility
        self._websocket_manager = None
        self._telegram_client = (
            self._telegram_channel._client if self._telegram_channel else None
        )

        logger.info(
            f"NotificationService initialized "
            f"(Telegram: {self.telegram_enabled}, Email: {self.email_enabled})"
        )

    def _get_or_create_telegram_client(self) -> Optional[TelegramClient]:
        """
        Get cached Telegram client instance or create a new one.

        Returns:
            TelegramClient instance or None if bot_token is missing
        """
        if self._telegram_channel:
            return self._telegram_channel._get_or_create_client()
        return None

    def set_websocket_manager(self, manager) -> None:
        """
        Set WebSocket manager for fallback notifications.

        Args:
            manager: WebSocket ConnectionManager instance
        """
        self._websocket_manager = manager
        self._websocket_channel.set_manager(manager)
        logger.debug("WebSocket manager set for notification fallback")

    async def _broadcast_via_websocket(self, title: str, message: str) -> bool:
        """
        Broadcast critical notification via WebSocket as fallback.

        Args:
            title: Notification title
            message: Notification message

        Returns:
            True if broadcast succeeded
        """
        return await self._websocket_channel.send(title, message)

    def get_notification_stats(self) -> dict:
        """
        Get notification service statistics.

        Returns:
            Dictionary with notification stats including failed high-priority count
        """
        return {
            "telegram_enabled": self.telegram_enabled,
            "email_enabled": self.email_enabled,
            "websocket_available": self._websocket_manager is not None,
            "failed_high_priority_notifications": self._failed_high_priority_count,
        }

    @staticmethod
    def _split_message(text: str, max_length: int) -> list:
        """
        Split a message into chunks (for backward compatibility with tests).

        Args:
            text: Text to split
            max_length: Maximum length per chunk

        Returns:
            List of text chunks
        """
        return TelegramClient.split_message(text, max_length)

    async def send_notification(
        self, title: str, message: str, priority: NotificationPriority = "normal"
    ) -> bool:
        """
        Send notification through all enabled channels.

        Args:
            title: Notification title
            message: Notification message
            priority: Priority level (low, normal, high)

        Returns:
            True if at least one channel succeeded, False if all failed
        """
        tasks = []
        channel_names = []

        # Use Strategy Pattern - iterate over channels
        # For backward compatibility with tests/mocks, we call through the deprecated methods
        # if they exist and are the original (not overridden)
        if self.telegram_enabled:
            tasks.append(self.send_telegram(title, message))
            channel_names.append("telegram")

        if self.email_enabled:
            tasks.append(self.send_email(title, message))
            channel_names.append("email")

        if not tasks:
            logger.warning("No notification channels enabled")
            return False

        # Execute all notification tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Track success/failure
        any_success = False
        all_failed = True

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Notification channel '{channel_names[i]}' failed: {result}")
            elif result is True:
                any_success = True
                all_failed = False

        # If all primary channels failed and priority is high, try WebSocket fallback
        if all_failed and priority == "high":
            logger.warning(
                f"All primary channels failed for high-priority notification: {title}"
            )
            self._failed_high_priority_count += 1

            # Try WebSocket fallback
            ws_success = await self._websocket_channel.send(title, message)
            if ws_success:
                logger.info("WebSocket fallback succeeded for high-priority notification")
                return True
            else:
                logger.error(
                    "All channels (including WebSocket fallback) failed for high-priority notification"
                )
                return False

        return any_success

    async def send_telegram(self, title: str, message: str) -> bool:
        """
        Send Telegram notification.

        Args:
            title: Message title
            message: Message content

        Returns:
            True if successful
        """
        if self._telegram_channel:
            return await self._telegram_channel.send(title, message)
        return False

    async def send_email(self, subject: str, body: str) -> bool:
        """
        Send email notification.

        Args:
            subject: Email subject
            body: Email body

        Returns:
            True if successful
        """
        if self._email_channel:
            return await self._email_channel.send(subject, body)
        return False

    async def notify_slot_found(self, centre: str, date: str, time: str) -> None:
        """
        Send notification when appointment slot is found.

        Args:
            centre: VFS centre name
            date: Appointment date
            time: Appointment time
        """
        title = "🎉 Appointment Slot Found!"
        message = f"""
Centre: {centre}
Date: {date}
Time: {time}

The bot is proceeding with the booking.
"""
        await self.send_notification(title, message, priority="high")

    async def notify_booking_success(
        self, centre: str, date: str, time: str, reference: str
    ) -> None:
        """
        Send notification when booking is successful.

        Args:
            centre: VFS centre name
            date: Appointment date
            time: Appointment time
            reference: Booking reference number
        """
        title = "✅ Appointment Booked Successfully!"
        message = f"""
Centre: {centre}
Date: {date}
Time: {time}
Reference: {reference}

Your appointment has been successfully booked!
"""
        await self.send_notification(title, message, priority="high")

    async def notify_error(self, error_type: str, details: str) -> None:
        """
        Send notification when an error occurs.

        Args:
            error_type: Type of error
            details: Error details
        """
        title = f"❌ Error: {error_type}"
        message = f"""
An error occurred during bot execution:

{details}

The bot will retry automatically.
"""
        await self.send_notification(title, message, priority="normal")

    async def notify_bot_started(self) -> None:
        """Send notification when bot starts."""
        title = "🚀 VFS-Bot Started"
        message = "The bot has started checking for appointment slots."
        await self.send_notification(title, message, priority="low")

    async def notify_bot_stopped(self) -> None:
        """Send notification when bot stops."""
        title = "🛑 VFS-Bot Stopped"
        message = "The bot has been stopped."
        await self.send_notification(title, message, priority="low")

    async def notify_waitlist_success(
        self, details: dict, screenshot_path: Optional[str] = None
    ) -> None:
        """
        Send notification when waitlist registration is successful.

        Args:
            details: Dictionary with waitlist details
            screenshot_path: Optional path to screenshot file
        """
        try:
            # Build people list
            people_list = ""
            people = details.get("people", [])
            if people:
                for i, person in enumerate(people, 1):
                    people_list += f"   {i}. {person}\n"
            else:
                people_list = "   (Information unavailable)\n"

            # Format datetime - use helper to convert UTC to local time for display
            from src.utils.helpers import format_local_datetime

            # Get timezone from config, default to Europe/Istanbul
            timezone_name = self.config.get("timezone", "Europe/Istanbul")
            dt_str = format_local_datetime(tz_name=timezone_name)

            # Build message
            title = "✅ BEKLEME LİSTESİNE KAYIT BAŞARILI!"
            message = f"""
📧 Giriş Yapılan Hesap: {details.get('login_email', 'N/A')}
📋 Referans: {details.get('reference_number', 'N/A')}

👥 Kayıt Yapılan Kişiler:
{people_list}
🌍 Ülke: {details.get('country', 'N/A')}
📍 Merkez: {details.get('centre', 'N/A')}
📂 Kategori: {details.get('category', 'N/A')}
📁 Alt Kategori: {details.get('subcategory', 'N/A')}

💰 Toplam Ücret: {details.get('total_amount', 'N/A')}

📅 Tarih: {dt_str}

ℹ️ Bekleme listesi durumunuz güncellendiğinde bilgilendirileceksiniz.
"""

            # Send notification with screenshot if available
            if self.telegram_enabled and screenshot_path:
                await self._send_telegram_with_photo(title, message, screenshot_path)
            else:
                await self.send_notification(title, message, priority="high")

        except Exception as e:
            logger.error(f"Failed to send waitlist success notification: {e}")

    async def _send_telegram_with_photo(self, title: str, message: str, photo_path: str) -> bool:
        """
        Send Telegram notification with photo attachment.

        Args:
            title: Message title
            message: Message content
            photo_path: Path to photo file

        Returns:
            True if successful
        """
        try:
            from pathlib import Path

            if not self._telegram_channel:
                logger.error("Telegram channel not initialized")
                return False

            chat_id = self.config.telegram.chat_id

            if not chat_id:
                logger.error("Telegram chat_id missing")
                return False

            photo_file = Path(photo_path)
            if not photo_file.exists():
                logger.warning(f"Screenshot file not found: {photo_path}")
                # Fall back to text-only message
                return await self._telegram_channel.send(title, message)

            # Get client from channel
            client = self._telegram_channel._get_or_create_client()
            if client is None:
                return False

            # Escape markdown special characters to prevent injection
            escaped_title = TelegramClient.escape_markdown(title)
            escaped_message = TelegramClient.escape_markdown(message)
            full_message = f"🤖 *{escaped_title}*\n\n{escaped_message}"

            # Send photo with caption (client handles truncation)
            success = await client.send_photo(
                chat_id=chat_id, photo_path=photo_path, caption=full_message
            )

            # If caption was truncated, send remaining text as separate message
            if success and len(full_message) > TelegramClient.TELEGRAM_CAPTION_LIMIT:
                remaining_text = full_message[TelegramClient.TELEGRAM_CAPTION_LIMIT - 3 :]
                await client.send_message(chat_id=chat_id, text=remaining_text)

            if success:
                logger.info("Telegram notification with photo sent successfully")
            return success

        except ImportError:
            logger.warning("python-telegram-bot not installed")
            return False
        except Exception as e:
            logger.error(f"Telegram notification with photo failed: {e}")
            return False
