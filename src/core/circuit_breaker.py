"""Generic circuit breaker implementation with async support."""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Awaitable, Callable, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failures exceeded threshold, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    def __init__(self, message: str = "Circuit breaker is open"):
        self.message = message
        super().__init__(self.message)


class CircuitBreaker:
    """
    Generic circuit breaker with async support.

    Prevents cascading failures by stopping calls to failing services.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests are rejected immediately
    - HALF_OPEN: Testing if service recovered, limited requests allowed

    Example:
        ```python
        circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout_seconds=60,
            expected_exception=HTTPException
        )

        @circuit_breaker.protected
        async def call_external_api():
            # Your code here
            pass
        ```
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: float = 60.0,
        expected_exception: Type[BaseException] = Exception,
        name: Optional[str] = None,
        half_open_threshold: int = 3,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout_seconds: Time to wait before attempting recovery (half-open)
            expected_exception: Exception type to catch (others will pass through)
            name: Optional name for logging
            half_open_threshold: Number of successes needed in HALF_OPEN to close
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.expected_exception = expected_exception
        self.name = name or "CircuitBreaker"
        self._half_open_threshold = half_open_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_successes = 0
        self._last_failure_time: Optional[datetime] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    async def _update_state(self) -> None:
        """
        Update circuit breaker state based on current conditions.

        Must be called with lock held.
        """
        if self._state == CircuitState.OPEN:
            # Check if enough time has passed to attempt recovery
            if self._last_failure_time:
                time_since_failure = datetime.now() - self._last_failure_time
                if time_since_failure >= timedelta(seconds=self.timeout_seconds):
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_successes = 0
                    logger.info(f"{self.name}: Circuit half-open, testing recovery")

    async def _record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self._half_open_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._half_open_successes = 0
                    logger.info(f"{self.name}: Circuit closed after successful recovery test")
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success in closed state
                self._failure_count = 0

    async def _record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open state reopens the circuit
                self._state = CircuitState.OPEN
                self._half_open_successes = 0
                logger.warning(f"{self.name}: Circuit reopened after failure during recovery test")
            elif self._failure_count >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        f"{self.name}: Circuit opened after {self._failure_count} failures"
                    )

    async def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._state != CircuitState.OPEN:
            return False

        if self._last_failure_time is None:
            return False

        time_since_failure = datetime.now() - self._last_failure_time
        return time_since_failure >= timedelta(seconds=self.timeout_seconds)

    async def can_execute(self) -> bool:
        """
        Check if a request can be executed.

        Returns:
            True if circuit allows execution
        """
        async with self._lock:
            await self._update_state()
            return self._state != CircuitState.OPEN

    async def call(self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        """
        Call a function through the circuit breaker.

        Args:
            func: Async function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Original exception from func if not expected_exception
        """
        # Check if we can execute (updates state if needed)
        if not await self.can_execute():
            raise CircuitBreakerError(
                f"{self.name}: Circuit breaker is open. "
                f"Service will be retried after {self.timeout_seconds}s"
            )

        # Attempt the call
        try:
            result = await func(*args, **kwargs)
            await self._record_success()
            return result
        except self.expected_exception:
            await self._record_failure()
            raise
        except Exception as e:
            # Unexpected exceptions pass through without affecting circuit
            logger.debug(f"{self.name}: Unexpected exception (not counted): {type(e).__name__}")
            raise

    def protected(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        """
        Decorator to protect an async function with circuit breaker.

        Args:
            func: Async function to protect

        Returns:
            Wrapped function

        Example:
            ```python
            @circuit_breaker.protected
            async def my_function():
                pass
            ```
        """

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await self.call(func, *args, **kwargs)

        return wrapper

    async def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            logger.info(f"{self.name}: Circuit manually reset to closed state")

    def get_stats(self) -> dict:
        """
        Get current circuit breaker statistics.

        Returns:
            Dictionary with state, failure_count, and last_failure_time
        """
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self._last_failure_time.isoformat()
            if self._last_failure_time
            else None,
            "timeout_seconds": self.timeout_seconds,
        }
