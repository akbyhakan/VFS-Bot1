"""SMS OTP Webhook receiver for VFS authentication."""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, List, Pattern
from collections import deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OTPEntry:
    """Represents a received OTP."""

    code: str
    phone_number: str
    raw_message: str
    received_at: datetime
    used: bool = False


class OTPPatternMatcher:
    """Regex-based OTP code extractor from SMS messages."""

    # Common OTP patterns - order matters (most specific first)
    DEFAULT_PATTERNS: List[str] = [
        r"\b(\d{6})\b",  # 6-digit code (most common)
        r"\b(\d{5})\b",  # 5-digit code
        r"\b(\d{4})\b",  # 4-digit code
        r"code[:\s]+(\d{4,6})",  # "code: 123456" or "code 123456"
        r"OTP[:\s]+(\d{4,6})",  # "OTP: 123456"
        r"verification[:\s]+(\d{4,6})",  # "verification: 123456"
        r"doğrulama[:\s]+(\d{4,6})",  # Turkish: "doğrulama: 123456"
        r"kod[:\s]+(\d{4,6})",  # Turkish: "kod: 123456"
    ]

    def __init__(self, custom_patterns: Optional[List[str]] = None):
        """
        Initialize OTP pattern matcher.

        Args:
            custom_patterns: Optional list of custom regex patterns
        """
        patterns = custom_patterns or self.DEFAULT_PATTERNS
        self._patterns: List[Pattern] = [re.compile(p, re.IGNORECASE) for p in patterns]

    def extract_otp(self, message: str) -> Optional[str]:
        """
        Extract OTP code from SMS message.

        Args:
            message: Raw SMS message text

        Returns:
            Extracted OTP code or None
        """
        if not message:
            return None

        for pattern in self._patterns:
            match = pattern.search(message)
            if match:
                otp = match.group(1)
                logger.debug(f"OTP extracted: {otp[:2]}****")
                return otp

        logger.warning(f"No OTP found in message: {message[:50]}...")
        return None


class OTPWebhookService:
    """
    Service to receive and manage OTP codes via webhook.

    Usage:
        1. Configure webhook endpoint in your SMS provider
        2. SMS provider sends POST to /api/webhook/sms
        3. This service extracts and stores OTP
        4. Bot retrieves OTP when needed for VFS authentication
    """

    def __init__(
        self,
        max_entries: int = 100,
        otp_timeout_seconds: int = 300,
        custom_patterns: Optional[List[str]] = None,
    ):
        """
        Initialize OTP webhook service.

        Args:
            max_entries: Maximum OTP entries to keep in memory
            otp_timeout_seconds: OTP validity period in seconds
            custom_patterns: Optional custom regex patterns for OTP extraction
        """
        # Separate queues for appointment and payment OTPs
        self._appointment_otp_queue: deque[OTPEntry] = deque(maxlen=max_entries)
        self._payment_otp_queue: deque[OTPEntry] = deque(maxlen=max_entries)
        self._otp_timeout = otp_timeout_seconds
        self._pattern_matcher = OTPPatternMatcher(custom_patterns)
        self._waiting_events: Dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

        logger.info(f"OTPWebhookService initialized with dual queues (timeout: {otp_timeout_seconds}s)")

    async def process_sms(self, phone_number: str, message: str) -> Optional[str]:
        """
        Process incoming SMS and extract OTP (legacy method for backward compatibility).
        Routes to appointment queue by default.

        Args:
            phone_number: Sender phone number
            message: SMS message text

        Returns:
            Extracted OTP code or None
        """
        return await self.process_appointment_sms(phone_number, message)

    async def process_appointment_sms(self, phone_number: str, message: str) -> Optional[str]:
        """
        Process incoming appointment SMS and extract OTP.

        Args:
            phone_number: Sender phone number
            message: SMS message text

        Returns:
            Extracted OTP code or None
        """
        otp_code = self._pattern_matcher.extract_otp(message)

        if not otp_code:
            logger.warning(f"No OTP found in appointment SMS from {phone_number[:4]}***")
            return None

        entry = OTPEntry(
            code=otp_code,
            phone_number=phone_number,
            raw_message=message,
            received_at=datetime.now(timezone.utc),
        )

        async with self._lock:
            self._appointment_otp_queue.append(entry)

            # Notify waiting consumers
            for key, event in self._waiting_events.items():
                if key.startswith("appointment_"):
                    event.set()

        logger.info(f"Appointment OTP received from {phone_number[:4]}***: {otp_code[:2]}****")
        return otp_code

    async def process_payment_sms(self, phone_number: str, message: str) -> Optional[str]:
        """
        Process incoming payment SMS and extract OTP.

        Args:
            phone_number: Sender phone number
            message: SMS message text

        Returns:
            Extracted OTP code or None
        """
        otp_code = self._pattern_matcher.extract_otp(message)

        if not otp_code:
            logger.warning(f"No OTP found in payment SMS from {phone_number[:4]}***")
            return None

        entry = OTPEntry(
            code=otp_code,
            phone_number=phone_number,
            raw_message=message,
            received_at=datetime.now(timezone.utc),
        )

        async with self._lock:
            self._payment_otp_queue.append(entry)

            # Notify waiting consumers
            for key, event in self._waiting_events.items():
                if key.startswith("payment_"):
                    event.set()

        logger.info(f"Payment OTP received from {phone_number[:4]}***: {otp_code[:2]}****")
        return otp_code

    async def wait_for_otp(
        self, phone_number: Optional[str] = None, timeout: Optional[int] = None
    ) -> Optional[str]:
        """
        Wait for OTP code to arrive (legacy method for backward compatibility).
        Routes to appointment queue by default.

        Args:
            phone_number: Optional phone number filter
            timeout: Maximum wait time in seconds (default: otp_timeout_seconds)

        Returns:
            OTP code or None if timeout
        """
        return await self.wait_for_appointment_otp(phone_number, timeout)

    async def wait_for_appointment_otp(
        self, phone_number: Optional[str] = None, timeout: Optional[int] = None
    ) -> Optional[str]:
        """
        Wait for appointment OTP code to arrive.

        Args:
            phone_number: Optional phone number filter
            timeout: Maximum wait time in seconds (default: otp_timeout_seconds)

        Returns:
            OTP code or None if timeout
        """
        timeout = timeout or self._otp_timeout
        wait_key = f"appointment_{phone_number or 'any'}"

        event = asyncio.Event()
        self._waiting_events[wait_key] = event

        try:
            start_time = datetime.now(timezone.utc)

            while True:
                # Check existing OTPs
                otp = await self._get_latest_otp_from_queue(
                    self._appointment_otp_queue, phone_number
                )
                if otp:
                    return otp

                # Calculate remaining time
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                remaining = timeout - elapsed

                if remaining <= 0:
                    logger.warning(f"Appointment OTP wait timeout after {timeout}s")
                    return None

                # Wait for new OTP or timeout
                try:
                    await asyncio.wait_for(event.wait(), timeout=min(remaining, 5.0))
                    event.clear()
                except asyncio.TimeoutError:
                    continue

        finally:
            self._waiting_events.pop(wait_key, None)

    async def wait_for_payment_otp(
        self, phone_number: Optional[str] = None, timeout: Optional[int] = None
    ) -> Optional[str]:
        """
        Wait for payment OTP code to arrive.

        Args:
            phone_number: Optional phone number filter
            timeout: Maximum wait time in seconds (default: otp_timeout_seconds)

        Returns:
            OTP code or None if timeout
        """
        timeout = timeout or self._otp_timeout
        wait_key = f"payment_{phone_number or 'any'}"

        event = asyncio.Event()
        self._waiting_events[wait_key] = event

        try:
            start_time = datetime.now(timezone.utc)

            while True:
                # Check existing OTPs
                otp = await self._get_latest_otp_from_queue(self._payment_otp_queue, phone_number)
                if otp:
                    return otp

                # Calculate remaining time
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                remaining = timeout - elapsed

                if remaining <= 0:
                    logger.warning(f"Payment OTP wait timeout after {timeout}s")
                    return None

                # Wait for new OTP or timeout
                try:
                    await asyncio.wait_for(event.wait(), timeout=min(remaining, 5.0))
                    event.clear()
                except asyncio.TimeoutError:
                    continue

        finally:
            self._waiting_events.pop(wait_key, None)

    async def _get_latest_otp(self, phone_number: Optional[str] = None) -> Optional[str]:
        """
        Get the latest unused OTP code from appointment queue (legacy).

        Args:
            phone_number: Optional phone number filter

        Returns:
            OTP code or None
        """
        return await self._get_latest_otp_from_queue(self._appointment_otp_queue, phone_number)

    async def _get_latest_otp_from_queue(
        self, queue: deque[OTPEntry], phone_number: Optional[str] = None
    ) -> Optional[str]:
        """
        Get the latest unused OTP code from specified queue.

        Args:
            queue: OTP queue to search
            phone_number: Optional phone number filter

        Returns:
            OTP code or None
        """
        async with self._lock:
            now = datetime.now(timezone.utc)

            for entry in reversed(queue):
                # Skip used entries
                if entry.used:
                    continue

                # Check timeout
                age = (now - entry.received_at).total_seconds()
                if age > self._otp_timeout:
                    continue

                # Check phone number filter
                if phone_number and entry.phone_number != phone_number:
                    continue

                # Mark as used and return
                entry.used = True
                logger.info(f"OTP consumed: {entry.code[:2]}****")
                return entry.code

            return None

    async def cleanup_expired(self) -> int:
        """
        Remove expired OTP entries from both queues.

        Returns:
            Number of entries removed
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            
            # Clean appointment queue
            initial_appt_count = len(self._appointment_otp_queue)
            self._appointment_otp_queue = deque(
                (
                    entry
                    for entry in self._appointment_otp_queue
                    if (now - entry.received_at).total_seconds() <= self._otp_timeout
                ),
                maxlen=self._appointment_otp_queue.maxlen,
            )
            appt_removed = initial_appt_count - len(self._appointment_otp_queue)
            
            # Clean payment queue
            initial_pay_count = len(self._payment_otp_queue)
            self._payment_otp_queue = deque(
                (
                    entry
                    for entry in self._payment_otp_queue
                    if (now - entry.received_at).total_seconds() <= self._otp_timeout
                ),
                maxlen=self._payment_otp_queue.maxlen,
            )
            pay_removed = initial_pay_count - len(self._payment_otp_queue)

            total_removed = appt_removed + pay_removed
            if total_removed > 0:
                logger.debug(
                    f"Cleaned up {total_removed} expired OTP entries "
                    f"(appointment: {appt_removed}, payment: {pay_removed})"
                )
            return total_removed


# Global instance
_otp_service: Optional[OTPWebhookService] = None


def get_otp_service() -> OTPWebhookService:
    """Get global OTP service instance."""
    global _otp_service
    if _otp_service is None:
        _otp_service = OTPWebhookService()
    return _otp_service
