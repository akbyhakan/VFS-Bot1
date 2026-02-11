"""
Generic circuit breaker implementation with async support.

This is the single source of truth for circuit breaker logic in the application.
All other circuit breaker implementations should delegate to this class.

Architecture:
    - Core implementation: src/core/circuit_breaker.py (this file)
    - Bot service wrapper: src/services/bot/circuit_breaker_service.py
        Thin wrapper maintaining backward compatibility with bot's API

Features:
    - 3-state machine (CLOSED → OPEN → HALF_OPEN → CLOSED)
    - Consecutive failure threshold
    - Time-windowed error threshold (max_errors_per_hour)
    - Exponential backoff with configurable base and max
    - Decorator pattern for easy function wrapping
    - Async/await support throughout
    - Thread-safe with asyncio.Lock

Example:
    ```python
    from src.core.circuit_breaker import CircuitBreaker

    # Method 1: Decorator pattern (recommended)
    cb = CircuitBreaker(failure_threshold=5, timeout_seconds=60.0)

    @cb.protected
    async def call_external_api():
        # Your code here
        pass

    # Method 2: Direct calls
    cb = CircuitBreaker(failure_threshold=5, timeout_seconds=60.0)

    if await cb.can_execute():
        try:
            result = await my_function()
            await cb.record_success()
        except Exception:
            await cb.record_failure()
    ```
"""

import asyncio
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any, Awaitable, Callable, Optional, Type, TypeVar

from loguru import logger

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
        max_errors_per_hour: Optional[int] = None,
        error_tracking_window: int = 3600,
        backoff_base: int = 60,
        backoff_max: int = 600,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout_seconds: Time to wait before attempting recovery (half-open)
            expected_exception: Exception type to catch (others will pass through)
            name: Optional name for logging
            half_open_threshold: Number of successes needed in HALF_OPEN to close
            max_errors_per_hour: Max total errors in tracking window before opening (optional)
            error_tracking_window: Time window for error tracking in seconds
            backoff_base: Base backoff time in seconds for exponential backoff
            backoff_max: Maximum backoff time in seconds
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.expected_exception = expected_exception
        self.name = name or "CircuitBreaker"
        self._half_open_threshold = half_open_threshold
        self._max_errors_per_hour = max_errors_per_hour
        self._error_tracking_window = error_tracking_window
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_successes = 0
        self._last_failure_time: Optional[datetime] = None
        self._lock = asyncio.Lock()

        # Error tracking for window-based threshold
        self._error_timestamps: deque = deque(
            maxlen=max_errors_per_hour if max_errors_per_hour else 100
        )

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
                time_since_failure = datetime.now(timezone.utc) - self._last_failure_time
                if time_since_failure >= timedelta(seconds=self.timeout_seconds):
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_successes = 0
                    logger.info(f"{self.name}: Circuit half-open, testing recovery")

    async def record_success(self) -> None:
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

    async def record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(timezone.utc)

            # Track error timestamp for window-based threshold
            if self._max_errors_per_hour:
                current_time = time.time()
                self._error_timestamps.append(current_time)

                # Clean old errors outside tracking window
                cutoff_time = current_time - self._error_tracking_window
                while self._error_timestamps and self._error_timestamps[0] < cutoff_time:
                    self._error_timestamps.popleft()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open state reopens the circuit
                self._state = CircuitState.OPEN
                self._half_open_successes = 0
                logger.warning(f"{self.name}: Circuit reopened after failure during recovery test")
            elif self._state == CircuitState.CLOSED:
                # Check consecutive failures threshold
                should_open = self._failure_count >= self.failure_threshold

                # Check window-based threshold if configured
                if self._max_errors_per_hour:
                    recent_errors = len(self._error_timestamps)
                    should_open = should_open or (recent_errors >= self._max_errors_per_hour)

                if should_open:
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

        time_since_failure = datetime.now(timezone.utc) - self._last_failure_time
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
            await self.record_success()
            return result
        except self.expected_exception:
            await self.record_failure()
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
            self._error_timestamps.clear()
            logger.info(f"{self.name}: Circuit manually reset to closed state")

    async def get_wait_time(self) -> float:
        """
        Calculate wait time with exponential backoff.

        Returns:
            Wait time in seconds based on consecutive failures
        """
        async with self._lock:
            # Exponential backoff: min(base * 2^(errors-1), max)
            errors = min(self._failure_count, 10)  # Cap for calculation
            if errors == 0:
                return 0.0
            backoff = min(self._backoff_base * (2 ** (errors - 1)), self._backoff_max)
            return float(backoff)

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
            "last_failure_time": (
                self._last_failure_time.isoformat() if self._last_failure_time else None
            ),
            "timeout_seconds": self.timeout_seconds,
            "total_errors_in_window": (
                len(self._error_timestamps) if self._max_errors_per_hour else 0
            ),
        }
