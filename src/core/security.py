"""Security middleware for web dashboard."""

import secrets
import hashlib
import hmac
import os
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

# API Key management
API_KEYS: Dict[str, Dict[str, Any]] = {
    # Format: "key_hash": {"name": "admin", "created": "2024-01-09", "scopes": ["read", "write"]}
}

# Salt for API key hashing (should be set via environment variable in production)
_API_KEY_SALT: Optional[bytes] = None


def _get_api_key_salt() -> bytes:
    """Get or generate API key salt."""
    global _API_KEY_SALT
    if _API_KEY_SALT is None:
        salt_env = os.getenv("API_KEY_SALT")
        if salt_env:
            _API_KEY_SALT = salt_env.encode()
        else:
            # Default salt for backward compatibility - should be overridden in production
            _API_KEY_SALT = b"vfs-bot-default-salt-change-in-production"
    return _API_KEY_SALT


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
    salt = _get_api_key_salt()
    return hmac.new(salt, api_key.encode(), hashlib.sha256).hexdigest()


def load_api_keys() -> None:
    """Load API keys from environment or file."""
    # Load from environment
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
    api_key = credentials.credentials
    key_hash = hash_api_key(api_key)

    if key_hash not in API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return API_KEYS[key_hash]


# Initialize API keys on module load
load_api_keys()
