"""Security-related constants."""

from typing import Final


class Security:
    """Security configuration."""

    MIN_SECRET_KEY_LENGTH: Final[int] = 64
    MIN_API_KEY_SALT_LENGTH: Final[int] = 32
    MIN_ENCRYPTION_KEY_LENGTH: Final[int] = 32
    # Supported: HS256, HS384, HS512, RS256, RS384, RS512, ES256, ES384, ES512
    JWT_ALGORITHM: Final[str] = "HS384"
    JWT_EXPIRY_HOURS: Final[int] = 24
    PASSWORD_HASH_ROUNDS: Final[int] = 12
    MAX_LOGIN_ATTEMPTS: Final[int] = 5
    LOCKOUT_DURATION_MINUTES: Final[int] = 15
    SESSION_FILE_PERMISSIONS: Final[int] = 0o600


# Allowed fields for personal_details table (SQL injection prevention)
ALLOWED_PERSONAL_DETAILS_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "passport_number",
        "passport_expiry",
        "gender",
        "mobile_code",
        "mobile_number",
        "email",
        "nationality",
        "date_of_birth",
        "address_line1",
        "address_line2",
        "state",
        "city",
        "postcode",
    }
)

# Allowed fields for vfs_account_pool table update (SQL injection prevention)
ALLOWED_VFS_ACCOUNT_UPDATE_FIELDS = frozenset(
    {
        "email",
        "password",
        "phone",
        "is_active",
    }
)

# Backward compatibility alias
ALLOWED_USER_UPDATE_FIELDS = ALLOWED_VFS_ACCOUNT_UPDATE_FIELDS
