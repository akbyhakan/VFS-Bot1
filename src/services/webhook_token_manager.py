"""Webhook Token Manager for dynamic SMS OTP routing.

This module manages webhook tokens for VFS accounts, enabling each account
to have a unique webhook URL for SMS OTP delivery via SMS Forwarder app.
"""

import logging
import re
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WebhookToken:
    """
    Represents a webhook token for SMS OTP delivery.
    
    Attributes:
        token: Unique webhook token (tk_xxxxxxxxxxxx format)
        account_id: Associated VFS account ID
        phone_number: Phone number receiving SMS
        session_id: Currently linked bot session ID (if any)
        webhook_url: Complete webhook URL
        created_at: Token creation timestamp
        last_used_at: Last time token was used
        is_active: Whether token is active
        metadata: Additional metadata
    """
    token: str
    account_id: str
    phone_number: str
    session_id: Optional[str] = None
    webhook_url: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: Optional[datetime] = None
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SMSPayload:
    """
    Standardized SMS payload from SMS Forwarder.
    
    Attributes:
        message: SMS message content
        phone_number: Sender phone number (optional)
        timestamp: Message timestamp (optional)
        sim_slot: SIM slot number (optional)
        raw_payload: Original payload data
    """
    message: str
    phone_number: Optional[str] = None
    timestamp: Optional[str] = None
    sim_slot: Optional[int] = None
    raw_payload: Dict[str, Any] = field(default_factory=dict)


class SMSPayloadParser:
    """Parses different SMS Forwarder payload formats into standardized format."""
    
    # Known field names (in priority order)
    MESSAGE_FIELDS = ["message", "text", "body", "sms", "content", "msg"]
    PHONE_FIELDS = ["from", "phone", "phone_number", "sender", "number"]
    TIMESTAMP_FIELDS = ["timestamp", "time", "date", "received_at", "sentStamp"]
    SIM_SLOT_FIELDS = ["sim_slot", "sim", "slot", "simSlot"]
    
    @classmethod
    def parse(cls, payload: Dict[str, Any]) -> SMSPayload:
        """
        Parse incoming SMS payload into standardized format.
        
        Args:
            payload: Raw payload from SMS Forwarder
            
        Returns:
            Standardized SMSPayload object
            
        Raises:
            ValueError: If no message content found
        """
        # Extract message
        message = next(
            (payload.get(field) for field in cls.MESSAGE_FIELDS if payload.get(field)),
            None
        )
        
        if not message:
            raise ValueError(
                f"No message content found. Expected one of: {', '.join(cls.MESSAGE_FIELDS)}"
            )
        
        # Extract phone number
        phone_number = next(
            (payload.get(field) for field in cls.PHONE_FIELDS if payload.get(field)),
            None
        )
        
        # Extract timestamp
        timestamp = next(
            (payload.get(field) for field in cls.TIMESTAMP_FIELDS if payload.get(field)),
            None
        )
        
        # Extract SIM slot
        sim_slot_raw = next(
            (payload.get(field) for field in cls.SIM_SLOT_FIELDS if payload.get(field)),
            None
        )
        sim_slot = int(sim_slot_raw) if sim_slot_raw is not None else None
        
        return SMSPayload(
            message=str(message),
            phone_number=str(phone_number) if phone_number else None,
            timestamp=str(timestamp) if timestamp else None,
            sim_slot=sim_slot,
            raw_payload=payload
        )


class WebhookTokenManager:
    """
    Manages webhook tokens for VFS accounts.
    
    Each VFS account gets a unique webhook token that routes SMS OTP
    messages to the correct bot session.
    """
    
    TOKEN_PREFIX = "tk_"
    TOKEN_LENGTH = 24  # Random hex characters after prefix
    
    # OTP extraction patterns (in priority order - most specific first)
    OTP_PATTERNS = [
        r'(?:OTP|code|verification|passcode)[:\s]+(\d{4,8})',  # "OTP: 123456"
        r'(?:OTP|code|verification|passcode)\s+is[:\s]+(\d{4,8})',  # "OTP is: 123456"
        r'\b(\d{6})\b(?!\d)',  # Generic 6-digit (with word boundary, not followed by more digits)
        r'\b(\d{4})\b(?!\d)',  # Generic 4-digit (with word boundary, not followed by more digits)
    ]
    
    def __init__(self, base_url: str = "https://api.vizecep.com"):
        """
        Initialize webhook token manager.
        
        Args:
            base_url: Base URL for webhook endpoints
        """
        self.base_url = base_url.rstrip('/')
        self._tokens: Dict[str, WebhookToken] = {}
        self._account_tokens: Dict[str, str] = {}  # account_id -> token
        self._phone_tokens: Dict[str, str] = {}  # phone_number -> token
        self._lock = threading.RLock()  # Re-entrant lock for thread safety
        logger.info(f"WebhookTokenManager initialized with base URL: {self.base_url}")
    
    def generate_token(self, account_id: str) -> str:
        """
        Generate a unique webhook token.
        
        Args:
            account_id: VFS account ID
            
        Returns:
            Unique token in format: tk_xxxxxxxxxxxx
        """
        token = f"{self.TOKEN_PREFIX}{secrets.token_hex(self.TOKEN_LENGTH // 2)}"
        logger.debug(f"Generated token for account {account_id}: {token[:10]}...")
        return token
    
    def register_token(
        self,
        token: str,
        account_id: str,
        phone_number: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> WebhookToken:
        """
        Register a webhook token (thread-safe).
        
        Args:
            token: Webhook token
            account_id: VFS account ID
            phone_number: Phone number for SMS delivery
            session_id: Optional bot session ID
            metadata: Optional metadata
            
        Returns:
            Registered WebhookToken
            
        Raises:
            ValueError: If token already exists
        """
        with self._lock:
            if token in self._tokens:
                raise ValueError(f"Token already exists: {token}")
            
            webhook_url = f"{self.base_url}/webhook/sms/{token}"
            
            webhook_token = WebhookToken(
                token=token,
                account_id=account_id,
                phone_number=phone_number,
                session_id=session_id,
                webhook_url=webhook_url,
                metadata=metadata or {}
            )
            
            self._tokens[token] = webhook_token
            self._account_tokens[account_id] = token
            self._phone_tokens[phone_number] = token
            
            logger.info(f"Registered webhook token for account {account_id}, phone {phone_number}")
            return webhook_token
    
    def get_webhook_url(self, token: str) -> str:
        """
        Get full webhook URL for a token.
        
        Args:
            token: Webhook token
            
        Returns:
            Complete webhook URL
            
        Raises:
            ValueError: If token not found
        """
        webhook_token = self.validate_token(token)
        if not webhook_token:
            raise ValueError(f"Invalid token: {token}")
        return webhook_token.webhook_url
    
    def validate_token(self, token: str) -> Optional[WebhookToken]:
        """
        Validate a webhook token.
        
        Args:
            token: Token to validate
            
        Returns:
            WebhookToken if valid, None otherwise
        """
        webhook_token = self._tokens.get(token)
        
        if not webhook_token:
            logger.warning(f"Token not found: {token}")
            return None
        
        if not webhook_token.is_active:
            logger.warning(f"Token is inactive: {token}")
            return None
        
        return webhook_token
    
    def link_session(self, token: str, session_id: str):
        """
        Link a token to an active bot session (thread-safe).
        
        Args:
            token: Webhook token
            session_id: Bot session ID
            
        Raises:
            ValueError: If token is invalid
        """
        with self._lock:
            webhook_token = self.validate_token(token)
            if not webhook_token:
                raise ValueError(f"Invalid token: {token}")
            
            webhook_token.session_id = session_id
            logger.info(f"Linked token {token[:10]}... to session {session_id}")
    
    def unlink_session(self, token: str):
        """
        Unlink a token from its session.
        
        Args:
            token: Webhook token
        """
        webhook_token = self._tokens.get(token)
        if webhook_token:
            webhook_token.session_id = None
            logger.debug(f"Unlinked session from token {token[:10]}...")
    
    def process_sms(self, token: str, payload: Dict) -> Optional[str]:
        """
        Process incoming SMS and extract OTP.
        
        Args:
            token: Webhook token
            payload: SMS payload from forwarder
            
        Returns:
            Extracted OTP code or None
            
        Raises:
            ValueError: If token is invalid or payload parsing fails
        """
        # Validate token
        webhook_token = self.validate_token(token)
        if not webhook_token:
            raise ValueError(f"Invalid token: {token}")
        
        # Parse payload
        try:
            sms_payload = SMSPayloadParser.parse(payload)
        except ValueError as e:
            logger.error(f"Failed to parse SMS payload: {e}")
            raise
        
        # Update last used timestamp
        webhook_token.last_used_at = datetime.now(timezone.utc)
        
        # Extract OTP from message
        otp = self._extract_otp(sms_payload.message)
        
        if otp:
            logger.info(
                f"Extracted OTP for account {webhook_token.account_id}: {otp[:2]}****"
            )
        else:
            logger.warning(
                f"No OTP found in message for token {token[:10]}...: {sms_payload.message[:50]}"
            )
        
        return otp
    
    def _extract_otp(self, message: str) -> Optional[str]:
        """
        Extract OTP code from SMS message.
        
        Args:
            message: SMS message text
            
        Returns:
            Extracted OTP or None
        """
        for pattern in self.OTP_PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def revoke_token(self, token: str):
        """
        Revoke (deactivate) a webhook token.
        
        Args:
            token: Token to revoke
        """
        webhook_token = self._tokens.get(token)
        if webhook_token:
            webhook_token.is_active = False
            logger.info(f"Revoked token {token[:10]}...")
    
    def list_tokens(self, account_id: Optional[str] = None) -> List[WebhookToken]:
        """
        List webhook tokens.
        
        Args:
            account_id: Optional account ID filter
            
        Returns:
            List of webhook tokens
        """
        if account_id:
            token = self._account_tokens.get(account_id)
            if token and token in self._tokens:
                return [self._tokens[token]]
            return []
        
        return list(self._tokens.values())
    
    def get_token_by_account(self, account_id: str) -> Optional[WebhookToken]:
        """
        Get webhook token for an account.
        
        Args:
            account_id: Account ID
            
        Returns:
            WebhookToken or None
        """
        token = self._account_tokens.get(account_id)
        if token:
            return self._tokens.get(token)
        return None
    
    def get_token_by_phone(self, phone_number: str) -> Optional[WebhookToken]:
        """
        Get webhook token for a phone number.
        
        Args:
            phone_number: Phone number
            
        Returns:
            WebhookToken or None
        """
        token = self._phone_tokens.get(phone_number)
        if token:
            return self._tokens.get(token)
        return None
