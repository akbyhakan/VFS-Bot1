"""Main OTP Manager class and singleton accessor.

This module provides the central OTPManager class that coordinates
all OTP management components.
"""

import threading
import time
from typing import Any, Dict, List, Optional

from loguru import logger

from .email_processor import EmailProcessor
from .imap_listener import IMAPListener
from .models import IMAPConfig, SessionState
from .pattern_matcher import OTPPatternMatcher
from .session_registry import SessionRegistry
from .sms_handler import SMSWebhookHandler


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
        from src.services.vfs_account_manager import VFSAccountManager

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
