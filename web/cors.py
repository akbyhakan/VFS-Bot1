"""CORS validation utilities for FastAPI web application."""

import re
from typing import List

from loguru import logger

from src.core.environment import Environment
from src.utils.log_sanitizer import sanitize_log_value

# Comprehensive localhost detection pattern
_LOCALHOST_PATTERN = re.compile(
    r"^https?://"
    r"(localhost(\.|:|/|$)|127\.0\.0\.1|(\[::1\]|::1)|0\.0\.0\.0)"
    r"(:\d+)?"
    r"(/.*)?$",
    re.IGNORECASE,
)


def get_validated_environment() -> str:
    """
    Get and validate environment name with whitelist check.

    Returns:
        Validated environment name (defaults to 'production' for unknown values)
    """
    env = Environment.current_raw()
    if env not in Environment.VALID:
        logger.warning(
            f"Unknown environment '{sanitize_log_value(env, max_length=50)}', "
            f"defaulting to 'production' for security"
        )
        return "production"
    return env


def _is_localhost_origin(origin: str) -> bool:
    """Check if origin is a localhost variant (including IPv6)."""
    # Check for localhost subdomains and variations
    # Extract hostname after protocol to avoid false positives
    if "://" in origin:
        # Extract the part after protocol (hostname and possibly port/path)
        after_protocol = origin.split("://", 1)[1]
        # Extract just the hostname (before port or path)
        hostname = after_protocol.split(":")[0].split("/")[0].lower()
        # Check if hostname starts with 'localhost.' or ends with '.localhost'
        if hostname.startswith("localhost.") or hostname.endswith(".localhost"):
            return True
    return bool(_LOCALHOST_PATTERN.match(origin))


def validate_cors_origins(origins_str: str) -> List[str]:
    """
    Validate and parse CORS origins, blocking wildcard and localhost in production.

    Args:
        origins_str: Comma-separated list of allowed origins

    Returns:
        List of validated origin strings

    Raises:
        ValueError: If wildcard is used in production environment
    """
    env = get_validated_environment()

    # Parse origins first
    origins = [origin.strip() for origin in origins_str.split(",") if origin.strip()]

    # Fail-fast: Block wildcard in production BEFORE filtering
    if env == "production" and "*" in origins:
        raise ValueError("Wildcard CORS origin ('*') not allowed in production")

    # Production-specific validation
    if env not in {"development", "dev", "testing", "test", "local"}:
        # More precise localhost detection
        invalid = []
        for o in origins:
            # Check for wildcard
            if o == "*":
                invalid.append(o)
            # Check for localhost variants (including IPv6, 0.0.0.0, subdomain bypass)
            elif _is_localhost_origin(o):
                invalid.append(o)

        if invalid:
            logger.warning(f"Removing insecure CORS origins in production: {invalid}")
            origins = [o for o in origins if o not in invalid]

            if not origins:
                logger.error("All CORS origins were insecure and removed. Using empty list.")

    return origins
