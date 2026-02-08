"""Thread-safe bot state management."""

import asyncio
import copy
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ThreadSafeBotState:
    """
    Thread-safe wrapper for bot state with asyncio support.
    
    This class uses threading.Lock for synchronization. When used in async contexts,
    use the async_* methods which run operations in an executor to avoid blocking.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _state: Dict[str, Any] = field(
        default_factory=lambda: {
            "running": False,
            "status": "stopped",
            "last_check": None,
            "slots_found": 0,
            "appointments_booked": 0,
            "active_users": 0,
            "logs": deque(maxlen=500),
        }
    )

    def get(self, key: str, default: Any = None) -> Any:
        """Thread-safe get."""
        with self._lock:
            return self._state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Thread-safe set."""
        with self._lock:
            self._state[key] = value

    def __getitem__(self, key: str) -> Any:
        with self._lock:
            return self._state[key]

    def __setitem__(self, key: str, value: Any) -> None:
        with self._lock:
            self._state[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """Return a deep copy of state data thread-safely."""
        with self._lock:
            # Use deepcopy to avoid issues with nested mutable objects
            # Note: deque objects are handled specially
            state_copy = {}
            for key, value in self._state.items():
                if isinstance(value, deque):
                    # Convert deque to list for deepcopy
                    state_copy[key] = list(value)
                else:
                    state_copy[key] = copy.deepcopy(value)
            return state_copy

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
