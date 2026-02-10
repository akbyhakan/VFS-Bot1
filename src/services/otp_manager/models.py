"""Data models for OTP Manager.

This module contains all data classes and enums used by the OTP Manager system.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class OTPSource(Enum):
    """OTP source enumeration."""

    EMAIL = "email"
    SMS = "sms"
    MANUAL = "manual"


class SessionState(Enum):
    """Bot session state enumeration."""

    ACTIVE = "active"
    WAITING_OTP = "waiting_otp"
    OTP_RECEIVED = "otp_received"
    EXPIRED = "expired"


@dataclass
class OTPEntry:
    """
    Represents a received OTP code.

    Attributes:
        code: The extracted OTP code (e.g., "123456")
        source: Source of the OTP (EMAIL, SMS, or MANUAL)
        target_identifier: Email address or phone number that received the OTP
        received_at: Timestamp when OTP was received
        raw_data: Raw message content (truncated for storage)
        used: Whether the OTP has been consumed
    """

    code: str
    source: OTPSource
    target_identifier: str
    received_at: datetime
    raw_data: str = ""
    used: bool = False


@dataclass
class BotSession:
    """
    Represents a bot session waiting for OTP.

    Attributes:
        session_id: Unique session identifier (UUID)
        target_email: Optional email address for email OTP delivery
        phone_number: Optional phone number for SMS OTP delivery
        country: Optional country code for the session
        metadata: Additional metadata for the session
        state: Current session state (ACTIVE, WAITING_OTP, OTP_RECEIVED, EXPIRED)
        created_at: Session creation timestamp
        otp_event: Threading event for OTP notification (auto-initialized)
        otp_code: Received OTP code (None until received)
    """

    session_id: str
    target_email: Optional[str] = None
    phone_number: Optional[str] = None
    country: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    state: SessionState = SessionState.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    otp_event: Optional[threading.Event] = field(default=None, init=False)
    otp_code: Optional[str] = None

    def __post_init__(self):
        """Initialize event after dataclass creation."""
        if self.otp_event is None:
            self.otp_event = threading.Event()


@dataclass
class IMAPConfig:
    """
    IMAP server configuration.

    Attributes:
        host: IMAP server hostname (default: outlook.office365.com)
        port: IMAP server port (default: 993 for SSL)
        use_ssl: Whether to use SSL/TLS connection (default: True)
        folder: IMAP folder to monitor (default: INBOX)
    """

    host: str = "outlook.office365.com"
    port: int = 993
    use_ssl: bool = True
    folder: str = "INBOX"
