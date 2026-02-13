"""Password hashing and validation."""

import os
import re

from src.core.environment import Environment

from ...core.exceptions import ValidationError

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

    Raises:
        ValueError: If unable to truncate to valid UTF-8 boundary
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
        # This should never happen with valid UTF-8 input, but handle it safely
        raise ValueError("Failed to truncate password to valid UTF-8 boundary")
    return password


def validate_password_length(password: str) -> None:
    """
    Validate password doesn't exceed bcrypt limit.

    Raises ValidationError if password exceeds the maximum length,
    providing clear feedback to users instead of silently truncating.

    Args:
        password: Password to validate

    Raises:
        ValidationError: If password exceeds maximum byte length
    """
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        raise ValidationError(
            f"Password exceeds maximum length of {MAX_PASSWORD_BYTES} bytes. "
            f"Current length: {len(password_bytes)} bytes. "
            "Please use a shorter password.",
            field="password",
        )


def validate_password_complexity(password: str) -> None:
    """
    Validate password meets complexity requirements.

    Requirements:
    - At least 12 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Args:
        password: Password to validate

    Raises:
        ValidationError: If password doesn't meet requirements
    """
    errors = []

    if len(password) < 12:
        errors.append("Password must be at least 12 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")
    if not re.search(r"[0-9]", password):
        errors.append("Password must contain at least one digit")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special character")

    if errors:
        raise ValidationError("; ".join(errors), field="password")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password

    Raises:
        ValidationError: If password exceeds maximum byte length
    """
    validate_password_length(password)  # Validate before hashing
    # Truncate for bcrypt (defensive - validation should prevent this case)
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


def validate_admin_password_format() -> bool:
    """
    Validate that ADMIN_PASSWORD is in bcrypt hash format in production.

    This function should be called at startup to ensure the admin password
    is properly hashed in production environments.

    Returns:
        True if validation passes

    Raises:
        ValueError: If ADMIN_PASSWORD is not properly formatted in production
    """
    admin_password = os.getenv("ADMIN_PASSWORD")

    # Skip validation if no password is set (optional var)
    if not admin_password:
        return True

    # In production, require bcrypt hash format
    if Environment.is_production():
        bcrypt_prefixes = ("$2b$", "$2a$", "$2y$")
        if not admin_password.startswith(bcrypt_prefixes):
            raise ValueError(
                "ADMIN_PASSWORD must be bcrypt hashed in production environment. "
                "Current value appears to be plain text. "
                'Generate a hash using: python -c "from passlib.context import CryptContext; '
                "print(CryptContext(schemes=['bcrypt']).hash('your-password'))\""
            )

    return True
