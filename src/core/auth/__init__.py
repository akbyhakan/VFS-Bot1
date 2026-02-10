"""JWT-based authentication for API endpoints.

This module has been refactored into a modular package structure for better
maintainability and separation of concerns.
"""

from .rate_limiter import (
    RateLimiterBackend,
    InMemoryBackend,
    RedisBackend,
    AuthRateLimiter,
    get_auth_rate_limiter,
)
from .token_blacklist import (
    TokenBlacklist,
    PersistentTokenBlacklist,
    get_token_blacklist,
    init_token_blacklist,
    check_blacklisted,
)
from .jwt_tokens import (
    SUPPORTED_JWT_ALGORITHMS,
    JWTSettings,
    _get_jwt_settings,
    invalidate_jwt_settings_cache,
    get_secret_key,
    get_algorithm,
    get_token_expire_hours,
    create_access_token,
    verify_token,
    revoke_token,
)
from .password import (
    MAX_PASSWORD_BYTES,
    pwd_context,
    _truncate_password,
    validate_password_length,
    validate_password_complexity,
    hash_password,
    verify_password,
    validate_admin_password_format,
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
