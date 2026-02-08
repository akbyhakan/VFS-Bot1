"""Thread-safe bot state management."""

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ThreadSafeBotState:
    """Thread-safe wrapper for bot state."""

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
