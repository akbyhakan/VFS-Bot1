"""Retry strategies for different exception types."""

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    wait_fixed,
)

from .exceptions import (
    LoginError,
    CaptchaError,
    NetworkError,
    SlotCheckError,
    RateLimitError,
)


def get_login_retry():
    """
    Get retry strategy for login operations.

    Returns:
        Retry decorator configured for login errors
    """
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=30),
        retry=retry_if_exception_type((LoginError, NetworkError)),
        reraise=True,
    )


def get_captcha_retry():
    """
    Get retry strategy for captcha solving.

    Returns:
        Retry decorator configured for captcha errors
    """
    return retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type(CaptchaError),
        reraise=True,
    )


def get_slot_check_retry():
    """
    Get retry strategy for slot checking.

    Returns:
        Retry decorator configured for slot check errors
    """
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=3, max=20),
        retry=retry_if_exception_type((SlotCheckError, NetworkError)),
        reraise=True,
    )


def get_network_retry():
    """
    Get retry strategy for network operations.

    Returns:
        Retry decorator configured for network errors
    """
    return retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type(NetworkError),
        reraise=True,
    )


def get_rate_limit_retry():
    """
    Get retry strategy for rate limit errors.

    Returns:
        Retry decorator configured for rate limit errors
    """
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(60),  # Wait 60 seconds between retries
        retry=retry_if_exception_type(RateLimitError),
        reraise=True,
    )
