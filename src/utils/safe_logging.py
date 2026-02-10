"""Safe logging utilities for protecting sensitive data."""

import logging as _stdlib_logging
import re
from typing import Any, Dict, List, Pattern

from loguru import logger


class SafeException:
    """Utility class for safely logging exceptions without exposing sensitive data."""

    SENSITIVE_PATTERNS: List[str] = [
        "token",
        "password",
        "secret",
        "auth",
        "credential",
        "api_key",
        "apikey",
        "bearer",
        "cookie",
        "session",
        "cvv",
        "card",
        "ssn",
        "social_security",
    ]

    # Precompile regex patterns for better performance
    _compiled_patterns: List[Pattern] = []

    @classmethod
    def _get_patterns(cls) -> List[Pattern]:
        """Get or create compiled regex patterns."""
        if not cls._compiled_patterns:
            for pattern in cls.SENSITIVE_PATTERNS:
                # Match pattern followed by assignment operator and value
                # Examples: token=abc123, password: "secret", api_key='key123'
                regex = rf"({pattern}['\"]?\s*[:=]\s*['\"]?)([^'\"\s,}}]+)"
                cls._compiled_patterns.append(re.compile(regex, flags=re.IGNORECASE))
        return cls._compiled_patterns

    @classmethod
    def safe_str(cls, exception: Exception) -> str:
        """
        Convert exception to string with sensitive data redacted.

        Args:
            exception: Exception to convert

        Returns:
            Safe string representation with sensitive data masked
        """
        msg = str(exception)

        # Apply all patterns
        for pattern in cls._get_patterns():
            msg = pattern.sub(r"\1[REDACTED]", msg)

        return msg

    @classmethod
    def safe_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a copy of dictionary with sensitive values redacted.

        Args:
            data: Dictionary to sanitize

        Returns:
            New dictionary with sensitive values masked
        """
        if not isinstance(data, dict):
            return data

        sanitized: Dict[str, Any] = {}
        for key, value in data.items():
            key_lower = key.lower()

            # Check if key contains sensitive pattern
            is_sensitive = any(pattern in key_lower for pattern in cls.SENSITIVE_PATTERNS)

            if is_sensitive:
                # Always use full redaction for security
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                # Recursively sanitize nested dictionaries
                sanitized[key] = cls.safe_dict(value)
            elif isinstance(value, list):
                # Sanitize lists
                sanitized[key] = [
                    cls.safe_dict(item) if isinstance(item, dict) else item for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized

    @classmethod
    def safe_log(
        cls, logger_instance: _stdlib_logging.Logger, level: int, message: str, exc_info: Any = None
    ) -> None:
        """
        Log message with automatic sensitive data redaction.

        Args:
            logger_instance: Logger instance to use
            level: Log level (logging.INFO, logging.ERROR, etc.)
            message: Message to log
            exc_info: Optional exception info to log
        """
        # Sanitize message
        safe_message = message
        for pattern in cls._get_patterns():
            safe_message = pattern.sub(r"\1[REDACTED]", safe_message)

        # Sanitize exception if provided
        if exc_info and isinstance(exc_info, Exception):
            exc_info = cls.safe_str(exc_info)

        logger_instance.log(level, safe_message, exc_info=exc_info)


def mask_sensitive_url(url: str) -> str:
    """
    Mask sensitive parts of URLs (query parameters, tokens in path).

    Args:
        url: URL to mask

    Returns:
        URL with sensitive parts masked
    """
    # Mask query parameters that look sensitive
    masked = re.sub(
        r"([?&](token|key|password|secret|auth|api_key|apikey)=)[^&\s]+",
        r"\1[REDACTED]",
        url,
        flags=re.IGNORECASE,
    )

    # Mask bearer tokens in path
    masked = re.sub(r"(bearer[:/])[a-zA-Z0-9._-]+", r"\1[REDACTED]", masked, flags=re.IGNORECASE)

    return masked


def mask_email(email: str) -> str:
    """
    Mask email address for logging.

    Args:
        email: Email address to mask

    Returns:
        Partially masked email (e.g., "us***@ex***.com")
    """
    if "@" not in email:
        return email

    local, domain = email.split("@", 1)

    # Mask local part
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[:2] + "***"

    # Mask domain
    if "." in domain:
        domain_parts = domain.split(".")
        masked_domain_parts = []
        for part in domain_parts:
            if len(part) <= 2:
                masked_domain_parts.append(part)
            else:
                masked_domain_parts.append(part[:2] + "***")
        masked_domain = ".".join(masked_domain_parts)
    else:
        masked_domain = domain[:2] + "***" if len(domain) > 2 else domain

    return f"{masked_local}@{masked_domain}"


def mask_phone(phone: str) -> str:
    """
    Mask phone number for logging.

    Args:
        phone: Phone number to mask

    Returns:
        Partially masked phone number (last 4 digits visible)
    """
    # Remove non-digit characters
    digits = re.sub(r"\D", "", phone)

    if len(digits) <= 4:
        return "***" + digits

    return "***" + digits[-4:]


def mask_credit_card(card_number: str) -> str:
    """
    Mask credit card number for logging.

    Args:
        card_number: Credit card number to mask

    Returns:
        Masked credit card number (only last 4 digits visible)
    """
    # Remove spaces and dashes
    digits = re.sub(r"[\s-]", "", card_number)

    if len(digits) <= 4:
        return "****" + digits

    return "****" + digits[-4:]
