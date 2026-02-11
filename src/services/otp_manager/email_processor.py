"""Email processing for OTP extraction.

This module handles processing of email messages to extract OTP codes.
"""

import email
import email.utils
import logging
import re
from email.header import decode_header
from email.message import Message
from typing import Optional

from .models import OTPEntry, OTPSource
from .pattern_matcher import HTMLTextExtractor, OTPPatternMatcher

logger = logging.getLogger(__name__)


class EmailProcessor:
    """Process emails and extract OTP codes."""

    def __init__(self, pattern_matcher: OTPPatternMatcher):
        """
        Initialize email processor.

        Args:
            pattern_matcher: OTP pattern matcher instance
        """
        self._pattern_matcher = pattern_matcher

    def _decode_header_value(self, header_value: str) -> str:
        """Decode MIME-encoded email header."""
        if not header_value:
            return ""

        decoded_parts = []
        for part, encoding in decode_header(header_value):
            if isinstance(part, bytes):
                decoded_parts.append(part.decode(encoding or "utf-8", errors="ignore"))
            else:
                decoded_parts.append(part)

        return " ".join(decoded_parts)

    def _extract_target_email(self, msg: Message) -> Optional[str]:
        """
        Extract target email address from message headers.

        Checks "To", "Delivered-To", and "X-Original-To" headers.
        """
        for header in ["To", "Delivered-To", "X-Original-To"]:
            value = msg.get(header)
            if value:
                decoded = self._decode_header_value(value)
                match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", decoded)
                if match:
                    target = match.group(0).lower()
                    logger.debug(f"Target email found in {header}: {target}")
                    return target

        return None

    def _extract_text_from_html(self, html: str) -> str:
        """Extract plain text from HTML content."""
        extractor = HTMLTextExtractor()
        extractor.feed(html)
        return extractor.get_text()

    def _get_email_body(self, msg: Message) -> str:
        """Extract email body (plain text or HTML)."""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
                    except Exception as e:
                        logger.warning(f"Failed to decode plain text: {e}")

                elif content_type == "text/html" and not body:
                    try:
                        html = part.get_payload(decode=True).decode(errors="ignore")
                        body = self._extract_text_from_html(html)
                    except Exception as e:
                        logger.warning(f"Failed to decode HTML: {e}")
        else:
            try:
                body = msg.get_payload(decode=True).decode(errors="ignore")
                if msg.get_content_type() == "text/html":
                    body = self._extract_text_from_html(body)
            except Exception as e:
                logger.warning(f"Failed to decode message body: {e}")

        return body

    def process_email(self, msg: Message) -> Optional[OTPEntry]:
        """
        Process email message and extract OTP.

        Args:
            msg: Email message object

        Returns:
            OTPEntry if OTP found, None otherwise
        """
        # Extract target email
        target_email = self._extract_target_email(msg)
        if not target_email:
            return None

        # Extract subject and body
        subject = self._decode_header_value(msg.get("Subject", ""))
        body = self._get_email_body(msg)
        full_text = f"{subject} {body}"

        # Extract OTP
        otp_code = self._pattern_matcher.extract_otp(full_text)
        if not otp_code:
            return None

        # Get received date
        date_str = msg.get("Date", "")
        try:
            received_at = email.utils.parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            from datetime import datetime, timezone

            received_at = datetime.now(timezone.utc)

        return OTPEntry(
            code=otp_code,
            source=OTPSource.EMAIL,
            target_identifier=target_email,
            received_at=received_at,
            raw_data=full_text[:500],
        )
