"""JWT token creation and verification."""

import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, NamedTuple, Optional, cast

import jwt
from fastapi import HTTPException, status
from jwt.exceptions import InvalidTokenError as JWTError
from loguru import logger

from .token_blacklist import check_blacklisted, get_token_blacklist

# Supported JWT algorithms whitelist
SUPPORTED_JWT_ALGORITHMS = frozenset(
    {"HS256", "HS384", "HS512", "RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}
)


class JWTSettings(NamedTuple):
    """JWT configuration settings."""

    secret_key: str
    algorithm: str
    expire_hours: int


# TTL-based cache for JWT settings (replaces lru_cache for key rotation support)
_jwt_settings_cache: Optional[JWTSettings] = None
_jwt_settings_cache_time: float = 0
_JWT_SETTINGS_TTL: int = 300  # 5 minutes TTL


def _get_jwt_settings() -> JWTSettings:
    """
    Get JWT settings with lazy initialization and TTL-based cache.

    This replaces lru_cache to support key rotation without server restart.
    Settings are cached for 5 minutes, then refreshed from environment.

    Returns:
        JWTSettings named tuple with secret_key, algorithm, and expire_hours

    Raises:
        ValueError: If API_SECRET_KEY is not set or invalid
    """
    global _jwt_settings_cache, _jwt_settings_cache_time

    now = time.monotonic()

    # Return cached settings if still valid
    if _jwt_settings_cache is not None and (now - _jwt_settings_cache_time) < _JWT_SETTINGS_TTL:
        return _jwt_settings_cache

    # Load fresh settings from environment
    secret_key = os.getenv("API_SECRET_KEY")
    if not secret_key:
        raise ValueError(
            "API_SECRET_KEY environment variable must be set. "
            "Generate a secure random key with: "
            "python -c 'import secrets; print(secrets.token_urlsafe(48))'"
        )

    # Minimum 64 characters for 256-bit security
    MIN_SECRET_KEY_LENGTH = 64
    if len(secret_key) < MIN_SECRET_KEY_LENGTH:
        raise ValueError(
            f"API_SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters for security. "
            "Generate a secure random key with: "
            "python -c 'import secrets; print(secrets.token_urlsafe(48))'"
        )

    algorithm = os.getenv("JWT_ALGORITHM", "HS256")

    # Validate algorithm against whitelist
    if algorithm not in SUPPORTED_JWT_ALGORITHMS:
        raise ValueError(
            f"Unsupported JWT algorithm: {algorithm}. "
            f"Supported algorithms: {', '.join(sorted(SUPPORTED_JWT_ALGORITHMS))}"
        )

    try:
        expire_hours = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
    except (ValueError, TypeError):
        raise ValueError("JWT_EXPIRY_HOURS environment variable must be a valid integer")

    # Update cache
    _jwt_settings_cache = JWTSettings(
        secret_key=secret_key, algorithm=algorithm, expire_hours=expire_hours
    )
    _jwt_settings_cache_time = now

    return _jwt_settings_cache


def invalidate_jwt_settings_cache() -> None:
    """
    Invalidate JWT settings cache.

    This forces a reload of settings from environment on next access.
    Useful for testing or when key rotation is performed.
    """
    global _jwt_settings_cache, _jwt_settings_cache_time
    _jwt_settings_cache = None
    _jwt_settings_cache_time = 0


def get_secret_key() -> str:
    """Get the JWT secret key."""
    return _get_jwt_settings().secret_key


def get_algorithm() -> str:
    """Get the JWT algorithm."""
    return _get_jwt_settings().algorithm


def get_token_expire_hours() -> int:
    """Get the JWT token expiry hours."""
    return _get_jwt_settings().expire_hours


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create JWT access token with key version tracking.

    Args:
        data: Data to encode in token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token

    """
    secret_key = get_secret_key()
    algorithm = get_algorithm()
    expire_hours = get_token_expire_hours()
    key_version = os.getenv("API_KEY_VERSION", "1")

    to_encode = data.copy()

    # Generate unique token ID for blacklist support
    jti = str(uuid.uuid4())

    # Set timestamps
    iat = datetime.now(timezone.utc)
    if expires_delta:
        expire = iat + expires_delta
    else:
        expire = iat + timedelta(hours=expire_hours)

    # Add standard and custom claims
    to_encode.update(
        {"exp": expire, "iat": iat, "jti": jti, "type": "access", "key_version": key_version}
    )

    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    # PyJWT >= 2.0 always returns str, but defensive bytes check kept for safety
    if isinstance(encoded_jwt, bytes):
        return encoded_jwt.decode()
    return str(encoded_jwt)


async def _check_token_blacklist(payload: Dict[str, Any]) -> None:
    """
    Check if token is blacklisted.

    Args:
        payload: JWT payload containing jti

    Raises:
        HTTPException: If token is blacklisted
    """
    jti = payload.get("jti")
    if jti and await check_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode JWT token with key rotation support.

    First tries to verify with current API_SECRET_KEY.
    If that fails, falls back to API_SECRET_KEY_PREVIOUS for backward compatibility
    during key rotation periods.

    Args:
        token: JWT token to verify

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    secret_key = get_secret_key()
    algorithm = get_algorithm()

    # Try current key first
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])

        # Check if token is blacklisted using helper
        await _check_token_blacklist(payload)

        return cast(dict[str, Any], payload)
    except JWTError as primary_error:
        # Try previous key for rotation support
        previous_key = os.getenv("API_SECRET_KEY_PREVIOUS")
        if previous_key:
            try:
                logger.debug("Attempting token verification with previous key")
                payload = jwt.decode(token, previous_key, algorithms=[algorithm])

                # Check blacklist for old key tokens too using helper
                await _check_token_blacklist(payload)

                # Check if token exceeds rotation max age
                rotation_max_hours = int(os.getenv("API_SECRET_KEY_ROTATION_MAX_HOURS", "72"))
                if "iat" in payload:
                    issued_at = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
                    age = datetime.now(timezone.utc) - issued_at
                    max_age = timedelta(hours=rotation_max_hours)

                    if age > max_age:
                        logger.warning(
                            f"Token verified with previous key but exceeds rotation max age "
                            f"({age.total_seconds()/3600:.1f}h > {rotation_max_hours}h), rejecting"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Token too old for previous key verification",
                            headers={"WWW-Authenticate": "Bearer"},
                        )

                logger.info("Token verified with previous key - consider refreshing token")
                return cast(dict[str, Any], payload)
            except JWTError:
                # Both keys failed, raise original error
                pass

        # Production: Don't expose internal error details for security
        if os.getenv("ENV", "production").lower() == "production":
            detail = "Could not validate credentials"
        else:
            detail = f"Could not validate credentials: {str(primary_error)}"

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


async def revoke_token(token: str) -> bool:
    """
    Revoke a JWT token by adding it to the blacklist.

    Args:
        token: JWT token to revoke

    Returns:
        True if token was successfully revoked

    Raises:
        HTTPException: If token is invalid or already expired
    """
    try:
        # Decode without verifying to get claims (we just need jti and exp)
        secret_key = get_secret_key()
        algorithm = get_algorithm()
        payload = jwt.decode(
            token, secret_key, algorithms=[algorithm], options={"verify_exp": False}
        )

        jti = payload.get("jti")
        if not jti:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token does not contain jti claim",
            )

        exp = payload.get("exp")
        if not exp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token does not contain exp claim",
            )

        # Convert exp to datetime
        exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)

        # Add to blacklist (use async method if available)
        blacklist = get_token_blacklist()
        if hasattr(blacklist, "add_async"):
            # PersistentTokenBlacklist
            await blacklist.add_async(jti, exp_dt)
        else:
            # Regular TokenBlacklist
            blacklist.add(jti, exp_dt)

        logger.info(f"Token {jti[:8]}... revoked successfully")
        return True

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid token: {str(e)}",
        )
