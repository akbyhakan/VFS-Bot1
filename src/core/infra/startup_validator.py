"""Startup security validator - prevents running with insecure defaults."""

import os
from typing import List

from loguru import logger

from src.core.environment import Environment

# Known dangerous default values that should never be used in production
# These are exact placeholder values from .env.example
DANGEROUS_DEFAULTS = frozenset(
    {
        "your-secret-key-here-must-be-at-least-64-characters-long-for-security",
        "your-base64-encoded-encryption-key-here",
        "your-32-byte-encryption-key-here",
        "your-secure-api-key-here",
        "one-time-secret-for-key-generation",
        "your-api-key-here",
        "change-me",
        "CHANGE_ME",
        "changeme",
    }
)


def validate_production_security() -> List[str]:
    """
    Validate critical security settings before starting in production.

    Returns:
        List of warning messages for insecure configurations
    """
    Environment.current()
    warnings: List[str] = []

    if not Environment.is_production_or_staging():
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
            "ADMIN_PASSWORD is not a bcrypt hash. " "Run: python scripts/setup_environment.py"
        )

    # Check for dangerous default values in security-critical env vars
    security_vars = {
        "API_SECRET_KEY": 64,
        "ENCRYPTION_KEY": 32,
        "VFS_ENCRYPTION_KEY": 32,
        "DASHBOARD_API_KEY": 32,
        "ADMIN_SECRET": 32,
    }
    for key, min_length in security_vars.items():
        value = os.getenv(key, "")
        if value in DANGEROUS_DEFAULTS or (value and len(value) < min_length):
            warnings.append(
                f"{key} appears to be a default or weak value "
                f"(minimum {min_length} characters required)."
            )

    # Check DATABASE_URL for dangerous defaults (substring match)
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        warnings.append("DATABASE_URL is empty. Set a valid database connection string.")
    elif database_url in DANGEROUS_DEFAULTS or any(
        pattern in database_url for pattern in ("CHANGE_ME", "change_me", "changeme")
    ):
        warnings.append(
            "DATABASE_URL contains a default/placeholder password. "
            "Generate a secure password with: "
            'python -c "import secrets; print(secrets.token_urlsafe(24))"'
        )

    # Check POSTGRES_PASSWORD
    postgres_password = os.getenv("POSTGRES_PASSWORD", "")
    if postgres_password and any(
        pattern in postgres_password for pattern in ("CHANGE_ME", "change_me", "changeme")
    ):
        warnings.append(
            "POSTGRES_PASSWORD contains a default/placeholder value. "
            "Generate a secure password with: "
            'python -c "import secrets; print(secrets.token_urlsafe(24))"'
        )

    # Check REDIS_PASSWORD
    redis_password = os.getenv("REDIS_PASSWORD", "")
    if redis_password and any(
        pattern in redis_password for pattern in ("CHANGE_ME", "change_me", "changeme")
    ):
        warnings.append(
            "REDIS_PASSWORD contains a default/placeholder value. "
            "Generate a secure password with: "
            'python -c "import secrets; print(secrets.token_urlsafe(24))"'
        )

    # Check GRAFANA_ADMIN_PASSWORD
    grafana_password = os.getenv("GRAFANA_ADMIN_PASSWORD", "")
    if grafana_password:
        # Exact match for known default passwords
        if grafana_password in ("vfsbot_grafana", "admin", "password", "grafana"):
            warnings.append(
                "GRAFANA_ADMIN_PASSWORD is set to a common default password. "
                "Generate a secure password with: "
                'python -c "import secrets; print(secrets.token_urlsafe(16))"'
            )
        # Substring match for placeholder patterns
        elif any(pattern in grafana_password for pattern in ("CHANGE_ME", "change_me", "changeme")):
            warnings.append(
                "GRAFANA_ADMIN_PASSWORD contains a default/placeholder value. "
                "Generate a secure password with: "
                'python -c "import secrets; print(secrets.token_urlsafe(16))"'
            )

    return warnings


def log_security_warnings(strict: bool = False) -> bool:
    """
    Log security warnings at startup.

    Args:
        strict: If True, raise SystemExit in production/staging when warnings exist

    Returns:
        True if no critical warnings found, False otherwise

    Raises:
        SystemExit: If strict=True and warnings exist in production/staging
    """
    Environment.current()
    warnings = validate_production_security()

    if not warnings:
        logger.info("Startup security validation passed")
        return True

    # In strict mode with production/staging, use critical logging
    log_func = (
        logger.critical if (strict and Environment.is_production_or_staging()) else logger.warning
    )

    log_func("=" * 60)
    log_func("SECURITY CONFIGURATION WARNINGS")
    log_func("=" * 60)
    for warning in warnings:
        log_func(f"⚠️  {warning}")
    log_func("=" * 60)
    log_func("Fix these issues or set ENV=development to suppress these warnings.")

    # In strict mode, exit if in production or staging
    if strict and Environment.is_production_or_staging():
        logger.critical("CRITICAL: Exiting due to security warnings in strict mode")
        raise SystemExit(1)

    return False
