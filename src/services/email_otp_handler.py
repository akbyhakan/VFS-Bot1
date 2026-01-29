"""IMAP-based Email OTP Handler for Microsoft 365 catch-all email system.

This module provides thread-safe OTP handling for multiple bot sessions
that receive OTP codes via a catch-all email configuration.
"""

import imaplib
import email
import re
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Pattern
from dataclasses import dataclass
from email.header import decode_header
from html.parser import HTMLParser
import io

logger = logging.getLogger(__name__)


@dataclass
class EmailOTPEntry:
    """Represents a received OTP from email."""

    code: str
    target_email: str
    raw_subject: str
    raw_body: str
    received_at: datetime
    used: bool = False


@dataclass
class IMAPConfig:
    """IMAP server configuration."""

    host: str = "outlook.office365.com"
    port: int = 993
    use_ssl: bool = True
    folder: str = "INBOX"


class HTMLTextExtractor(HTMLParser):
    """Extract plain text from HTML content."""

    def __init__(self):
        super().__init__()
        self.text = []
        self.in_script = False
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'script':
            self.in_script = True
        elif tag.lower() == 'style':
            self.in_style = True

    def handle_endtag(self, tag):
        if tag.lower() == 'script':
            self.in_script = False
        elif tag.lower() == 'style':
            self.in_style = False

    def handle_data(self, data):
        if not self.in_script and not self.in_style:
            self.text.append(data)

    def get_text(self) -> str:
        return ' '.join(self.text)


class EmailOTPPatternMatcher:
    """Regex-based OTP code extractor from email messages."""

    # VFS Global and general OTP patterns - order matters (most specific first)
    DEFAULT_PATTERNS: List[str] = [
        r"VFS\s+Global.*?(\d{6})",  # VFS Global specific
        r"doğrulama\s+kodu[:\s]+(\d{6})",  # Turkish: verification code
        r"doğrulama[:\s]+(\d{6})",  # Turkish: verification
        r"tek\s+kullanımlık\s+şifre[:\s]+(\d{6})",  # Turkish: one-time password
        r"OTP[:\s]+(\d{6})",  # OTP: 123456
        r"kod[:\s]+(\d{6})",  # Turkish: code
        r"code[:\s]+(\d{6})",  # code: 123456
        r"verification\s+code[:\s]+(\d{6})",  # verification code: 123456
        r"authentication\s+code[:\s]+(\d{6})",  # authentication code: 123456
        r"\b(\d{6})\b",  # 6-digit code (fallback)
    ]

    def __init__(self, custom_patterns: Optional[List[str]] = None):
        """
        Initialize OTP pattern matcher.

        Args:
            custom_patterns: Optional list of custom regex patterns
        """
        patterns = custom_patterns or self.DEFAULT_PATTERNS
        self._patterns: List[Pattern] = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in patterns]

    def extract_otp(self, text: str) -> Optional[str]:
        """
        Extract OTP code from email text.

        Args:
            text: Email message text (plain or HTML)

        Returns:
            Extracted OTP code or None
        """
        if not text:
            return None

        for pattern in self._patterns:
            match = pattern.search(text)
            if match:
                otp = match.group(1)
                logger.debug(f"OTP extracted: {otp[:2]}****")
                return otp

        logger.warning(f"No OTP found in message: {text[:100]}...")
        return None


class EmailOTPHandler:
    """
    Thread-safe IMAP-based email OTP handler for Microsoft 365 catch-all system.

    This handler supports multiple concurrent bot sessions, each waiting for OTP
    codes sent to different target email addresses that are all received in a
    single catch-all mailbox.

    Example:
        handler = EmailOTPHandler(
            email="akby.hakan@vizecep.com",
            app_password="xxxx-xxxx-xxxx-xxxx"
        )
        otp = handler.wait_for_otp("bot55@vizecep.com", timeout=120)
    """

    def __init__(
        self,
        email: str,
        app_password: str,
        imap_config: Optional[IMAPConfig] = None,
        otp_timeout_seconds: int = 120,
        poll_interval_seconds: int = 5,
        max_email_age_seconds: int = 300,
        custom_patterns: Optional[List[str]] = None,
    ):
        """
        Initialize Email OTP Handler.

        Args:
            email: Microsoft 365 email address (catch-all mailbox)
            app_password: Microsoft 365 App Password
            imap_config: IMAP configuration (default: outlook.office365.com:993)
            otp_timeout_seconds: Maximum wait time for OTP (default: 120)
            poll_interval_seconds: Interval between email checks (default: 5)
            max_email_age_seconds: Maximum age of emails to consider (default: 300)
            custom_patterns: Optional custom regex patterns for OTP extraction
        """
        self._email = email
        self._app_password = app_password
        self._imap_config = imap_config or IMAPConfig()
        self._otp_timeout = otp_timeout_seconds
        self._poll_interval = poll_interval_seconds
        self._max_email_age = max_email_age_seconds
        self._pattern_matcher = EmailOTPPatternMatcher(custom_patterns)

        # Thread-safe cache for OTP entries
        self._otp_cache: Dict[str, EmailOTPEntry] = {}
        self._lock = threading.RLock()

        logger.info(
            f"EmailOTPHandler initialized for {email} "
            f"(timeout: {otp_timeout_seconds}s, poll: {poll_interval_seconds}s)"
        )

    def _connect_imap(self) -> imaplib.IMAP4_SSL:
        """
        Create and authenticate IMAP connection.

        Returns:
            Authenticated IMAP connection

        Raises:
            imaplib.IMAP4.error: If connection or authentication fails
        """
        try:
            mail = imaplib.IMAP4_SSL(self._imap_config.host, self._imap_config.port)
            mail.login(self._email, self._app_password)
            mail.select(self._imap_config.folder)
            logger.debug(f"IMAP connection established to {self._imap_config.host}")
            return mail
        except Exception as e:
            logger.error(f"IMAP connection failed: {e}")
            raise

    def _decode_header_value(self, header_value: str) -> str:
        """
        Decode MIME-encoded email header.

        Args:
            header_value: Raw header value

        Returns:
            Decoded header string
        """
        if not header_value:
            return ""

        decoded_parts = []
        for part, encoding in decode_header(header_value):
            if isinstance(part, bytes):
                decoded_parts.append(part.decode(encoding or 'utf-8', errors='ignore'))
            else:
                decoded_parts.append(part)

        return ' '.join(decoded_parts)

    def _extract_target_email(self, msg: email.message.Message) -> Optional[str]:
        """
        Extract target email address from message headers.

        Checks "To", "Delivered-To", and "X-Original-To" headers to find
        the actual recipient in catch-all configuration.

        Args:
            msg: Email message object

        Returns:
            Target email address or None
        """
        # Check multiple headers for target email
        for header in ["To", "Delivered-To", "X-Original-To"]:
            value = msg.get(header)
            if value:
                decoded = self._decode_header_value(value)
                # Extract email address from "Name <email@domain.com>" format
                match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', decoded)
                if match:
                    target = match.group(0).lower()
                    logger.debug(f"Target email found in {header}: {target}")
                    return target

        return None

    def _extract_text_from_html(self, html: str) -> str:
        """
        Extract plain text from HTML content.

        Args:
            html: HTML content

        Returns:
            Plain text
        """
        extractor = HTMLTextExtractor()
        extractor.feed(html)
        return extractor.get_text()

    def _get_email_body(self, msg: email.message.Message) -> str:
        """
        Extract email body (plain text or HTML).

        Args:
            msg: Email message object

        Returns:
            Email body text
        """
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                # Skip attachments
                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode(errors='ignore')
                        break
                    except Exception as e:
                        logger.warning(f"Failed to decode plain text: {e}")

                elif content_type == "text/html" and not body:
                    try:
                        html = part.get_payload(decode=True).decode(errors='ignore')
                        body = self._extract_text_from_html(html)
                    except Exception as e:
                        logger.warning(f"Failed to decode HTML: {e}")
        else:
            try:
                body = msg.get_payload(decode=True).decode(errors='ignore')
                if msg.get_content_type() == "text/html":
                    body = self._extract_text_from_html(body)
            except Exception as e:
                logger.warning(f"Failed to decode message body: {e}")

        return body

    def _fetch_and_process_emails(self, target_email: str, since_time: datetime) -> Optional[str]:
        """
        Fetch and process emails to find OTP for target email.

        Args:
            target_email: Target email address to filter
            since_time: Only process emails received after this time

        Returns:
            OTP code if found, None otherwise
        """
        try:
            mail = self._connect_imap()

            # Search for recent unread emails
            since_date = since_time.strftime("%d-%b-%Y")
            _, message_numbers = mail.search(None, f'(UNSEEN SINCE {since_date})')

            if not message_numbers[0]:
                logger.debug("No new emails found")
                mail.close()
                mail.logout()
                return None

            for num in message_numbers[0].split():
                try:
                    _, msg_data = mail.fetch(num, '(RFC822)')
                    email_body = msg_data[0][1]
                    msg = email.message_from_bytes(email_body)

                    # Extract target email from headers
                    msg_target = self._extract_target_email(msg)
                    if not msg_target or msg_target.lower() != target_email.lower():
                        continue

                    # Extract subject and body
                    subject = self._decode_header_value(msg.get("Subject", ""))
                    body = self._get_email_body(msg)
                    full_text = f"{subject} {body}"

                    # Extract OTP
                    otp = self._pattern_matcher.extract_otp(full_text)
                    if otp:
                        # Get received date
                        date_str = msg.get("Date", "")
                        try:
                            received_at = email.utils.parsedate_to_datetime(date_str)
                        except:
                            received_at = datetime.now(timezone.utc)

                        # Cache the OTP
                        with self._lock:
                            entry = EmailOTPEntry(
                                code=otp,
                                target_email=target_email,
                                raw_subject=subject,
                                raw_body=body,
                                received_at=received_at,
                            )
                            self._otp_cache[target_email] = entry

                        logger.info(f"OTP found for {target_email}: {otp[:2]}****")
                        mail.close()
                        mail.logout()
                        return otp

                except Exception as e:
                    logger.warning(f"Error processing email: {e}")
                    continue

            mail.close()
            mail.logout()
            return None

        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return None

    def wait_for_otp(
        self,
        target_email: str,
        timeout: Optional[int] = None,
        mark_used: bool = True
    ) -> Optional[str]:
        """
        Wait for OTP code for specific target email.

        This method polls the IMAP server for new emails containing OTP codes
        sent to the specified target email address.

        Args:
            target_email: Target email address (e.g., "bot55@vizecep.com")
            timeout: Maximum wait time in seconds (default: otp_timeout_seconds)
            mark_used: Whether to mark OTP as used after retrieval (default: True)

        Returns:
            OTP code or None if timeout
        """
        timeout = timeout or self._otp_timeout
        target_email = target_email.lower()

        # Check cache first
        cached_otp = self.get_cached_otp(target_email)
        if cached_otp:
            if mark_used:
                with self._lock:
                    if target_email in self._otp_cache:
                        self._otp_cache[target_email].used = True
            return cached_otp

        # Poll for new emails
        start_time = time.time()
        since_time = datetime.now(timezone.utc) - timedelta(seconds=self._max_email_age)

        while time.time() - start_time < timeout:
            otp = self._fetch_and_process_emails(target_email, since_time)
            if otp:
                if mark_used:
                    with self._lock:
                        if target_email in self._otp_cache:
                            self._otp_cache[target_email].used = True
                return otp

            # Wait before next poll
            remaining = timeout - (time.time() - start_time)
            if remaining > 0:
                time.sleep(min(self._poll_interval, remaining))

        logger.warning(f"OTP timeout for {target_email} after {timeout}s")
        return None

    def get_cached_otp(self, target_email: str) -> Optional[str]:
        """
        Get cached OTP for target email without marking as used.

        Args:
            target_email: Target email address

        Returns:
            OTP code or None
        """
        target_email = target_email.lower()

        with self._lock:
            entry = self._otp_cache.get(target_email)
            if not entry or entry.used:
                return None

            # Check if OTP is still valid
            age = (datetime.now(timezone.utc) - entry.received_at).total_seconds()
            if age > self._max_email_age:
                logger.debug(f"Cached OTP for {target_email} expired")
                return None

            return entry.code

    def clear_cache(self, target_email: Optional[str] = None):
        """
        Clear OTP cache.

        Args:
            target_email: Specific email to clear, or None to clear all
        """
        with self._lock:
            if target_email:
                target_email = target_email.lower()
                self._otp_cache.pop(target_email, None)
                logger.debug(f"Cache cleared for {target_email}")
            else:
                self._otp_cache.clear()
                logger.debug("All OTP cache cleared")

    def close(self):
        """Clean up resources."""
        self.clear_cache()
        logger.info("EmailOTPHandler closed")


# Global instance with thread-safe initialization
_email_otp_handler: Optional[EmailOTPHandler] = None
_handler_lock = threading.Lock()


def get_email_otp_handler(
    email: Optional[str] = None,
    app_password: Optional[str] = None,
    **kwargs
) -> EmailOTPHandler:
    """
    Get global EmailOTPHandler instance (thread-safe singleton).

    Args:
        email: Email address (required on first call)
        app_password: App password (required on first call)
        **kwargs: Additional configuration options

    Returns:
        Global EmailOTPHandler instance

    Raises:
        ValueError: If email/password not provided on first initialization
    """
    global _email_otp_handler

    # First check without lock (fast path)
    if _email_otp_handler is not None:
        return _email_otp_handler

    # Acquire lock for initialization
    with _handler_lock:
        # Double-check after acquiring lock
        if _email_otp_handler is None:
            if not email or not app_password:
                raise ValueError("Email and app_password required for first initialization")

            _email_otp_handler = EmailOTPHandler(email, app_password, **kwargs)
            logger.info("Global EmailOTPHandler initialized")

        return _email_otp_handler
