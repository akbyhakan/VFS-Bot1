"""Secure memory handling utilities for sensitive data."""

import ctypes
from typing import Optional, Union

from loguru import logger


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
        except Exception as e:
            logger.debug(f"ctypes memset failed, using fallback: {e}")
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


class SecureKeyContext:
    """
    Context manager for handling encryption keys securely in memory.

    Converts the key to a mutable bytearray immediately and securely
    zeroes it on exit. This minimizes the window during which the key
    exists in cleartext memory.

    SECURITY LIMITATIONS (Python language constraints):
    - The original str returned by os.getenv() is immutable and cannot be zeroed.
      It remains in memory until the garbage collector reclaims it.
    - For maximum security, disable core dumps in production:
      ulimit -c 0 or prctl(PR_SET_DUMPABLE, 0)

    Example:
        >>> with SecureKeyContext(os.getenv("SECRET_KEY")) as key_bytes:
        ...     # key_bytes is a bytearray — use it for crypto operations
        ...     cipher = AES.new(bytes(key_bytes), AES.MODE_CBC, iv)
        >>> # key_bytes is now zeroed
    """

    def __init__(self, key_str: Optional[str]):
        """
        Initialize with a key string.

        Args:
            key_str: The key string from environment variable or other source
        """
        self._key_str = key_str
        self._data: Optional[bytearray] = None

    def __enter__(self) -> bytearray:
        """
        Convert key string to bytearray and return it.

        Returns:
            Mutable bytearray containing the key

        Raises:
            ValueError: If key_str is None or empty
        """
        if not self._key_str:
            raise ValueError("Key string is None or empty")
        self._data = bytearray(self._key_str.encode("utf-8"))
        self._key_str = None  # Remove reference to allow GC
        return self._data

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Securely zero the key from memory when exiting context.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)

        Returns:
            False to propagate any exception
        """
        if self._data is not None:
            secure_zero_memory(self._data)
            self._data = bytearray()
        return False
