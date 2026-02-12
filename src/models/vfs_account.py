"""VFS Account model.

This module provides the VFS account dataclass model.
Each account automatically gets a unique webhook URL for SMS OTP delivery.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


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
