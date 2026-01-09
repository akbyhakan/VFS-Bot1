"""Security middleware for web dashboard."""

import secrets
import hashlib
import os
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

# API Key management
API_KEYS: Dict[str, Dict[str, Any]] = {
    # Format: "key_hash": {"name": "admin", "created": "2024-01-09", "scopes": ["read", "write"]}
}


def generate_api_key() -> str:
    """
    Generate a new API key.

    Returns:
        Secure random API key
    """
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """
    Hash API key for storage.

    Args:
        api_key: API key to hash

    Returns:
        SHA256 hash of the API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


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
