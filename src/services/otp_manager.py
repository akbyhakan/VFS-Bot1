"""Centralized OTP Manager for VFS automation.

This module provides a unified OTP management system that handles OTP codes
from both email (catch-all mailbox) and SMS sources for 100+ concurrent bot sessions.
"""

import email
import email.utils
import imaplib
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from enum import Enum
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Pattern

logger = logging.getLogger(__name__)


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


class HTMLTextExtractor(HTMLParser):
    """Extract plain text from HTML content."""

    def __init__(self):
        super().__init__()
        self.text = []
        self.in_script = False
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            self.in_script = True
        elif tag.lower() == "style":
            self.in_style = True

    def handle_endtag(self, tag):
        if tag.lower() == "script":
            self.in_script = False
        elif tag.lower() == "style":
            self.in_style = False

    def handle_data(self, data):
        if not self.in_script and not self.in_style:
            self.text.append(data)

    def get_text(self) -> str:
        return " ".join(self.text)


class OTPPatternMatcher:
    """Regex-based OTP code extractor."""

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
        Extract OTP code from text.

        Args:
            text: Text to search for OTP

        Returns:
            Extracted OTP code or None
        """
        if not text:
            return None

        for pattern in self._patterns:
            match = pattern.search(text)
            if match:
                otp = match.group(1)
                logger.debug("OTP code successfully extracted")
                return otp

        logger.warning(f"No OTP found in text: {text[:100]}...")
        return None


class SessionRegistry:
    """Thread-safe session registry for managing bot sessions."""

    def __init__(self, session_timeout_seconds: int = 600):
        """
        Initialize session registry.

        Args:
            session_timeout_seconds: Auto-expire sessions after this time
        """
        self._sessions: Dict[str, BotSession] = {}
        self._email_to_session: Dict[str, str] = {}  # target_email -> session_id
        self._phone_to_session: Dict[str, str] = {}  # phone_number -> session_id
        self._lock = threading.RLock()
        self._session_timeout = session_timeout_seconds

    def register(
        self,
        target_email: Optional[str] = None,
        phone_number: Optional[str] = None,
        country: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Register a new bot session.

        Args:
            target_email: Target email address
            phone_number: Phone number
            country: Country code
            metadata: Additional metadata

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())

        session = BotSession(
            session_id=session_id,
            target_email=target_email.lower() if target_email else None,
            phone_number=phone_number,
            country=country,
            metadata=metadata or {},
        )

        with self._lock:
            self._sessions[session_id] = session
            if target_email:
                self._email_to_session[target_email.lower()] = session_id
            if phone_number:
                self._phone_to_session[phone_number] = session_id

        logger.info(
            f"Session registered: {session_id} (email={target_email}, phone={phone_number})"
        )
        return session_id

    def unregister(self, session_id: str) -> bool:
        """
        Unregister a session.

        Args:
            session_id: Session ID to unregister

        Returns:
            True if session was found and removed
        """
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if not session:
                return False

            # Clean up mappings
            if session.target_email:
                self._email_to_session.pop(session.target_email, None)
            if session.phone_number:
                self._phone_to_session.pop(session.phone_number, None)

        logger.info(f"Session unregistered: {session_id}")
        return True

    def get_session(self, session_id: str) -> Optional[BotSession]:
        """Get session by ID."""
        with self._lock:
            return self._sessions.get(session_id)

    def find_by_email(self, email: str) -> Optional[BotSession]:
        """Find session by target email."""
        email = email.lower()
        with self._lock:
            session_id = self._email_to_session.get(email)
            if session_id:
                return self._sessions.get(session_id)
        return None

    def find_by_phone(self, phone: str) -> Optional[BotSession]:
        """Find session by phone number."""
        with self._lock:
            session_id = self._phone_to_session.get(phone)
            if session_id:
                return self._sessions.get(session_id)
        return None

    def notify_otp(self, session_id: str, otp_code: str) -> bool:
        """
        Notify session about received OTP.

        Args:
            session_id: Session ID
            otp_code: OTP code

        Returns:
            True if session was found and notified
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            session.otp_code = otp_code
            session.state = SessionState.OTP_RECEIVED
            if session.otp_event:
                session.otp_event.set()

        logger.debug(f"Session {session_id} notified with OTP")
        return True

    def cleanup_expired(self) -> int:
        """
        Remove expired sessions.

        Returns:
            Number of sessions removed
        """
        now = datetime.now(timezone.utc)
        expired_ids = []

        with self._lock:
            for session_id, session in self._sessions.items():
                age = (now - session.created_at).total_seconds()
                if age > self._session_timeout:
                    expired_ids.append(session_id)

            for session_id in expired_ids:
                self.unregister(session_id)

        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired sessions")

        return len(expired_ids)

    def get_all_sessions(self) -> List[BotSession]:
        """Get all active sessions."""
        with self._lock:
            return list(self._sessions.values())


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
            received_at = datetime.now(timezone.utc)

        return OTPEntry(
            code=otp_code,
            source=OTPSource.EMAIL,
            target_identifier=target_email,
            received_at=received_at,
            raw_data=full_text[:500],
        )


class IMAPListener:
    """IMAP listener for catch-all mailbox monitoring."""

    def __init__(
        self,
        email: str,
        app_password: str,
        imap_config: IMAPConfig,
        email_processor: EmailProcessor,
        session_registry: SessionRegistry,
        poll_interval: int = 3,
        max_email_age_seconds: int = 300,
        max_processed_uids: int = 10000,
        noop_interval_seconds: int = 120,
    ):
        """
        Initialize IMAP listener.

        Args:
            email: Email address
            app_password: App password
            imap_config: IMAP configuration
            email_processor: Email processor instance
            session_registry: Session registry instance
            poll_interval: Poll interval in seconds
            max_email_age_seconds: Maximum age of emails to process
            max_processed_uids: Maximum size of processed UIDs set before cleanup
            noop_interval_seconds: Interval for IMAP NOOP keepalive commands
        """
        self._email = email
        self._app_password = app_password
        self._imap_config = imap_config
        self._email_processor = email_processor
        self._session_registry = session_registry
        self._poll_interval = poll_interval
        self._max_email_age = max_email_age_seconds
        self._max_processed_uids = max_processed_uids
        self._noop_interval = noop_interval_seconds

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._processed_uids: set = set()
        self._lock = threading.Lock()
        
        # Health tracking
        self._last_noop_time = time.time()
        self._connection_healthy = False
        self._last_successful_poll: Optional[datetime] = None
        self._total_reconnects = 0
        self._consecutive_poll_errors = 0

    def start(self):
        """Start IMAP listener thread."""
        if self._running:
            logger.warning("IMAP listener already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("IMAP listener started")

    def stop(self):
        """Stop IMAP listener thread."""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("IMAP listener stopped")

    def _connect_imap(self) -> imaplib.IMAP4_SSL:
        """Create and authenticate IMAP connection."""
        try:
            mail = imaplib.IMAP4_SSL(self._imap_config.host, self._imap_config.port)
            mail.login(self._email, self._app_password)
            mail.select(self._imap_config.folder)
            logger.debug(f"IMAP connection established to {self._imap_config.host}")
            return mail
        except Exception as e:
            logger.error(f"IMAP connection failed: {e}")
            raise

    def _listen_loop(self):
        """Main IMAP listening loop."""
        reconnect_delay = 5
        max_reconnect_delay = 60

        while self._running:
            mail = None
            try:
                mail = self._connect_imap()
                self._connection_healthy = True
                self._last_noop_time = time.time()
                reconnect_delay = 5  # Reset on successful connection

                # Main poll loop
                while self._running:
                    try:
                        # Send NOOP keepalive if interval elapsed
                        current_time = time.time()
                        if current_time - self._last_noop_time >= self._noop_interval:
                            try:
                                mail.noop()
                                self._last_noop_time = current_time
                                logger.debug("IMAP NOOP keepalive sent")
                            except Exception as e:
                                logger.warning(f"NOOP keepalive failed: {e}")
                                raise  # Trigger reconnection
                        
                        self._poll_emails(mail)
                        self._last_successful_poll = datetime.now(timezone.utc)
                        self._consecutive_poll_errors = 0
                        
                        # Cleanup processed UIDs after successful poll
                        self._cleanup_processed_uids()
                        
                        time.sleep(self._poll_interval)
                    except (imaplib.IMAP4.abort, imaplib.IMAP4.error) as e:
                        # Protocol-level errors - reconnect immediately
                        logger.error(f"IMAP protocol error: {e}")
                        self._consecutive_poll_errors += 1
                        break  # Reconnect
                    except Exception as e:
                        self._consecutive_poll_errors += 1
                        logger.error(f"Error polling emails (consecutive: {self._consecutive_poll_errors}): {e}")
                        
                        # Break after 5 consecutive errors
                        if self._consecutive_poll_errors >= 5:
                            logger.critical("5 consecutive poll errors - stopping IMAP listener")
                            self._running = False
                            break
                        break  # Reconnect

            except Exception as e:
                logger.error(f"IMAP listener error: {e}")
                self._total_reconnects += 1

            finally:
                self._connection_healthy = False
                if mail:
                    try:
                        mail.close()
                        mail.logout()
                    except Exception as e:
                        logger.debug(f"Error closing IMAP connection: {e}")

            # Wait before reconnecting
            if self._running:
                logger.info(f"Reconnecting in {reconnect_delay}s... (total reconnects: {self._total_reconnects})")
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

    def _poll_emails(self, mail: imaplib.IMAP4_SSL) -> None:
        """Poll for new emails."""
        # Search for recent unread emails
        since_time = datetime.now(timezone.utc) - timedelta(seconds=self._max_email_age)
        since_date = since_time.strftime("%d-%b-%Y")

        try:
            _, message_numbers = mail.search(None, f"(UNSEEN SINCE {since_date})")
        except Exception as e:
            logger.error(f"IMAP search failed: {e}")
            raise

        if not message_numbers[0]:
            return

        for num in message_numbers[0].split():
            try:
                # Check if already processed
                with self._lock:
                    if num in self._processed_uids:
                        continue
                    self._processed_uids.add(num)

                # Fetch and process email
                _, msg_data = mail.fetch(num, "(RFC822)")
                if msg_data and msg_data[0] and isinstance(msg_data[0], tuple):
                    email_body = msg_data[0][1]
                    msg = message_from_bytes(email_body)

                    # Process email
                    otp_entry = self._email_processor.process_email(msg)
                    if otp_entry:
                        # Find session and notify
                        session = self._session_registry.find_by_email(otp_entry.target_identifier)
                        if session:
                            self._session_registry.notify_otp(session.session_id, otp_entry.code)
                            logger.info(f"OTP delivered to session {session.session_id}")

            except Exception as e:
                logger.warning(f"Error processing email: {e}")
                with self._lock:
                    self._processed_uids.discard(num)

    def _cleanup_processed_uids(self) -> None:
        """Clean up processed UIDs set to prevent unbounded memory growth."""
        with self._lock:
            current_size = len(self._processed_uids)
            if current_size > self._max_processed_uids:
                # Discard until size is max_processed_uids // 2
                target_size = self._max_processed_uids // 2
                to_remove = current_size - target_size
                
                # Convert to list and remove oldest (first) items
                uid_list = list(self._processed_uids)
                for uid in uid_list[:to_remove]:
                    self._processed_uids.discard(uid)
                
                logger.info(
                    f"Cleaned up processed UIDs: {current_size} -> {len(self._processed_uids)} "
                    f"(removed {to_remove} oldest UIDs)"
                )

    def get_health(self) -> dict:
        """
        Get IMAP listener health status.
        
        Returns:
            Dictionary with health metrics
        """
        with self._lock:
            return {
                "connected": self._connection_healthy,
                "last_successful_poll": self._last_successful_poll.isoformat() if self._last_successful_poll else None,
                "total_reconnects": self._total_reconnects,
                "consecutive_poll_errors": self._consecutive_poll_errors,
                "processed_uids_count": len(self._processed_uids),
            }


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
            # Mask phone number better - show only last 3 digits
            masked = f"***{phone_number[-3:]}" if len(phone_number) > 3 else "***"
            logger.warning(f"No OTP found in SMS from {masked}")
            return None

        # Find session by phone number
        session = self._session_registry.find_by_phone(phone_number)
        if session:
            self._session_registry.notify_otp(session.session_id, otp_code)
            logger.info(f"SMS OTP delivered to session {session.session_id}")
            return otp_code

        # Mask phone number better - show only last 3 digits
        masked = f"***{phone_number[-3:]}" if len(phone_number) > 3 else "***"
        logger.warning(f"No session found for phone {masked}")
        return None


class OTPManager:
    """
    Centralized OTP Manager for VFS automation.

    Manages OTP codes from both email (catch-all mailbox) and SMS sources
    for 100+ concurrent bot sessions.

    Example:
        manager = OTPManager(
            email="akby.hakan@vizecep.com",
            app_password="xxxx-xxxx-xxxx-xxxx"
        )
        manager.start()

        session_id = manager.register_session(
            target_email="hollanda_vize@vizecep.com",
            phone_number="+905551234567",
            country="Netherlands"
        )

        otp = manager.wait_for_otp(session_id, timeout=120)
        manager.unregister_session(session_id)
        manager.stop()
    """

    def __init__(
        self,
        email: str,
        app_password: str,
        imap_config: Optional[IMAPConfig] = None,
        otp_timeout_seconds: int = 120,
        session_timeout_seconds: int = 600,
        max_email_age_seconds: int = 300,
        custom_patterns: Optional[List[str]] = None,
    ):
        """
        Initialize OTP Manager.

        Args:
            email: Microsoft 365 email address (catch-all mailbox)
            app_password: Microsoft 365 App Password
            imap_config: IMAP configuration (default: outlook.office365.com:993)
            otp_timeout_seconds: Maximum wait time for OTP (default: 120)
            session_timeout_seconds: Auto-expire sessions after this time (default: 600)
            max_email_age_seconds: Maximum age of emails to process (default: 300)
            custom_patterns: Optional custom regex patterns for OTP extraction
        """
        self._email = email
        self._app_password = app_password
        self._imap_config = imap_config or IMAPConfig()
        self._otp_timeout = otp_timeout_seconds
        self._session_timeout = session_timeout_seconds
        self._max_email_age = max_email_age_seconds

        # Initialize components
        self._pattern_matcher = OTPPatternMatcher(custom_patterns)
        self._session_registry = SessionRegistry(session_timeout_seconds)
        self._email_processor = EmailProcessor(self._pattern_matcher)
        self._imap_listener = IMAPListener(
            email=email,
            app_password=app_password,
            imap_config=self._imap_config,
            email_processor=self._email_processor,
            session_registry=self._session_registry,
            max_email_age_seconds=max_email_age_seconds,
        )
        self._sms_handler = SMSWebhookHandler(
            session_registry=self._session_registry, pattern_matcher=self._pattern_matcher
        )

        # Cleanup thread
        self._cleanup_thread: Optional[threading.Thread] = None
        self._running = False

        logger.info(
            f"OTPManager initialized for {email} "
            f"(otp_timeout: {otp_timeout_seconds}s, session_timeout: {session_timeout_seconds}s)"
        )

    def start(self):
        """Start OTP Manager (IMAP listener and cleanup scheduler)."""
        if self._running:
            logger.warning("OTP Manager already running")
            return

        self._running = True
        self._imap_listener.start()

        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

        logger.info("OTP Manager started")

    def stop(self):
        """Stop OTP Manager."""
        if not self._running:
            return

        self._running = False
        self._imap_listener.stop()

        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)

        logger.info("OTP Manager stopped")

    def _cleanup_loop(self):
        """Background loop for cleaning up expired sessions."""
        while self._running:
            try:
                time.sleep(60)  # Run every minute
                self._session_registry.cleanup_expired()
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    def register_session(
        self,
        target_email: Optional[str] = None,
        phone_number: Optional[str] = None,
        country: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Register a new bot session.

        Args:
            target_email: Target email address (e.g., "bot55@vizecep.com")
            phone_number: Phone number (e.g., "+905551234567")
            country: Country code (e.g., "Netherlands")
            metadata: Additional metadata

        Returns:
            Session ID
        """
        if not target_email and not phone_number:
            raise ValueError("At least one of target_email or phone_number must be provided")

        return self._session_registry.register(
            target_email=target_email, phone_number=phone_number, country=country, metadata=metadata
        )

    def unregister_session(self, session_id: str) -> None:
        """
        Unregister a session.

        Args:
            session_id: Session ID to unregister
        """
        self._session_registry.unregister(session_id)

    def wait_for_otp(self, session_id: str, timeout: Optional[int] = None) -> Optional[str]:
        """
        Wait for OTP code (from email or SMS).

        This method blocks until an OTP is received or timeout occurs.

        Args:
            session_id: Session ID
            timeout: Maximum wait time in seconds (default: otp_timeout_seconds)

        Returns:
            OTP code or None if timeout
        """
        timeout = timeout or self._otp_timeout
        session = self._session_registry.get_session(session_id)

        if not session:
            logger.error(f"Session not found: {session_id}")
            return None

        # Check if OTP already received
        if session.otp_code:
            return session.otp_code

        # Wait for OTP
        session.state = SessionState.WAITING_OTP
        if session.otp_event is not None:
            result = session.otp_event.wait(timeout=timeout)
        else:
            result = False

        if result and session.otp_code:
            logger.info(f"OTP received for session {session_id}")
            return session.otp_code

        logger.warning(f"OTP timeout for session {session_id}")
        session.state = SessionState.EXPIRED
        return None

    def process_sms_webhook(self, phone_number: str, message: str) -> Optional[str]:
        """
        Process SMS webhook and route OTP to session.

        Args:
            phone_number: Phone number
            message: SMS message text

        Returns:
            OTP code if extracted and delivered, None otherwise
        """
        return self._sms_handler.process_sms(phone_number, message)

    def manual_otp_input(self, session_id: str, otp_code: str) -> bool:
        """
        Manually input OTP for a session.

        Args:
            session_id: Session ID
            otp_code: OTP code

        Returns:
            True if session was found and notified
        """
        logger.info(f"Manual OTP input for session {session_id}")
        return self._session_registry.notify_otp(session_id, otp_code)

    def register_account(
        self,
        vfs_email: str,
        vfs_password: str,
        phone_number: str,
        target_email: str,
        country: Optional[str] = None,
        visa_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Register a VFS account with automatic webhook URL generation.

        This method creates a VFS account and automatically generates a unique
        webhook token and URL for SMS OTP delivery via SMS Forwarder app.

        Args:
            vfs_email: VFS login email
            vfs_password: VFS password
            phone_number: Phone number for SMS OTP
            target_email: Catch-all email for email OTP
            country: Optional country code
            visa_type: Optional visa type
            metadata: Optional metadata

        Returns:
            VFSAccount with webhook_url field

        Example:
            account = manager.register_account(
                vfs_email="user@email.com",
                vfs_password="password",
                phone_number="+905551234567",
                target_email="bot1@vizecep.com"
            )
            print(account.webhook_url)
            # → https://api.vizecep.com/webhook/sms/tk_a1b2c3d4e5f6
        """
        from src.models.vfs_account import VFSAccountManager

        # Initialize account manager if not already done
        if not hasattr(self, "_account_manager"):
            import os

            from src.services.webhook_token_manager import WebhookTokenManager

            base_url = os.getenv("WEBHOOK_BASE_URL")
            if not base_url:
                raise ValueError(
                    "WEBHOOK_BASE_URL environment variable must be set "
                    "(e.g., https://your-api-domain.example.com). "
                    "Configure it in your .env file."
                )
            webhook_manager = WebhookTokenManager(base_url=base_url)
            self._account_manager = VFSAccountManager(webhook_token_manager=webhook_manager)

            # Set webhook manager for routes
            from web.routes.sms_webhook import set_webhook_manager

            set_webhook_manager(webhook_manager)

        # Register account
        account = self._account_manager.register_account(
            vfs_email=vfs_email,
            vfs_password=vfs_password,
            phone_number=phone_number,
            target_email=target_email,
            country=country,
            visa_type=visa_type,
            metadata=metadata,
        )

        logger.info(
            f"Registered VFS account {account.account_id} with webhook URL: {account.webhook_url}"
        )
        return account.to_dict()

    def get_webhook_url(self, account_id: str) -> str:
        """
        Get webhook URL for an account.

        Args:
            account_id: Account ID

        Returns:
            Webhook URL

        Raises:
            ValueError: If account not found
        """
        if not hasattr(self, "_account_manager"):
            raise ValueError("No accounts registered. Call register_account first.")

        account = self._account_manager.get_account(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")

        return account.webhook_url

    def process_webhook_sms(self, token: str, payload: Dict) -> Optional[str]:
        """
        Process SMS from webhook and extract OTP.

        This method is called by the webhook endpoint to process incoming
        SMS messages and route OTP to the correct session.

        Args:
            token: Webhook token
            payload: SMS payload from forwarder

        Returns:
            Extracted OTP code or None

        Raises:
            ValueError: If token is invalid or payload parsing fails
        """
        if not hasattr(self, "_account_manager"):
            raise ValueError("Webhook system not initialized. Call register_account first.")

        webhook_manager = self._account_manager.webhook_manager

        # Process SMS and extract OTP
        otp = webhook_manager.process_sms(token, payload)

        if otp:
            # Get webhook token to find account
            webhook_token = webhook_manager.validate_token(token)
            if webhook_token and webhook_token.session_id:
                # Notify the session
                self._session_registry.notify_otp(webhook_token.session_id, otp)
                logger.info(f"OTP from webhook delivered to session {webhook_token.session_id}")

        return otp

    def start_session(self, account_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Start a bot session for a VFS account.

        This method creates a session and links it to the account's webhook token
        so that incoming SMS OTP messages are automatically routed to this session.

        Args:
            account_id: VFS account ID
            metadata: Optional metadata

        Returns:
            Session ID

        Raises:
            ValueError: If account not found
        """
        if not hasattr(self, "_account_manager"):
            raise ValueError("No accounts registered. Call register_account first.")

        account = self._account_manager.get_account(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")

        # Register session with target email and phone
        session_id = self.register_session(
            target_email=account.target_email,
            phone_number=account.phone_number,
            country=account.country,
            metadata=metadata or {},
        )

        # Link webhook token to session
        webhook_manager = self._account_manager.webhook_manager
        webhook_manager.link_session(account.webhook_token, session_id)

        logger.info(
            f"Started session {session_id} for account {account_id}, "
            f"linked to webhook {account.webhook_token[:10]}..."
        )

        return session_id

    def end_session(self, session_id: str) -> None:
        """
        End a bot session and unlink from webhook.

        Args:
            session_id: Session ID
        """
        session = self._session_registry.get_session(session_id)
        if session and hasattr(self, "_account_manager"):
            # Find webhook token linked to this session
            webhook_manager = self._account_manager.webhook_manager
            for webhook_token in webhook_manager.list_tokens():
                if webhook_token.session_id == session_id:
                    webhook_manager.unlink_session(webhook_token.token)
                    logger.info(f"Unlinked session {session_id} from webhook")
                    break

        # Unregister session
        self.unregister_session(session_id)

    def health_check(self) -> Dict[str, Any]:
        """
        Get OTP Manager health status.

        Returns:
            Dictionary with health metrics
        """
        sessions = self._session_registry.get_all_sessions()

        return {
            "status": "healthy" if self._running else "stopped",
            "active_sessions": len(sessions),
            "otp_timeout_seconds": self._otp_timeout,
            "session_timeout_seconds": self._session_timeout,
            "imap_config": {
                "host": self._imap_config.host,
                "port": self._imap_config.port,
                "folder": self._imap_config.folder,
            },
            "imap_health": self._imap_listener.get_health(),
        }


# Global instance management
_otp_manager: Optional[OTPManager] = None
_manager_lock = threading.Lock()


def get_otp_manager(
    email: Optional[str] = None, app_password: Optional[str] = None, **kwargs: Any
) -> OTPManager:
    """
    Get global OTPManager instance (thread-safe singleton).

    Args:
        email: Email address (required on first call)
        app_password: App password (required on first call)
        **kwargs: Additional configuration options

    Returns:
        Global OTPManager instance

    Raises:
        ValueError: If email/password not provided on first initialization
    """
    global _otp_manager

    # Thread-safe singleton initialization
    with _manager_lock:
        if _otp_manager is None:
            if not email or not app_password:
                raise ValueError("Email and app_password required on first call")

            _otp_manager = OTPManager(email, app_password, **kwargs)
            logger.info("Global OTPManager initialized")

        return _otp_manager
