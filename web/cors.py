"""CORS validation utilities for FastAPI web application."""

import re
from typing import List
from urllib.parse import urlparse

from loguru import logger

from src.core.environment import Environment
from src.utils.log_sanitizer import sanitize_log_value

# Patterns for dangerous hosts (exact hostname checks)
_DANGEROUS_HOST_RE = re.compile(
    r"^(localhost|127\.\d+\.\d+\.\d+|0\.0\.0\.0|::1)$", re.IGNORECASE
)
# Patterns for subdomain bypass: hostname starts with "localhost." or ends with ".localhost"
_LOCALHOST_SUBDOMAIN_RE = re.compile(
    r"(^localhost\.|\.localhost$)", re.IGNORECASE
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


def validate_cors_origins(origins_str: str) -> List[str]:
    """
    Parse and validate CORS origins from comma-separated string.

    In production, dangerous origins (wildcard, localhost, 127.x, 0.0.0.0,
    IPv6 loopback, localhost subdomain bypasses) are rejected.
    In non-production environments all origins are allowed.

    Args:
        origins_str: Comma-separated list of allowed origins

    Returns:
        List of validated origin strings

    Raises:
        ValueError: If wildcard "*" is used in production
    """
    origins = [origin.strip() for origin in origins_str.split(",") if origin.strip()]

    if not Environment.is_production():
        return origins

    # Production: enforce security rules
    if "*" in origins:
        raise ValueError(
            "Wildcard '*' CORS origin is not allowed in production. "
            "Specify explicit allowed origins."
        )

    allowed = []
    for origin in origins:
        hostname = urlparse(origin).hostname or ""
        if _DANGEROUS_HOST_RE.match(hostname):
            logger.warning(
                f"Blocking dangerous CORS origin: {sanitize_log_value(origin, max_length=100)}"
            )
            continue
        if _LOCALHOST_SUBDOMAIN_RE.search(hostname):
            logger.warning(
                f"Blocking localhost subdomain bypass CORS origin: "
                f"{sanitize_log_value(origin, max_length=100)}"
            )
            continue
        allowed.append(origin)
    return allowed
