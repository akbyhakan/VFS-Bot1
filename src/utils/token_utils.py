"""Token utility functions for handling token expiry calculations."""

import logging

logger = logging.getLogger(__name__)


def calculate_effective_expiry(expires_in: int, buffer_minutes: int, min_expiry: int = 1) -> int:
    """
    Calculate effective expiry time with buffer.

    This function handles edge cases such as negative or zero expiry times,
    and ensures the buffer doesn't exceed the expiry time.

    Args:
        expires_in: Token expiry time in minutes from API
        buffer_minutes: Buffer time before actual expiry
        min_expiry: Minimum expiry time to return (default: 1 minute)

    Returns:
        Effective expiry time in minutes (always >= min_expiry)

    Examples:
        >>> calculate_effective_expiry(60, 5)  # 60 min expiry, 5 min buffer
        55
        >>> calculate_effective_expiry(2, 5)   # Short expiry, use 50% buffer
        1
        >>> calculate_effective_expiry(0, 5)   # Invalid expiry, return min
        1
        >>> calculate_effective_expiry(-10, 5) # Negative expiry, return min
        1
    """
    # Ensure expires_in is positive
    expires_in = max(min_expiry, expires_in)

    # If expires_in is very short (<=2 min), use 50% of the time as buffer
    # to avoid buffer exceeding expiry time
    if expires_in <= 2:
        effective_expiry = max(min_expiry, expires_in // 2)
    else:
        # Use the configured buffer, but never more than expires_in - 1
        buffer_minutes = min(buffer_minutes, expires_in - 1)
        effective_expiry = max(min_expiry, expires_in - buffer_minutes)

    logger.debug(
        f"Token expiry calculation: expires_in={expires_in}min, "
        f"buffer={buffer_minutes}min, effective={effective_expiry}min"
    )

    return effective_expiry
