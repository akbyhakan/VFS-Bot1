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
    
    _instance: Optional['APIKeyManager'] = None
    _lock = RLock()
    
    def __new__(cls) -> 'APIKeyManager':
        """Create or return singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                # Initialize in __new__ to ensure it happens once
                cls._instance._keys: Dict[str, Dict[str, Any]] = {}
                cls._instance._salt: Optional[bytes] = None
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
        env = os.getenv("ENV", "production").lower()
        
        if not salt_env:
            # Explicitly allowed development environments
            allowed_dev_envs = ["development", "dev", "test", "testing", "local"]
            if env not in allowed_dev_envs:
                raise ValueError(
                    f"API_KEY_SALT environment variable MUST be set in '{env}' environment. "
                    "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
            
            # Development: generate random salt for this session
            logger.warning(
                "⚠️ SECURITY WARNING: API_KEY_SALT not set. "
                "Generating random salt for this session. This is only acceptable in development!"
            )
            self._salt = secrets.token_bytes(32)
            logger.info(f"Generated random salt for development session (length: {len(self._salt)} bytes)")
        else:
            if len(salt_env) < 32:
                raise ValueError(
                    f"API_KEY_SALT must be at least 32 characters (current: {len(salt_env)})"
                )
            self._salt = salt_env.encode()
    
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
            self._keys[key_hash] = metadata
            return key_hash
    
    def load_keys(self) -> None:
        """Load API keys from environment."""
        master_key = os.getenv("DASHBOARD_API_KEY")
        if master_key:
            self.add_key(master_key, {
                "name": "master",
                "created": datetime.now().isoformat(),
                "scopes": ["read", "write", "admin"],
            })


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
