"""Email notification channel."""

import html
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from loguru import logger

from src.utils.decorators import retry_async

from ..base import EmailConfig, NotificationChannel


class EmailChannel(NotificationChannel):
    """Email notification channel."""

    def __init__(self, config: EmailConfig):
        """
        Initialize Email channel.

        Args:
            config: Email configuration
        """
        self._config = config

    @property
    def name(self) -> str:
        """Get channel name."""
        return "email"

    @property
    def enabled(self) -> bool:
        """Check if channel is enabled."""
        return self._config.enabled

    @retry_async(
        max_retries=2,
        delay=1.0,
        backoff=2.0,
        exceptions=(ConnectionError, TimeoutError, OSError, aiosmtplib.SMTPException),
    )
    async def send(self, subject: str, body: str) -> bool:
        """
        Send email notification.

        Args:
            subject: Email subject
            body: Email body

        Returns:
            True if successful
        """
        try:
            if not all([self._config.sender, self._config.password, self._config.receiver]):
                logger.error("Email credentials missing")
                return False

            sender = self._config.sender or ""
            password = self._config.password or ""
            receiver = self._config.receiver or ""

            # Create message
            message = MIMEMultipart()
            message["From"] = sender
            message["To"] = receiver
            message["Subject"] = f"VFS-Bot: {subject}"

            # Add body with XSS protection
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
            async with aiosmtplib.SMTP(
                hostname=self._config.smtp_server, port=self._config.smtp_port
            ) as smtp:
                await smtp.starttls()
                await smtp.login(sender, password)
                await smtp.send_message(message)

            logger.info("Email notification sent successfully")
            return True
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            return False
