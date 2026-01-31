"""VFS Account model and management.

This module provides VFS account management with integrated webhook token system.
Each account automatically gets a unique webhook URL for SMS OTP delivery.
"""

import logging
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.utils.encryption import encrypt_password, decrypt_password

logger = logging.getLogger(__name__)


@dataclass
class VFSAccount:
    """
    VFS account with webhook token.

    Attributes:
        account_id: Unique account identifier
        vfs_email: VFS login email
        vfs_password: Encrypted VFS password
        phone_number: Phone number for SMS OTP
        target_email: Catch-all email for email OTP
        webhook_token: Unique webhook token
        webhook_url: Complete webhook URL
        country: Optional country code
        visa_type: Optional visa type
        is_active: Account active status
        created_at: Account creation timestamp
        last_login_at: Last successful login timestamp
        metadata: Additional metadata
    """

    account_id: str
    vfs_email: str
    vfs_password: str  # Encrypted
    phone_number: str
    target_email: str
    webhook_token: str
    webhook_url: str
    country: Optional[str] = None
    visa_type: Optional[str] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_password: bool = False) -> Dict[str, Any]:
        """
        Convert account to dictionary.

        Args:
            include_password: If True, includes encrypted password (default: False)

        Returns:
            Dictionary representation of account
        """
        data = {
            "account_id": self.account_id,
            "vfs_email": self.vfs_email,
            "phone_number": self.phone_number,
            "target_email": self.target_email,
            "webhook_token": self.webhook_token,
            "webhook_url": self.webhook_url,
            "country": self.country,
            "visa_type": self.visa_type,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "metadata": self.metadata,
        }

        if include_password:
            data["vfs_password"] = self.vfs_password

        return data


class VFSAccountManager:
    """
    Manages VFS accounts with webhook tokens.

    This manager handles account registration, lookup, and lifecycle management.
    It integrates with WebhookTokenManager for automatic webhook URL generation.
    """

    def __init__(self, webhook_token_manager=None):
        """
        Initialize VFS account manager.

        Args:
            webhook_token_manager: Optional WebhookTokenManager instance.
                                  If None, creates a new instance.
        """
        from src.services.webhook_token_manager import WebhookTokenManager

        self.webhook_manager = webhook_token_manager or WebhookTokenManager()
        self._accounts: Dict[str, VFSAccount] = {}
        self._email_index: Dict[str, str] = {}  # vfs_email -> account_id
        self._phone_index: Dict[str, str] = {}  # phone_number -> account_id
        self._token_index: Dict[str, str] = {}  # webhook_token -> account_id
        self._lock = threading.RLock()  # Re-entrant lock for thread safety

        logger.info("VFSAccountManager initialized")

    def _generate_account_id(self) -> str:
        """Generate a unique account ID."""
        return f"acc_{secrets.token_hex(12)}"

    def register_account(
        self,
        vfs_email: str,
        vfs_password: str,
        phone_number: str,
        target_email: str,
        country: Optional[str] = None,
        visa_type: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> VFSAccount:
        """
        Register a new VFS account (thread-safe).

        Automatically generates:
        - Unique account_id
        - Webhook token
        - Webhook URL

        Args:
            vfs_email: VFS login email
            vfs_password: VFS password (will be encrypted)
            phone_number: Phone number for SMS OTP
            target_email: Catch-all email for email OTP
            country: Optional country code
            visa_type: Optional visa type
            metadata: Optional metadata

        Returns:
            Created VFSAccount

        Raises:
            ValueError: If account with same email or phone already exists
        """
        with self._lock:
            # Check for duplicates
            if vfs_email in self._email_index:
                raise ValueError(f"Account with email {vfs_email} already exists")

            if phone_number in self._phone_index:
                raise ValueError(f"Account with phone {phone_number} already exists")

            # Generate account ID
            account_id = self._generate_account_id()

            # Generate webhook token
            webhook_token = self.webhook_manager.generate_token(account_id)

            # Encrypt password
            encrypted_password = encrypt_password(vfs_password)

            # Register webhook token
            self.webhook_manager.register_token(
                token=webhook_token,
                account_id=account_id,
                phone_number=phone_number,
                metadata=metadata,
            )

            # Get webhook URL
            webhook_url = self.webhook_manager.get_webhook_url(webhook_token)

            # Create account
            account = VFSAccount(
                account_id=account_id,
                vfs_email=vfs_email,
                vfs_password=encrypted_password,
                phone_number=phone_number,
                target_email=target_email,
                webhook_token=webhook_token,
                webhook_url=webhook_url,
                country=country,
                visa_type=visa_type,
                metadata=metadata or {},
            )

            # Store account and update indexes
            self._accounts[account_id] = account
            self._email_index[vfs_email] = account_id
            self._phone_index[phone_number] = account_id
            self._token_index[webhook_token] = account_id

            logger.info(
                f"Registered VFS account {account_id} for {vfs_email}, " f"webhook: {webhook_url}"
            )

            return account

    def get_account(self, account_id: str) -> Optional[VFSAccount]:
        """
        Get account by ID.

        Args:
            account_id: Account ID

        Returns:
            VFSAccount or None
        """
        return self._accounts.get(account_id)

    def get_account_by_email(self, vfs_email: str) -> Optional[VFSAccount]:
        """
        Get account by VFS email.

        Args:
            vfs_email: VFS email address

        Returns:
            VFSAccount or None
        """
        account_id = self._email_index.get(vfs_email)
        if account_id:
            return self._accounts.get(account_id)
        return None

    def get_account_by_token(self, webhook_token: str) -> Optional[VFSAccount]:
        """
        Get account by webhook token.

        Args:
            webhook_token: Webhook token

        Returns:
            VFSAccount or None
        """
        account_id = self._token_index.get(webhook_token)
        if account_id:
            return self._accounts.get(account_id)
        return None

    def get_account_by_phone(self, phone_number: str) -> Optional[VFSAccount]:
        """
        Get account by phone number.

        Args:
            phone_number: Phone number

        Returns:
            VFSAccount or None
        """
        account_id = self._phone_index.get(phone_number)
        if account_id:
            return self._accounts.get(account_id)
        return None

    def update_account(self, account_id: str, **kwargs: Any) -> VFSAccount:
        """
        Update account fields.

        Args:
            account_id: Account ID
            **kwargs: Fields to update

        Returns:
            Updated VFSAccount

        Raises:
            ValueError: If account not found or invalid fields
        """
        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")

        # Handle password encryption
        if "vfs_password" in kwargs and kwargs["vfs_password"]:
            kwargs["vfs_password"] = encrypt_password(kwargs["vfs_password"])

        # Update allowed fields
        allowed_fields = {
            "vfs_password",
            "country",
            "visa_type",
            "is_active",
            "last_login_at",
            "metadata",
        }

        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(account, key, value)
            else:
                logger.warning(f"Ignoring update to non-updatable field: {key}")

        logger.info(f"Updated account {account_id}")
        return account

    def deactivate_account(self, account_id: str) -> None:
        """
        Deactivate an account.

        Args:
            account_id: Account ID

        Raises:
            ValueError: If account not found
        """
        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")

        account.is_active = False

        # Revoke webhook token
        self.webhook_manager.revoke_token(account.webhook_token)

        logger.info(f"Deactivated account {account_id}")

    def reactivate_account(self, account_id: str) -> None:
        """
        Reactivate a deactivated account.

        Args:
            account_id: Account ID

        Raises:
            ValueError: If account not found
        """
        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")

        account.is_active = True

        # Reactivate webhook token
        webhook_token_obj = self.webhook_manager.validate_token(account.webhook_token)
        if webhook_token_obj:
            webhook_token_obj.is_active = True

        logger.info(f"Reactivated account {account_id}")

    def list_accounts(self, active_only: bool = True) -> List[VFSAccount]:
        """
        List all accounts.

        Args:
            active_only: If True, only return active accounts

        Returns:
            List of VFSAccount objects
        """
        accounts = list(self._accounts.values())

        if active_only:
            accounts = [acc for acc in accounts if acc.is_active]

        return accounts

    def get_decrypted_password(self, account_id: str) -> Optional[str]:
        """
        Get decrypted password for an account.

        Args:
            account_id: Account ID

        Returns:
            Decrypted password or None
        """
        account = self.get_account(account_id)
        if not account:
            return None

        try:
            return decrypt_password(account.vfs_password)
        except Exception as e:
            logger.error(f"Failed to decrypt password for account {account_id}: {e}")
            return None
