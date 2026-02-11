"""SMS webhook handler for routing OTP codes.

This module handles incoming SMS webhooks and routes OTP codes to sessions.
"""

from typing import Optional

from loguru import logger

from .pattern_matcher import OTPPatternMatcher
from .session_registry import SessionRegistry


class SMSWebhookHandler:
    """Handle SMS OTP webhooks and route to sessions."""

    def __init__(self, session_registry: SessionRegistry, pattern_matcher: OTPPatternMatcher):
        """
        Initialize SMS webhook handler.

        Args:
            session_registry: Session registry instance
            pattern_matcher: OTP pattern matcher instance
        """
        self._session_registry = session_registry
        self._pattern_matcher = pattern_matcher

    def _mask_phone_number(self, phone_number: str) -> str:
        """
        Mask phone number for logging (show only last 3 digits).

        Args:
            phone_number: Phone number to mask

        Returns:
            Masked phone number
        """
        return f"***{phone_number[-3:]}" if len(phone_number) > 3 else "***"

    def process_sms(self, phone_number: str, message: str) -> Optional[str]:
        """
        Process incoming SMS and route OTP to session.

        Args:
            phone_number: Phone number
            message: SMS message text

        Returns:
            OTP code if extracted and delivered, None otherwise
        """
        otp_code = self._pattern_matcher.extract_otp(message)
        if not otp_code:
            masked = self._mask_phone_number(phone_number)
            logger.warning(f"No OTP found in SMS from {masked}")
            return None

        # Find session by phone number
        session = self._session_registry.find_by_phone(phone_number)
        if session:
            self._session_registry.notify_otp(session.session_id, otp_code)
            logger.info(f"SMS OTP delivered to session {session.session_id}")
            return otp_code

        masked = self._mask_phone_number(phone_number)
        logger.warning(f"No session found for phone {masked}")
        return None
