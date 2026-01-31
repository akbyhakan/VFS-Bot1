"""Circuit Breaker pattern implementation for API calls."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable, Any
import asyncio
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """
    Circuit Breaker pattern implementation for API calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service failing, requests rejected immediately
    - HALF_OPEN: Testing recovery, limited requests allowed
    """

    name: str
    fail_threshold: int = 5
    reset_timeout: int = 60
    half_open_max_calls: int = 3

    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _last_failure_time: Optional[datetime] = field(default=None, init=False)
    _half_open_calls: int = field(default=0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing)."""
        return self._state == CircuitState.OPEN

    async def can_execute(self) -> bool:
        """Check if request can be executed."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if reset timeout has passed
                if self._last_failure_time and datetime.now() - self._last_failure_time > timedelta(
                    seconds=self.reset_timeout
                ):
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(f"Circuit {self.name}: OPEN -> HALF_OPEN")
                    return True
                return False

            # HALF_OPEN state
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

    async def record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"Circuit {self.name}: HALF_OPEN -> CLOSED (recovered)")
            else:
                self._failure_count = 0

    async def record_failure(self, error: Optional[Exception] = None) -> None:
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._success_count = 0
                logger.warning(f"Circuit {self.name}: HALF_OPEN -> OPEN (failed during recovery)")
            elif self._failure_count >= self.fail_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit {self.name}: CLOSED -> OPEN "
                    f"(threshold reached: {self._failure_count})"
                )

    async def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute function with circuit breaker protection."""
        if not await self.can_execute():
            raise CircuitBreakerOpenError(f"Circuit {self.name} is OPEN")

        try:
            result = await func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as e:
            await self.record_failure(e)
            raise

    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure": self._last_failure_time.isoformat()
            if self._last_failure_time
            else None,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


# Global circuit breakers for different services
_circuit_breakers: dict[str, CircuitBreaker] = {}
_cb_lock = asyncio.Lock()


async def get_circuit_breaker(name: str, **kwargs: Any) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    async with _cb_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(name=name, **kwargs)
        return _circuit_breakers[name]
