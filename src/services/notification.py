"""Notification system with Telegram and Email support."""

import asyncio
import html
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Literal, Optional

import aiosmtplib

logger = logging.getLogger(__name__)

# Type aliases for better type hints
NotificationPriority = Literal["low", "normal", "high"]
NotificationConfig = Dict[str, Any]  # Could be TypedDict for more specificity


class NotificationService:
    """Multi-channel notification service for VFS-Bot."""

    def __init__(self, config: NotificationConfig):
        """
        Initialize notification service.

        Args:
            config: Notification configuration dictionary
        """
        self.config = config
        self.telegram_enabled = config.get("telegram", {}).get("enabled", False)
        self.email_enabled = config.get("email", {}).get("enabled", False)

        # Cache Telegram bot instance if enabled
        self._telegram_bot = None
        if self.telegram_enabled:
            try:
                from telegram import Bot

                telegram_config = config.get("telegram", {})
                bot_token = telegram_config.get("bot_token")
                if bot_token:
                    self._telegram_bot = Bot(token=bot_token)
            except Exception as e:
                logger.warning(f"Failed to initialize Telegram bot: {e}")

        logger.info(
            f"NotificationService initialized "
            f"(Telegram: {self.telegram_enabled}, Email: {self.email_enabled})"
        )

    def _get_or_create_telegram_bot(self) -> Optional[Any]:
        """
        Get cached Telegram bot instance or create a new one.
        
        Returns:
            Telegram Bot instance or None if bot_token is missing
        """
        if self._telegram_bot is not None:
            return self._telegram_bot
        
        telegram_config = self.config.get("telegram", {})
        bot_token = telegram_config.get("bot_token")
        
        if not bot_token:
            logger.error("Telegram bot_token missing")
            return None
        
        try:
            from telegram import Bot
            
            self._telegram_bot = Bot(token=bot_token)
            return self._telegram_bot
        except Exception as e:
            logger.error(f"Failed to create Telegram bot: {e}")
            return None

    async def send_notification(
        self, title: str, message: str, priority: NotificationPriority = "normal"
    ) -> None:
        """
        Send notification through all enabled channels.

        Args:
            title: Notification title
            message: Notification message
            priority: Priority level (low, normal, high)
        """
        tasks = []

        if self.telegram_enabled:
            tasks.append(self.send_telegram(title, message))

        if self.email_enabled:
            tasks.append(self.send_email(title, message))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Notification failed: {result}")
        else:
            logger.warning("No notification channels enabled")

    async def send_telegram(self, title: str, message: str) -> bool:
        """
        Send Telegram notification.

        Args:
            title: Message title
            message: Message content

        Returns:
            True if successful
        """
        try:
            telegram_config = self.config.get("telegram", {})
            chat_id = telegram_config.get("chat_id")

            if not chat_id:
                logger.error("Telegram chat_id missing")
                return False

            # Use helper to get or create bot instance
            bot = self._get_or_create_telegram_bot()
            if bot is None:
                return False

            full_message = f"🤖 *{title}*\n\n{message}"

            await bot.send_message(chat_id=chat_id, text=full_message, parse_mode="Markdown")

            logger.info("Telegram notification sent successfully")
            return True
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")
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
        try:
            email_config = self.config.get("email", {})
            sender = email_config.get("sender")
            password = email_config.get("password")
            receiver = email_config.get("receiver")
            smtp_server = email_config.get("smtp_server", "smtp.gmail.com")
            smtp_port = email_config.get("smtp_port", 587)

            if not all([sender, password, receiver]):
                logger.error("Email credentials missing")
                return False

            # Create message
            message = MIMEMultipart()
            message["From"] = sender
            message["To"] = receiver
            message["Subject"] = f"VFS-Bot: {subject}"

            # Add body with XSS protection
            # Escape HTML to prevent XSS attacks
            escaped_subject = html.escape(subject)
            escaped_body = html.escape(body).replace("\n", "<br>")
            html_body = f"""
            <html>
                <body>
                    <h2>{escaped_subject}</h2>
                    <p>{escaped_body}</p>
                    <hr>
                    <p><small>This is an automated message from VFS-Bot</small></p>
                </body>
            </html>
            """
            message.attach(MIMEText(html_body, "html"))

            # Send email
            async with aiosmtplib.SMTP(hostname=smtp_server, port=smtp_port) as smtp:
                await smtp.starttls()
                await smtp.login(sender, password)
                await smtp.send_message(message)

            logger.info("Email notification sent successfully")
            return True
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
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
            from ..utils.helpers import format_local_datetime

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

            telegram_config = self.config.get("telegram", {})
            chat_id = telegram_config.get("chat_id")

            if not chat_id:
                logger.error("Telegram chat_id missing")
                return False

            photo_file = Path(photo_path)
            if not photo_file.exists():
                logger.warning(f"Screenshot file not found: {photo_path}")
                # Fall back to text-only message
                return await self.send_telegram(title, message)

            # Use helper to get or create bot instance
            bot = self._get_or_create_telegram_bot()
            if bot is None:
                return False

            full_message = f"🤖 *{title}*\n\n{message}"

            with open(photo_file, "rb") as photo:
                await bot.send_photo(
                    chat_id=chat_id, photo=photo, caption=full_message, parse_mode="Markdown"
                )

            logger.info("Telegram notification with photo sent successfully")
            return True
        except Exception as e:
            logger.error(f"Telegram notification with photo failed: {e}")
            return False
