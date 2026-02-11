"""SMS OTP Webhook receiver for VFS authentication."""

import asyncio
import re
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Pattern

from loguru import logger


@dataclass
class OTPEntry:
    """Represents a received OTP."""

    code: str
    phone_number: str
    raw_message: str
    received_at: datetime
    used: bool = False


class OTPType(Enum):
    """OTP type enumeration."""

    APPOINTMENT = "appointment"
    PAYMENT = "payment"


class OTPPatternMatcher:
    """Regex-based OTP code extractor from SMS messages."""

    # Common OTP patterns - order matters (most specific first)
    DEFAULT_PATTERNS: List[str] = [
        # --- Keyword-based patterns (most specific, checked first) ---
        r"(?:verification|doğrulama)\s*(?:code|kodu?)?[:\s]+(\d{4,6})",
        r"(?:OTP|one.time)\s*(?:code|password)?[:\s]+(\d{4,6})",
        r"(?:code|kod|şifre)[:\s]+(\d{4,6})",
        r"VFS[^0-9]{0,20}(\d{4,6})",  # VFS-specific context
        # --- Bare digit fallbacks (least specific, checked last) ---
        r"\b(\d{6})\b",  # 6-digit code
        r"\b(\d{5})\b",  # 5-digit code
        # NOTE: 4-digit bare pattern removed — too many false positives
        # (years, PINs, prices). Use keyword patterns above for 4-digit OTPs.
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
        self._queues: Dict[OTPType, deque] = {
            OTPType.APPOINTMENT: deque(maxlen=max_entries),
            OTPType.PAYMENT: deque(maxlen=max_entries),
        }
        # Keep backward compatibility aliases
        self._appointment_otp_queue = self._queues[OTPType.APPOINTMENT]
        self._payment_otp_queue = self._queues[OTPType.PAYMENT]

        self._otp_timeout = otp_timeout_seconds
        self._pattern_matcher = OTPPatternMatcher(custom_patterns)
        self._waiting_events: Dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

        logger.info(
            f"OTPWebhookService initialized with dual queues (timeout: {otp_timeout_seconds}s)"
        )

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

    async def _process_sms_generic(
        self, otp_type: OTPType, phone_number: str, message: str
    ) -> Optional[str]:
        """
        Generic SMS processing - DRY implementation.

        Args:
            otp_type: Type of OTP (APPOINTMENT or PAYMENT)
            phone_number: Sender phone number
            message: SMS message text

        Returns:
            Extracted OTP code or None
        """
        otp_code = self._pattern_matcher.extract_otp(message)

        if not otp_code:
            logger.warning(f"No OTP found in {otp_type.value} SMS from {phone_number[:4]}***")
            return None

        entry = OTPEntry(
            code=otp_code,
            phone_number=phone_number,
            raw_message=message,
            received_at=datetime.now(timezone.utc),
        )

        queue = self._queues[otp_type]
        event_prefix = f"{otp_type.value}_"

        async with self._lock:
            queue.append(entry)

            # Notify waiting consumers - MUST BE INSIDE LOCK to prevent race condition
            for key, event in self._waiting_events.items():
                if key.startswith(event_prefix):
                    event.set()

        logger.info(
            f"{otp_type.value.capitalize()} OTP received from "
            f"{phone_number[:4]}***: {otp_code[:2]}****"
        )
        return otp_code

    async def process_appointment_sms(self, phone_number: str, message: str) -> Optional[str]:
        """
        Process incoming appointment SMS and extract OTP.

        Args:
            phone_number: Sender phone number
            message: SMS message text

        Returns:
            Extracted OTP code or None
        """
        return await self._process_sms_generic(OTPType.APPOINTMENT, phone_number, message)

    async def process_payment_sms(self, phone_number: str, message: str) -> Optional[str]:
        """
        Process incoming payment SMS and extract OTP.

        Args:
            phone_number: Sender phone number
            message: SMS message text

        Returns:
            Extracted OTP code or None
        """
        return await self._process_sms_generic(OTPType.PAYMENT, phone_number, message)

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

    async def _wait_for_otp_generic(
        self,
        queue: deque,
        queue_type: str,
        phone_number: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Optional[str]:
        """
        Generic OTP wait method.

        Args:
            queue: OTP queue to check
            queue_type: 'appointment' or 'payment'
            phone_number: Optional phone number filter
            timeout: Maximum wait time in seconds

        Returns:
            OTP code or None if timeout
        """
        timeout = timeout or self._otp_timeout
        wait_key = f"{queue_type}_{phone_number or 'any'}"

        # Create event and add to waiting events inside lock to prevent race condition
        async with self._lock:
            event = asyncio.Event()
            self._waiting_events[wait_key] = event

        # Safety limit: maximum iteration count
        max_iterations = (timeout // 5) + 10  # 5-second loops + safety margin
        iteration = 0

        try:
            start_time = datetime.now(timezone.utc)

            while iteration < max_iterations:
                iteration += 1

                # Check existing OTPs
                otp = await self._get_latest_otp_from_queue(queue, phone_number)
                if otp:
                    return otp

                # Calculate remaining time
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                remaining = timeout - elapsed

                if remaining <= 0:
                    logger.warning(f"{queue_type.capitalize()} OTP wait timeout after {timeout}s")
                    return None

                # Wait for new OTP or timeout
                try:
                    await asyncio.wait_for(event.wait(), timeout=min(remaining, 5.0))
                    event.clear()
                except asyncio.TimeoutError:
                    continue

            # Max iterations reached
            logger.error(
                f"{queue_type.capitalize()} OTP wait exceeded max iterations ({max_iterations})"
            )
            return None

        finally:
            self._waiting_events.pop(wait_key, None)

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
        return await self._wait_for_otp_generic(
            self._appointment_otp_queue, "appointment", phone_number, timeout
        )

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
        return await self._wait_for_otp_generic(
            self._payment_otp_queue, "payment", phone_number, timeout
        )

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
        Uses in-place modification to preserve queue references.

        Returns:
            Number of entries removed
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            total_removed = 0

            for otp_type in OTPType:
                queue = self._queues[otp_type]
                initial_count = len(queue)

                # Find expired entries
                # Use list() to create a copy for safe iteration
                expired_entries = [
                    entry
                    for entry in list(queue)
                    if (now - entry.received_at).total_seconds() > self._otp_timeout
                ]

                # Remove expired entries in-place
                for entry in expired_entries:
                    try:
                        queue.remove(entry)
                    except ValueError as e:
                        logger.debug(f"Failed to remove entry from queue (not found): {e}")

                removed = initial_count - len(queue)
                total_removed += removed

                if removed > 0:
                    logger.debug(f"Cleaned up {removed} expired {otp_type.value} OTPs")

            if total_removed > 0:
                logger.info(f"Total expired OTPs cleaned: {total_removed}")

            return total_removed

    async def wait_for_otp_with_fallback(
        self,
        phone_number: Optional[str] = None,
        timeout: Optional[int] = None,
        fallback_callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """
        Wait for OTP with graceful degradation.

        If OTP service fails or times out, calls fallback_callback
        for manual OTP input.

        Args:
            phone_number: Optional phone number filter
            timeout: Maximum wait time in seconds
            fallback_callback: Async function to call for manual input

        Returns:
            OTP code or None
        """
        try:
            otp = await self.wait_for_appointment_otp(phone_number, timeout)
            if otp:
                return otp
        except Exception as e:
            logger.warning(f"OTP service error: {e}, switching to fallback")

        # Fallback to manual input if provided
        if fallback_callback:
            logger.info("Requesting manual OTP input")
            try:
                result: Optional[str] = await fallback_callback()
                return result
            except Exception as e:
                logger.error(f"Fallback OTP input failed: {e}")

        return None

    def health_check(self) -> Dict[str, Any]:
        """
        Return OTP service health status.

        Note: Queue size readings are not locked as they are atomic operations
        and provide a snapshot of the current state.

        Returns:
            Dictionary with service health metrics
        """
        appointment_queue_size = len(self._appointment_otp_queue)
        payment_queue_size = len(self._payment_otp_queue)
        waiting_consumers = len(self._waiting_events)
        max_entries = self._appointment_otp_queue.maxlen

        return {
            "status": "healthy",
            "appointment_queue_size": appointment_queue_size,
            "payment_queue_size": payment_queue_size,
            "timeout_seconds": self._otp_timeout,
            "waiting_consumers": waiting_consumers,
            "max_entries": max_entries,
        }

    async def start_cleanup_scheduler(self, interval_seconds: int = 60) -> None:
        """
        Start background task for periodic OTP cleanup.

        Args:
            interval_seconds: Cleanup interval in seconds (default: 60)
        """
        self._cleanup_task = asyncio.create_task(self._cleanup_loop(interval_seconds))
        logger.info(f"OTP cleanup scheduler started (interval: {interval_seconds}s)")

    async def stop_cleanup_scheduler(self) -> None:
        """Stop the cleanup scheduler."""
        if hasattr(self, "_cleanup_task") and self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("OTP cleanup scheduler stopped")

    async def _cleanup_loop(self, interval: int) -> None:
        """
        Background loop for periodic cleanup.

        Args:
            interval: Cleanup interval in seconds
        """
        while True:
            try:
                await asyncio.sleep(interval)
                removed = await self.cleanup_expired()
                if removed > 0:
                    logger.debug(f"Periodic cleanup removed {removed} expired OTPs")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in OTP cleanup loop: {e}")


# Global instance with thread-safe initialization
_otp_service: Optional[OTPWebhookService] = None
_otp_lock = threading.Lock()


def get_otp_service() -> OTPWebhookService:
    """
    Get global OTP service instance (thread-safe singleton).

    Uses double-checked locking pattern for efficiency.
    """
    global _otp_service

    # First check without lock (fast path)
    if _otp_service is not None:
        return _otp_service

    # Acquire lock for initialization
    with _otp_lock:
        # Double-check after acquiring lock
        if _otp_service is None:
            _otp_service = OTPWebhookService()
            logger.info("OTP service singleton initialized")

        return _otp_service
