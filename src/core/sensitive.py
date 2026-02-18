"""Sensitive data wrappers to prevent exposure in logs and stack traces."""

from typing import Any, Dict, Iterator, Optional


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

    def __iter__(self) -> Iterator[str]:
        """Iterate over keys (same behavior as dict)."""
        return iter(self._data)

    def __len__(self) -> int:
        """Return number of items."""
        return len(self._data)

    def items(self):
        """Return view of (key, value) pairs."""
        return self._data.items()

    def values(self):
        """Return view of values."""
        return self._data.values()

    def __setitem__(self, key: str, value: Any) -> None:
        """Set item by key."""
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        """Delete item by key."""
        del self._data[key]

    def update(self, other: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        """Update dict with key-value pairs."""
        if other:
            self._data.update(other)
        self._data.update(kwargs)

    def pop(self, key: str, *args: Any) -> Any:
        """Remove and return value for key."""
        return self._data.pop(key, *args)

    def __eq__(self, other: object) -> bool:
        """Compare equality (compares internal data)."""
        if isinstance(other, SensitiveDict):
            return self._data == other._data
        if isinstance(other, dict):
            return self._data == other
        return NotImplemented

    def copy(self) -> "SensitiveDict":
        """Return a shallow copy."""
        return SensitiveDict(self._data.copy())

    def wipe(self) -> None:
        """
        Best-effort memory wipe of internal data.

        Clears the internal dictionary, removing all key-value references.

        .. warning::
            Python's immutable ``str`` and ``bytes`` values cannot be reliably
            zeroed from memory.  They remain until the garbage collector
            reclaims them.  For true secure memory erasure (e.g. PCI-DSS
            cardholder data), store values as ``bytearray`` and use
            ``src.utils.secure_memory.secure_zero_memory()`` before clearing.

        Call this in a ``finally`` block after sensitive data is no longer needed.
        """
        self._data.clear()
