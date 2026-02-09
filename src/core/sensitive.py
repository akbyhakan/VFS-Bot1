"""Sensitive data wrappers to prevent exposure in logs and stack traces."""

from typing import Any, Dict, Iterator, List, Optional


class SensitiveDict:
    """
    A dictionary wrapper that masks values in repr/str to prevent exposure.
    
    This class prevents sensitive data (like card details) from appearing in:
    - Stack traces and exception messages
    - Log outputs
    - Debug prints
    
    While still allowing normal dictionary access for actual usage.
    """

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        """
        Initialize SensitiveDict with optional data.
        
        Args:
            data: Dictionary to wrap (copied internally)
        """
        self._data: Dict[str, Any] = dict(data) if data else {}

    def __getitem__(self, key: str) -> Any:
        """Get item by key."""
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Get item with default fallback."""
        return self._data.get(key, default)

    def keys(self) -> Iterator[str]:
        """Return iterator over keys."""
        return iter(self._data.keys())

    def __contains__(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._data

    def __bool__(self) -> bool:
        """Check if dict is non-empty."""
        return bool(self._data)

    def __repr__(self) -> str:
        """Return masked representation (safe for logs/traces)."""
        keys_list = list(self._data.keys())
        return f"SensitiveDict(keys={keys_list}, ***MASKED***)"

    def __str__(self) -> str:
        """Return masked string representation (safe for logs/traces)."""
        return self.__repr__()

    def to_dict(self) -> Dict[str, Any]:
        """
        Explicitly unwrap to regular dict.
        
        Use this only at point-of-use when you need the actual values.
        
        Returns:
            Copy of internal dictionary
        """
        return dict(self._data)

    def wipe(self) -> None:
        """
        Securely wipe internal data from memory.
        
        Call this in a finally block after sensitive data is no longer needed.
        """
        self._data.clear()
