"""CORS validation utilities for FastAPI web application."""

from typing import List

from loguru import logger

from src.core.environment import Environment
from src.utils.log_sanitizer import sanitize_log_value


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
    Parse CORS origins from comma-separated string.

    Args:
        origins_str: Comma-separated list of allowed origins

    Returns:
        List of origin strings
    """
    return [origin.strip() for origin in origins_str.split(",") if origin.strip()]
