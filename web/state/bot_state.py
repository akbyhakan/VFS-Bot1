"""Thread-safe bot state management."""

import copy
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ThreadSafeBotState:
    """Thread-safe wrapper for bot state with unified lock for sync and async methods.
    
    Uses a single threading.Lock for all operations (both sync and async methods).
    This ensures thread-safety across all contexts without race conditions.
    
    The threading.Lock works correctly in async contexts as state operations are
    microsecond-level (dict get/set), so event loop blocking is negligible.
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
            state_copy = {}
            for key, value in self._state.items():
                if isinstance(value, deque):
                    state_copy[key] = list(value)
                else:
                    state_copy[key] = copy.deepcopy(value)
            return state_copy

    async def async_get(self, key: str, default: Any = None) -> Any:
        """Async get - uses threading.Lock (safe in async context)."""
        with self._lock:
            return self._state.get(key, default)

    async def async_set(self, key: str, value: Any) -> None:
        """Async set - uses threading.Lock (safe in async context)."""
        with self._lock:
            self._state[key] = value

    async def async_to_dict(self) -> Dict[str, Any]:
        """Async to_dict - uses threading.Lock (safe in async context)."""
        with self._lock:
            state_copy = {}
            for key, value in self._state.items():
                if isinstance(value, deque):
                    state_copy[key] = list(value)
                else:
                    state_copy[key] = copy.deepcopy(value)
            return state_copy
