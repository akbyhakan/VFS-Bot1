"""Thread-safe metrics storage."""

import asyncio
import copy
import threading
from datetime import datetime, timezone
from typing import Any, Dict


class ThreadSafeMetrics:
    """
    Thread-safe metrics storage with asyncio support.

    This class uses threading.Lock for synchronization. When used in async contexts,
    use the async_* methods which run operations in an executor to avoid blocking.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._data = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "slots_checked": 0,
            "slots_found": 0,
            "appointments_booked": 0,
            "captchas_solved": 0,
            "errors": {},
            "start_time": datetime.now(timezone.utc),
        }

    def increment(self, key: str, value: int = 1) -> None:
        """Increment a metric value thread-safely."""
        with self._lock:
            if key in self._data and isinstance(self._data[key], (int, float)):
                self._data[key] += value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a metric value thread-safely."""
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a metric value thread-safely."""
        with self._lock:
            self._data[key] = value

    def add_error(self, error_type: str) -> None:
        """Add an error to metrics thread-safely."""
        with self._lock:
            if "errors" not in self._data:
                self._data["errors"] = {}
            if error_type not in self._data["errors"]:
                self._data["errors"][error_type] = 0
            self._data["errors"][error_type] += 1

    def to_dict(self) -> Dict[str, Any]:
        """Return a deep copy of metrics data thread-safely."""
        with self._lock:
            return copy.deepcopy(self._data)

    async def async_increment(self, key: str, value: int = 1) -> None:
        """Async wrapper for increment - runs in executor to avoid blocking."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.increment, key, value)

    async def async_get(self, key: str, default: Any = None) -> Any:
        """Async wrapper for get - runs in executor to avoid blocking."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.get, key, default)

    async def async_set(self, key: str, value: Any) -> None:
        """Async wrapper for set - runs in executor to avoid blocking."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.set, key, value)

    async def async_to_dict(self) -> Dict[str, Any]:
        """Async wrapper for to_dict - runs in executor to avoid blocking."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.to_dict)

    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dictionary-style item assignment."""
        self.set(key, value)

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style item access."""
        with self._lock:
            return self._data[key]

    def __contains__(self, key: str) -> bool:
        """Allow 'in' operator for checking key existence."""
        with self._lock:
            return key in self._data
