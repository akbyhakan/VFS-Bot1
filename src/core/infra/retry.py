"""Retry strategies for different exception types."""

import logging as stdlib_logging
from typing import Tuple, Type, Union

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
    wait_random,
)

from src.core.exceptions import (
    CaptchaError,
    LoginError,
    NetworkError,
    RateLimitError,
    SlotCheckError,
)

# Stdlib logger needed for tenacity's before_sleep_log
_stdlib_logger = stdlib_logging.getLogger(__name__)


def _make_retry(
    attempts: int,
    wait_strategy: object,
    exception_types: Union[Type[Exception], Tuple[Type[Exception], ...]],
) -> object:
    """
    Factory for creating retry decorators with consistent configuration.

    Args:
        attempts: Maximum number of retry attempts
        wait_strategy: Tenacity wait strategy
        exception_types: Exception type(s) to retry on

    Returns:
        Configured retry decorator
    """
    return retry(
        stop=stop_after_attempt(attempts),
        wait=wait_strategy,
        retry=retry_if_exception_type(exception_types),
        before_sleep=before_sleep_log(_stdlib_logger, stdlib_logging.WARNING),
        reraise=True,
    )


def get_login_retry():
    """
    Get retry strategy for login operations.

    Returns:
        Retry decorator configured for login errors
    """
    return _make_retry(
        attempts=3,
        wait_strategy=wait_exponential(multiplier=2, min=5, max=30) + wait_random(0, 3),
        exception_types=(LoginError, NetworkError),
    )


def get_captcha_retry():
    """
    Get retry strategy for captcha solving.

    Returns:
        Retry decorator configured for captcha errors
    """
    return _make_retry(
        attempts=5,
        wait_strategy=wait_exponential(multiplier=1, min=2, max=15) + wait_random(0, 2),
        exception_types=CaptchaError,
    )


def get_slot_check_retry():
    """
    Get retry strategy for slot checking.

    Returns:
        Retry decorator configured for slot check errors
    """
    return _make_retry(
        attempts=3,
        wait_strategy=wait_exponential(multiplier=1, min=3, max=20) + wait_random(0, 2),
        exception_types=(SlotCheckError, NetworkError),
    )


def get_network_retry():
    """
    Get retry strategy for network operations.

    Returns:
        Retry decorator configured for network errors
    """
    return _make_retry(
        attempts=5,
        wait_strategy=wait_exponential(multiplier=2, min=2, max=60) + wait_random(0, 5),
        exception_types=NetworkError,
    )


def get_rate_limit_retry():
    """
    Get retry strategy for rate limit errors.

    Returns:
        Retry decorator configured for rate limit errors
    """
    return _make_retry(
        attempts=3,
        wait_strategy=wait_fixed(60) + wait_random(0, 10),  # Wait 60 seconds + random jitter
        exception_types=RateLimitError,
    )


def get_telegram_retry():
    """Get retry strategy for Telegram API operations."""
    return _make_retry(
        attempts=3,
        wait_strategy=wait_exponential(multiplier=1, min=1, max=8) + wait_random(0, 1),
        exception_types=(ConnectionError, TimeoutError, OSError),
    )
