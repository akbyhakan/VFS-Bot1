"""Secure memory handling utilities for sensitive data."""

import ctypes
from typing import Union


def secure_zero_memory(data: Union[str, bytes, bytearray]) -> None:
    """
    Securely zero out memory containing sensitive data.
    
    Args:
        data: Sensitive data to zero out (string, bytes, or bytearray)
    """
    if data is None:
        return
    try:
        if isinstance(data, (bytes, bytearray)):
            if isinstance(data, bytes):
                mutable = bytearray(data)
                ctypes.memset(ctypes.addressof((ctypes.c_char * len(mutable)).from_buffer(mutable)), 0, len(mutable))
            else:
                ctypes.memset(ctypes.addressof((ctypes.c_char * len(data)).from_buffer(data)), 0, len(data))
    except Exception:
        # Fallback: manually zero each byte
        if isinstance(data, bytearray):
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
        self._data = bytearray(cvv.encode('utf-8'))
        
    def __enter__(self) -> str:
        """Return CVV as string when entering context."""
        return self._data.decode('utf-8')
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Securely clear CVV from memory when exiting context."""
        secure_zero_memory(self._data)
        self._data = None
        return False
