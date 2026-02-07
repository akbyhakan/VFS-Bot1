"""Startup security validator - prevents running with insecure defaults."""

import logging
import os
from typing import List

logger = logging.getLogger(__name__)

# Known dangerous default values that should never be used in production
DANGEROUS_DEFAULTS = frozenset({
    "admin",
    "password",
    "123456",
    "admin123",
    "YOUR_SECURE_HASHED_PASSWORD_HERE",
    "your-secret-key-here-must-be-at-least-64-characters-long-for-security",
    "your-secure-api-key-here",
    "change-me",
    "secret",
})


def validate_production_security() -> List[str]:
    """
    Validate critical security settings before starting in production.

    Returns:
        List of warning messages for insecure configurations
    """
    env = os.getenv("ENV", "production").lower()
    warnings: List[str] = []

    if env not in ("production", "staging"):
        return warnings

    # Check admin username
    admin_user = os.getenv("ADMIN_USERNAME", "")
    if admin_user and admin_user.lower() in ("admin", "administrator", "root"):
        warnings.append(
            f"ADMIN_USERNAME='{admin_user}' is a common default. "
            "Change to a unique username to prevent brute-force attacks."
        )

    # Check admin password is a valid bcrypt hash
    admin_pass = os.getenv("ADMIN_PASSWORD", "")
    if admin_pass and not (
        admin_pass.startswith("$2b$")
        or admin_pass.startswith("$2a$")
        or admin_pass.startswith("$2y$")
    ):
        warnings.append(
            "ADMIN_PASSWORD is not a bcrypt hash. "
            "Run: python scripts/setup_environment.py"
        )

    # Check for dangerous default values in security-critical env vars
    security_vars = {
        "API_SECRET_KEY": 64,
        "ENCRYPTION_KEY": 32,
        "VFS_ENCRYPTION_KEY": 32,
    }
    for key, min_length in security_vars.items():
        value = os.getenv(key, "")
        if value in DANGEROUS_DEFAULTS or (value and len(value) < min_length):
            warnings.append(
                f"{key} appears to be a default or weak value "
                f"(minimum {min_length} characters required)."
            )

    return warnings


def log_security_warnings() -> bool:
    """
    Log security warnings at startup.

    Returns:
        True if no critical warnings found, False otherwise
    """
    warnings = validate_production_security()

    if not warnings:
        logger.info("Startup security validation passed")
        return True

    logger.warning("=" * 60)
    logger.warning("SECURITY CONFIGURATION WARNINGS")
    logger.warning("=" * 60)
    for warning in warnings:
        logger.warning(f"⚠️  {warning}")
    logger.warning("=" * 60)
    logger.warning(
        "Fix these issues or set ENV=development to suppress these warnings."
    )

    return False
