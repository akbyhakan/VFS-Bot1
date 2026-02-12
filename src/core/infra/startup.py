"""
Startup validation module.

Handles environment validation and critical dependency verification at startup.
"""

import os

from loguru import logger

from src.core.environment import Environment
from src.core.exceptions import ConfigurationError


def validate_environment():
    """Validate all required environment variables at startup."""
    env = Environment.current()

    # Always required
    required_vars = ["ENCRYPTION_KEY"]

    # Required in production
    production_required = [
        "API_SECRET_KEY",
        "API_KEY_SALT",
        "VFS_ENCRYPTION_KEY",
    ]

    missing = [var for var in required_vars if not os.getenv(var)]

    if Environment.is_production():
        missing.extend([var for var in production_required if not os.getenv(var)])

    if missing:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Please check your .env file or environment configuration."
        )

    # Validate minimum lengths
    api_secret = os.getenv("API_SECRET_KEY", "")
    if api_secret and len(api_secret) < 64:
        raise ConfigurationError(
            f"API_SECRET_KEY must be at least 64 characters (current: {len(api_secret)})"
        )

    api_key_salt = os.getenv("API_KEY_SALT", "")
    if api_key_salt and len(api_key_salt) < 32:
        raise ConfigurationError(
            f"API_KEY_SALT must be at least 32 characters (current: {len(api_key_salt)})"
        )

    logger.info("✅ Environment validation passed")


def verify_critical_dependencies():
    """Verify all critical dependencies are installed."""
    missing = []

    try:
        import curl_cffi  # noqa: F401 - PyPI package name is curl-cffi
    except ImportError:
        missing.append("curl-cffi")

    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")

    if missing:
        raise ImportError(
            f"Critical dependencies missing: {', '.join(missing)}. "
            f"Install with: pip install {' '.join(missing)}"
        )

    logger.info("✅ Critical dependencies verified")
