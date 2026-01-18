"""Security middleware for web dashboard."""

import secrets
import hashlib
import hmac
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

security = HTTPBearer()

# API Key management
API_KEYS: Dict[str, Dict[str, Any]] = {
    # Format: "key_hash": {"name": "admin", "created": "2024-01-09", "scopes": ["read", "write"]}
}

# Salt for API key hashing (should be set via environment variable in production)
_API_KEY_SALT: Optional[bytes] = None


def _get_api_key_salt() -> bytes:
    """Get API key salt from environment variable - REQUIRED in production."""
    global _API_KEY_SALT
    if _API_KEY_SALT is None:
        salt_env = os.getenv("API_KEY_SALT")
        env = os.getenv("ENV", "production").lower()
        
        if not salt_env:
            if env == "production":
                raise ValueError(
                    "API_KEY_SALT environment variable MUST be set in production. "
                    "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
            else:
                # Development only - log warning
                logger.warning(
                    "⚠️ SECURITY WARNING: API_KEY_SALT not set. "
                    "Using insecure default. This is only acceptable in development!"
                )
                _API_KEY_SALT = b"dev-only-insecure-salt-do-not-use-in-prod"
        else:
            if len(salt_env) < 32:
                raise ValueError(
                    f"API_KEY_SALT must be at least 32 characters (current: {len(salt_env)}). "
                    "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
            _API_KEY_SALT = salt_env.encode()
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
