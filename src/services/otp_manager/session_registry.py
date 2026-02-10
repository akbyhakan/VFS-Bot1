"""Session registry for managing bot sessions.

This module provides thread-safe session management for OTP delivery.
"""

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import BotSession, SessionState

logger = logging.getLogger(__name__)


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
