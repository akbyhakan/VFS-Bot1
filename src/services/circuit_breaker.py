"""Circuit breaker service for managing system resilience."""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from src.constants import CircuitBreaker as CircuitBreakerConfig

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests due to errors
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker."""

    state: CircuitState
    consecutive_errors: int
    total_errors_in_window: int
    open_since: Optional[float]
    half_open_attempts: int


class CircuitBreakerService:
    """
    Thread-safe circuit breaker service for managing system resilience.

    Prevents cascading failures by temporarily blocking operations when
    error thresholds are exceeded.
    """

    def __init__(
        self,
        fail_threshold: int = CircuitBreakerConfig.FAIL_THRESHOLD,
        max_errors_per_hour: int = CircuitBreakerConfig.MAX_ERRORS_PER_HOUR,
        error_tracking_window: int = CircuitBreakerConfig.ERROR_TRACKING_WINDOW,
        reset_timeout: int = CircuitBreakerConfig.RESET_TIMEOUT_SECONDS,
        backoff_base: int = CircuitBreakerConfig.BACKOFF_BASE,
        backoff_max: int = CircuitBreakerConfig.BACKOFF_MAX,
    ):
        """
        Initialize circuit breaker service.

        Args:
            fail_threshold: Consecutive errors before opening circuit
            max_errors_per_hour: Total errors in window before opening circuit
            error_tracking_window: Time window for error tracking (seconds)
            reset_timeout: Time to wait before attempting reset (seconds)
            backoff_base: Base backoff time in seconds
            backoff_max: Maximum backoff time in seconds
        """
        self.fail_threshold = fail_threshold
        self.max_errors_per_hour = max_errors_per_hour
        self.error_tracking_window = error_tracking_window
        self.reset_timeout = reset_timeout
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max

        # State
        self.state = CircuitState.CLOSED
        self.consecutive_errors = 0
        self.total_errors: deque = deque(maxlen=max_errors_per_hour)
        self.open_time: Optional[float] = None
        self.half_open_attempts = 0

        # Thread safety
        self._lock = asyncio.Lock()

    async def is_available(self) -> bool:
        """
        Check if circuit breaker allows requests.

        Returns:
            True if requests are allowed
        """
        async with self._lock:
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.HALF_OPEN:
                # Allow limited requests in half-open state
                return self.half_open_attempts < CircuitBreakerConfig.HALF_OPEN_MAX_CALLS

            # OPEN state - check if we should transition to HALF_OPEN
            if self.open_time and time.time() - self.open_time >= self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_attempts = 0
                logger.info("Circuit breaker transitioning to HALF_OPEN - testing recovery")
                return True

            return False

    async def record_success(self) -> None:
        """Record successful operation."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                # Successful test in half-open state - close circuit
                self.state = CircuitState.CLOSED
                self.consecutive_errors = 0
                self.open_time = None
                self.half_open_attempts = 0
                logger.info("✅ Circuit breaker CLOSED - service recovered")
            elif self.state == CircuitState.CLOSED:
                # Reset consecutive errors on success
                self.consecutive_errors = 0

    async def record_failure(self) -> None:
        """Record failed operation and potentially open circuit."""
        async with self._lock:
            current_time = time.time()
            self.consecutive_errors += 1
            self.total_errors.append(current_time)

            # Clean old errors outside tracking window
            cutoff_time = current_time - self.error_tracking_window
            while self.total_errors and self.total_errors[0] < cutoff_time:
                self.total_errors.popleft()

            recent_errors = len(self.total_errors)

            if self.state == CircuitState.HALF_OPEN:
                # Failed test in half-open state - reopen circuit
                self.state = CircuitState.OPEN
                self.open_time = current_time
                self.half_open_attempts = 0
                logger.error("🚨 Circuit breaker REOPENED - service still failing")

            elif self.state == CircuitState.CLOSED:
                # Check if we should open circuit
                if (
                    self.consecutive_errors >= self.fail_threshold
                    or recent_errors >= self.max_errors_per_hour
                ):
                    self.state = CircuitState.OPEN
                    self.open_time = current_time
                    logger.error(
                        f"🚨 CIRCUIT BREAKER OPENED - "
                        f"consecutive: {self.consecutive_errors}, "
                        f"total in window: {recent_errors}"
                    )

    async def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        async with self._lock:
            self.state = CircuitState.CLOSED
            self.consecutive_errors = 0
            self.total_errors.clear()
            self.open_time = None
            self.half_open_attempts = 0
            logger.info("Circuit breaker manually reset to CLOSED")

    async def get_wait_time(self) -> float:
        """
        Calculate wait time with exponential backoff (thread-safe).

        Returns:
            Wait time in seconds
        """
        async with self._lock:
            # Exponential backoff: min(base * 2^(errors-1), max)
            errors = min(self.consecutive_errors, 10)  # Cap for calculation
            backoff = min(self.backoff_base * (2 ** (errors - 1)), self.backoff_max)
            return float(backoff)

    async def get_stats(self) -> CircuitBreakerStats:
        """
        Get current circuit breaker statistics.

        Returns:
            CircuitBreakerStats with current state
        """
        async with self._lock:
            # Clean old errors for accurate count
            current_time = time.time()
            cutoff_time = current_time - self.error_tracking_window
            while self.total_errors and self.total_errors[0] < cutoff_time:
                self.total_errors.popleft()

            return CircuitBreakerStats(
                state=self.state,
                consecutive_errors=self.consecutive_errors,
                total_errors_in_window=len(self.total_errors),
                open_since=self.open_time,
                half_open_attempts=self.half_open_attempts,
            )
