"""JWT-based authentication for API endpoints."""

import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bcrypt has a maximum password length of 72 bytes
MAX_PASSWORD_BYTES = 72

# JWT settings from environment
_secret_key = os.getenv("API_SECRET_KEY")
if not _secret_key:
    raise ValueError(
        "API_SECRET_KEY environment variable must be set. "
        "Generate a secure random key with: "
        "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )
SECRET_KEY = _secret_key
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Validate and convert JWT_EXPIRY_HOURS
try:
    ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
except (ValueError, TypeError):
    raise ValueError("JWT_EXPIRY_HOURS environment variable must be a valid integer")


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create JWT access token.

    Args:
        data: Data to encode in token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token

    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    # Ensure we return a str (jwt.encode should return str, but cast for mypy)
    return str(encoded_jwt)


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode JWT token.

    Args:
        token: JWT token to verify

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Cast to Dict[str, Any] for type safety
        return dict(payload)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    # Truncate password to 72 bytes to comply with bcrypt limitations
    # We need to ensure we don't split multi-byte UTF-8 characters
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        # Truncate bytes, then find the last valid UTF-8 character boundary
        truncated_bytes = password_bytes[:MAX_PASSWORD_BYTES]
        # Decode with 'ignore' to drop incomplete trailing characters
        truncated_password = truncated_bytes.decode("utf-8", errors="ignore")
    else:
        truncated_password = password

    hashed = pwd_context.hash(truncated_password)
    # Ensure we return a str (pwd_context.hash should return str, but cast for mypy)
    return str(hashed)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        True if password matches
    """
    # Truncate password to 72 bytes to comply with bcrypt limitations
    # We need to ensure we don't split multi-byte UTF-8 characters
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        # Truncate bytes, then find the last valid UTF-8 character boundary
        truncated_bytes = password_bytes[:MAX_PASSWORD_BYTES]
        # Decode with 'ignore' to drop incomplete trailing characters
        truncated_password = truncated_bytes.decode("utf-8", errors="ignore")
    else:
        truncated_password = plain_password

    result = pwd_context.verify(truncated_password, hashed_password)
    # Ensure we return a bool (pwd_context.verify should return bool, but cast for mypy)
    return bool(result)
