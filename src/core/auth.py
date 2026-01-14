"""JWT-based authentication for API endpoints."""

import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, cast

from jose import JWTError, jwt
from fastapi import HTTPException, status

# Bcrypt has a maximum password length of 72 bytes
MAX_PASSWORD_BYTES = 72

# Monkey-patch passlib to handle bcrypt 5.0.0 compatibility
# passlib 1.7.4's detect_wrap_bug creates a 200-char test password which exceeds
# bcrypt 5.0.0's strict 72-byte limit. We patch it to truncate test passwords.
import passlib.handlers.bcrypt as _pbcrypt  # noqa: E402


_original_calc_checksum = _pbcrypt._BcryptBackend._calc_checksum


def _patched_calc_checksum(self, secret):
    """Patched _calc_checksum that truncates passwords to 72 bytes for bcrypt 5.0.0."""
    if isinstance(secret, bytes) and len(secret) > MAX_PASSWORD_BYTES:
        # Truncate at UTF-8 character boundaries to avoid corruption
        truncated = secret[:MAX_PASSWORD_BYTES]
        # Find valid UTF-8 boundary by stepping back if needed
        for i in range(len(truncated), 0, -1):
            try:
                truncated[:i].decode("utf-8")
                secret = truncated[:i]
                break
            except UnicodeDecodeError:
                continue
    return _original_calc_checksum(self, secret)


_pbcrypt._BcryptBackend._calc_checksum = _patched_calc_checksum

# Now we can safely import and create the password context
from passlib.context import CryptContext  # noqa: E402

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings from environment
_secret_key = os.getenv("API_SECRET_KEY")
if not _secret_key:
    raise ValueError(
        "API_SECRET_KEY environment variable must be set. "
        "Generate a secure random key with: "
        "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )
if len(_secret_key) < 32:
    raise ValueError(
        "API_SECRET_KEY must be at least 32 characters for security. "
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


def _truncate_password(password: str) -> str:
    """
    Truncate password to 72 bytes for bcrypt, handling UTF-8 safely.

    Bcrypt has a maximum password length of 72 bytes. This function explicitly
    truncates passwords to 72 bytes, ensuring that multi-byte UTF-8 characters
    are handled correctly by finding valid character boundaries.

    Args:
        password: Plain text password

    Returns:
        Truncated password (max 72 bytes when encoded as UTF-8)
    """
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        # Only take complete characters that fit into MAX_PASSWORD_BYTES
        truncated_bytes = password_bytes[:MAX_PASSWORD_BYTES]
        # If decoding fails at the boundary, move back until we hit a valid boundary
        for i in range(len(truncated_bytes), 0, -1):
            try:
                return truncated_bytes[:i].decode("utf-8")
            except UnicodeDecodeError:
                continue
        # Fallback: return empty string if no valid boundary found (should never happen)
        # This would only occur if the entire password is invalid UTF-8
        return ""
    return password


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
    if isinstance(encoded_jwt, bytes):
        return encoded_jwt.decode()
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
        return cast(dict[str, Any], payload)
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
    truncated = _truncate_password(password)
    result = pwd_context.hash(truncated)
    return str(result)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        True if password matches
    """
    truncated = _truncate_password(plain_password)
    return bool(pwd_context.verify(truncated, hashed_password))
