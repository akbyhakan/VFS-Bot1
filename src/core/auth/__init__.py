"""JWT-based authentication for API endpoints.

This module has been refactored into a modular package structure for better
maintainability and separation of concerns.
"""

from src.core.rate_limiting import (
    AuthRateLimiter,
    InMemoryBackend,
    RateLimiterBackend,
    RedisBackend,
    get_auth_rate_limiter,
)

from .jwt_tokens import (
    SUPPORTED_JWT_ALGORITHMS,
    JWTSettings,
    _get_jwt_settings,
    create_access_token,
    get_algorithm,
    get_secret_key,
    get_token_expire_hours,
    invalidate_jwt_settings_cache,
    revoke_token,
    verify_token,
    verify_token_allow_expired,
)
from .password import (
    MAX_PASSWORD_BYTES,
    _truncate_password,
    hash_password,
    pwd_context,
    validate_admin_password_format,
    validate_password_complexity,
    validate_password_length,
    verify_password,
)
from .token_blacklist import (
    PersistentTokenBlacklist,
    TokenBlacklist,
    check_blacklisted,
    get_token_blacklist,
    init_token_blacklist,
)

__all__ = [
    # Rate limiter
    "RateLimiterBackend",
    "InMemoryBackend",
    "RedisBackend",
    "AuthRateLimiter",
    "get_auth_rate_limiter",
    # Token blacklist
    "TokenBlacklist",
    "PersistentTokenBlacklist",
    "get_token_blacklist",
    "init_token_blacklist",
    "check_blacklisted",
    # JWT tokens
    "SUPPORTED_JWT_ALGORITHMS",
    "JWTSettings",
    "_get_jwt_settings",
    "invalidate_jwt_settings_cache",
    "get_secret_key",
    "get_algorithm",
    "get_token_expire_hours",
    "create_access_token",
    "verify_token",
    "verify_token_allow_expired",
    "revoke_token",
    # Password
    "MAX_PASSWORD_BYTES",
    "pwd_context",
    "_truncate_password",
    "validate_password_length",
    "validate_password_complexity",
    "hash_password",
    "verify_password",
    "validate_admin_password_format",
]
