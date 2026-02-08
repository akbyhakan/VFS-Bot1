"""Secure memory handling utilities for sensitive data."""

import ctypes
import logging
from typing import Union

logger = logging.getLogger(__name__)


def secure_zero_memory(data: Union[bytearray, bytes, str]) -> None:
    """
    Securely zero out memory containing sensitive data.

    IMPORTANT SECURITY NOTES:
    - Only ``bytearray`` objects can be reliably zeroed in-place.
    - ``bytes`` and ``str`` are immutable in Python; passing them here will
      only zero a *copy*, leaving the original intact in memory.  A warning
      is logged when this happens so callers can migrate to ``bytearray``.

    Args:
        data: Sensitive data to zero out. Prefer ``bytearray`` for real security.
    """
    if data is None:
        return

    if isinstance(data, str):
        logger.warning(
            "secure_zero_memory called with 'str' — immutable objects cannot be "
            "securely zeroed. Convert to bytearray before calling this function."
        )
        return

    if isinstance(data, bytes):
        logger.warning(
            "secure_zero_memory called with 'bytes' — immutable objects cannot be "
            "securely zeroed. Convert to bytearray before calling this function."
        )
        return

    # bytearray — can actually be zeroed in-place
    if isinstance(data, bytearray) and len(data) > 0:
        try:
            ctypes.memset(
                ctypes.addressof((ctypes.c_char * len(data)).from_buffer(data)),
                0,
                len(data),
            )
        except Exception:
            # Fallback: manually zero each byte
            for i in range(len(data)):
                data[i] = 0


class SecureCVV:
    """Context manager for handling CVV securely in memory."""

    def __init__(self, cvv: str):
        """
        Initialize with CVV string.

        Args:
            cvv: CVV code to handle securely
        """
        self._data = bytearray(cvv.encode("utf-8"))

    def __enter__(self) -> str:
        """Return CVV as string when entering context."""
        return self._data.decode("utf-8")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Securely clear CVV from memory when exiting context."""
        secure_zero_memory(self._data)
        self._data = bytearray()
        return False
