"""Thread-safe bot state management."""

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ThreadSafeBotState:
    """Thread-safe wrapper for bot state using typed dataclass fields.

    Uses a single threading.Lock for all operations (both sync and async methods).
    This ensures thread-safety across all contexts without race conditions.

    The threading.Lock works correctly in async contexts as state operations are
    microsecond-level, so event loop blocking is negligible.

    All dict-style access has been removed in favor of typed getters/setters.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    running: bool = field(default=False, init=False)
    status: str = field(default="stopped", init=False)
    last_check: Optional[str] = field(default=None, init=False)
    slots_found: int = field(default=0, init=False)
    appointments_booked: int = field(default=0, init=False)
    active_users: int = field(default=0, init=False)
    logs: deque = field(default_factory=lambda: deque(maxlen=500), init=False)
    read_only: bool = field(default=False, init=False)

    # Typed getters
    def get_running(self) -> bool:
        """Thread-safe get running status."""
        with self._lock:
            return self.running

    def get_status(self) -> str:
        """Thread-safe get status."""
        with self._lock:
            return self.status

    def get_last_check(self) -> Optional[str]:
        """Thread-safe get last check timestamp."""
        with self._lock:
            return self.last_check

    def get_slots_found(self) -> int:
        """Thread-safe get slots found count."""
        with self._lock:
            return self.slots_found

    def get_appointments_booked(self) -> int:
        """Thread-safe get appointments booked count."""
        with self._lock:
            return self.appointments_booked

    def get_active_users(self) -> int:
        """Thread-safe get active users count."""
        with self._lock:
            return self.active_users

    def get_read_only(self) -> bool:
        """Thread-safe get read-only mode flag."""
        with self._lock:
            return self.read_only

    def get_logs(self) -> deque:
        """Thread-safe get logs deque reference."""
        with self._lock:
            return self.logs

    # Typed setters
    def set_running(self, value: bool) -> None:
        """Thread-safe set running status."""
        with self._lock:
            self.running = value

    def set_status(self, value: str) -> None:
        """Thread-safe set status."""
        with self._lock:
            self.status = value

    def set_last_check(self, value: Optional[str]) -> None:
        """Thread-safe set last check timestamp."""
        with self._lock:
            self.last_check = value

    def set_slots_found(self, value: int) -> None:
        """Thread-safe set slots found count."""
        with self._lock:
            self.slots_found = value

    def set_appointments_booked(self, value: int) -> None:
        """Thread-safe set appointments booked count."""
        with self._lock:
            self.appointments_booked = value

    def set_active_users(self, value: int) -> None:
        """Thread-safe set active users count."""
        with self._lock:
            self.active_users = value

    def set_read_only(self, value: bool) -> None:
        """Thread-safe set read-only mode flag."""
        with self._lock:
            self.read_only = value

    # Atomic operations
    def increment_slots_found(self, count: int = 1) -> None:
        """Thread-safe increment slots found count."""
        with self._lock:
            self.slots_found += count

    def increment_appointments_booked(self, count: int = 1) -> None:
        """Thread-safe increment appointments booked count."""
        with self._lock:
            self.appointments_booked += count

    # Log operations
    def append_log(self, message: str, level: str = "INFO") -> None:
        """Thread-safe append log message as structured dict."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            self.logs.append({"message": message, "level": level, "timestamp": timestamp})

    def get_logs_list(self) -> List[Dict[str, str]]:
        """Thread-safe get logs as a list (copy)."""
        with self._lock:
            return list(self.logs)

    # Dictionary conversion
    def to_dict(self) -> Dict[str, Any]:
        """Return a deep copy of state data thread-safely."""
        with self._lock:
            return {
                "running": self.running,
                "status": self.status,
                "last_check": self.last_check,
                "slots_found": self.slots_found,
                "appointments_booked": self.appointments_booked,
                "active_users": self.active_users,
                "logs": list(self.logs),
            }

    async def async_to_dict(self) -> Dict[str, Any]:
        """Async to_dict - uses threading.Lock (safe in async context)."""
        with self._lock:
            return {
                "running": self.running,
                "status": self.status,
                "last_check": self.last_check,
                "slots_found": self.slots_found,
                "appointments_booked": self.appointments_booked,
                "active_users": self.active_users,
                "logs": list(self.logs),
            }
