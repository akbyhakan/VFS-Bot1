"""Security middleware for web dashboard."""

import secrets
import hashlib
import hmac
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from threading import RLock
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

security = HTTPBearer()


class APIKeyManager:
    """Thread-safe API key manager using singleton pattern."""

    _instance: Optional["APIKeyManager"] = None
    _lock = RLock()
    _keys: Dict[str, Dict[str, Any]]
    _salt: Optional[bytes]

    def __new__(cls) -> "APIKeyManager":
        """Create or return singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                # Initialize in __new__ to ensure it happens once
                cls._instance._keys = {}
                cls._instance._salt = None
            return cls._instance

    def __init__(self) -> None:
        """Initialize is a no-op since we use __new__ for singleton."""
        pass

    def get_salt(self) -> bytes:
        """Get API key salt from environment variable - REQUIRED in production."""
        with self._lock:
            if self._salt is None:
                self._load_salt()
            return self._salt

    def _load_salt(self) -> None:
        """Load salt from environment (must be called with lock held)."""
        salt_env = os.getenv("API_KEY_SALT")

        if not salt_env:
            # STRICT MODE: Salt is MANDATORY in all environments
            raise ValueError(
                "API_KEY_SALT environment variable MUST be set in ALL environments. "
                "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        if len(salt_env) < 32:
            raise ValueError(
                f"API_KEY_SALT must be at least 32 characters for security "
                f"(current: {len(salt_env)})"
            )

        self._salt = salt_env.encode()
        logger.info("API_KEY_SALT loaded successfully")

    def _hash_key(self, api_key: str) -> str:
        """Hash API key using HMAC-SHA256."""
        salt = self.get_salt()
        return hmac.new(salt, api_key.encode(), hashlib.sha256).hexdigest()

    def verify_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Verify API key and return metadata.

        Args:
            api_key: API key to verify

        Returns:
            API key metadata if valid, None otherwise
        """
        with self._lock:
            key_hash = self._hash_key(api_key)
            return self._keys.get(key_hash)

    def add_key(self, api_key: str, metadata: Dict[str, Any]) -> str:
        """
        Add API key with metadata.

        Args:
            api_key: API key to add
            metadata: Key metadata (name, scopes, etc.)

        Returns:
            Key hash
        """
        with self._lock:
            key_hash = self._hash_key(api_key)
            # Ensure created timestamp
            if "created" not in metadata:
                metadata["created"] = datetime.now().isoformat()
            self._keys[key_hash] = metadata
            return key_hash

    def rotate_key(self, old_api_key: str, new_api_key: str) -> Optional[str]:
        """
        Rotate an API key - remove old key and add new one with same metadata.

        Args:
            old_api_key: Current API key to be replaced
            new_api_key: New API key to add

        Returns:
            New key hash if successful, None if old key not found
        """
        with self._lock:
            old_key_hash = self._hash_key(old_api_key)
            metadata = self._keys.get(old_key_hash)

            if metadata is None:
                logger.warning("Cannot rotate: old API key not found")
                return None

            # Remove old key
            del self._keys[old_key_hash]

            # Add new key with same metadata but updated timestamp
            new_metadata = metadata.copy()
            new_metadata["rotated_at"] = datetime.now().isoformat()
            new_key_hash = self._hash_key(new_api_key)
            self._keys[new_key_hash] = new_metadata

            logger.info(f"API key rotated for '{metadata.get('name', 'unknown')}'")
            return new_key_hash

    def cleanup_expired_keys(self, max_age_days: int = 90) -> int:
        """
        Remove API keys older than specified age.

        Args:
            max_age_days: Maximum age of keys in days

        Returns:
            Number of keys removed
        """
        from datetime import datetime, timedelta

        with self._lock:
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(days=max_age_days)

            expired_keys = []
            for key_hash, metadata in self._keys.items():
                created_str = metadata.get("created")
                if created_str:
                    try:
                        created_time = datetime.fromisoformat(created_str)
                        if created_time < cutoff_time:
                            expired_keys.append(key_hash)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid created timestamp for key: {created_str}")

            # Remove expired keys
            for key_hash in expired_keys:
                metadata = self._keys.pop(key_hash, {})
                logger.info(f"Removed expired API key: {metadata.get('name', 'unknown')}")

            return len(expired_keys)

    def load_keys(self) -> None:
        """Load API keys from environment."""
        master_key = os.getenv("DASHBOARD_API_KEY")
        if master_key:
            self.add_key(
                master_key,
                {
                    "name": "master",
                    "created": datetime.now().isoformat(),
                    "scopes": ["read", "write", "admin"],
                },
            )


# Backward compatibility - keep old global variables and functions
API_KEYS: Dict[str, Dict[str, Any]] = {}
_API_KEY_SALT: Optional[bytes] = None


def _get_api_key_salt() -> bytes:
    """Get API key salt from environment variable - REQUIRED in production."""
    manager = APIKeyManager()
    return manager.get_salt()


def generate_api_key() -> str:
    """
    Generate a new API key.

    Returns:
        Secure random API key
    """
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """
    Hash API key for storage using HMAC-SHA256 with salt.

    Args:
        api_key: API key to hash

    Returns:
        HMAC-SHA256 hash of the API key
    """
    manager = APIKeyManager()
    return manager._hash_key(api_key)


def load_api_keys() -> None:
    """Load API keys from environment or file."""
    manager = APIKeyManager()
    manager.load_keys()

    # Backward compatibility: sync to global API_KEYS dict
    master_key = os.getenv("DASHBOARD_API_KEY")
    if master_key:
        key_hash = hash_api_key(master_key)
        API_KEYS[key_hash] = {
            "name": "master",
            "created": datetime.now().isoformat(),
            "scopes": ["read", "write", "admin"],
        }


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> Dict[str, Any]:
    """
    Verify API key from Authorization header.

    Args:
        credentials: HTTP authorization credentials

    Returns:
        API key metadata

    Raises:
        HTTPException: If API key is invalid
    """
    manager = APIKeyManager()
    api_key = credentials.credentials
    key_metadata = manager.verify_key(api_key)

    if key_metadata is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return key_metadata


# Initialize API keys on module load
load_api_keys()
