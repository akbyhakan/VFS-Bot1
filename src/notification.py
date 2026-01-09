"""Notification system with Telegram and Email support."""

import logging
import asyncio
from typing import Optional, Dict, Any
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


class NotificationService:
    """Multi-channel notification service for VFS-Bot."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize notification service.

        Args:
            config: Notification configuration dictionary
        """
        self.config = config
        self.telegram_enabled = config.get("telegram", {}).get("enabled", False)
        self.email_enabled = config.get("email", {}).get("enabled", False)
        logger.info(
            f"NotificationService initialized (Telegram: {self.telegram_enabled}, Email: {self.email_enabled})"
        )

    async def send_notification(self, title: str, message: str, priority: str = "normal") -> None:
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
            from telegram import Bot

            telegram_config = self.config.get("telegram", {})
            bot_token = telegram_config.get("bot_token")
            chat_id = telegram_config.get("chat_id")

            if not bot_token or not chat_id:
                logger.error("Telegram credentials missing")
                return False

            bot = Bot(token=bot_token)
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

            # Add body
            html_body = f"""
            <html>
                <body>
                    <h2>{subject}</h2>
                    <p>{body.replace('\n', '<br>')}</p>
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
