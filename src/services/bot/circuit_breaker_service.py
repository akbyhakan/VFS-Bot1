"""Circuit breaker service for fault tolerance and error tracking."""

import asyncio
import logging
import time
from collections import deque
from typing import Optional, TypedDict

from ...constants import CircuitBreaker

logger = logging.getLogger(__name__)


class CircuitBreakerStats(TypedDict):
    """Circuit breaker statistics."""

    consecutive_errors: int
    total_errors_in_window: int
    is_open: bool
    open_time: Optional[float]


class CircuitBreakerService:
    """
    Circuit breaker implementation for fault tolerance.

    Tracks errors and opens circuit when thresholds are exceeded,
    preventing cascading failures. Supports exponential backoff and
    automatic recovery.
    """

    def __init__(self):
        """Initialize circuit breaker with default settings."""
        self.consecutive_errors = 0
        self.total_errors: deque = deque(maxlen=CircuitBreaker.MAX_ERRORS_PER_HOUR)
        self.circuit_breaker_open = False
        self.circuit_breaker_open_time: Optional[float] = None
        self._lock = asyncio.Lock()  # Thread-safety for circuit breaker

    async def is_available(self) -> bool:
        """
        Check if circuit breaker allows requests.

        Returns:
            True if circuit is closed (requests allowed), False if open
        """
        async with self._lock:
            return not self.circuit_breaker_open

    async def record_success(self) -> None:
        """Record successful operation and close circuit if open."""
        async with self._lock:
            self.consecutive_errors = 0
            if self.circuit_breaker_open:
                self.circuit_breaker_open = False
                self.circuit_breaker_open_time = None
                logger.info("Circuit breaker closed after successful operation")

    async def record_failure(self) -> None:
        """
        Record failed operation and potentially open circuit breaker.

        Opens circuit if consecutive errors or total errors in window exceed thresholds.
        """
        async with self._lock:
            current_time = time.time()
            self.consecutive_errors += 1
            self.total_errors.append(current_time)

            # Clean old errors outside tracking window
            cutoff_time = current_time - CircuitBreaker.ERROR_TRACKING_WINDOW
            while self.total_errors and self.total_errors[0] < cutoff_time:
                self.total_errors.popleft()

            # Check if circuit breaker should open
            recent_errors = len(self.total_errors)

            if (
                self.consecutive_errors >= CircuitBreaker.MAX_CONSECUTIVE_ERRORS
                or recent_errors >= CircuitBreaker.MAX_TOTAL_ERRORS_PER_HOUR
            ):
                self.circuit_breaker_open = True
                self.circuit_breaker_open_time = current_time
                logger.error(
                    f"CIRCUIT BREAKER OPENED - "
                    f"consecutive: {self.consecutive_errors}, "
                    f"total in hour: {recent_errors}"
                )

                # Record circuit breaker trip in metrics
                try:
                    from ...utils.metrics import get_metrics

                    metrics = await get_metrics()
                    await metrics.record_circuit_breaker_trip()
                except Exception as e:
                    logger.debug(f"Failed to record circuit breaker trip metric: {e}")

    async def reset(self) -> None:
        """Reset circuit breaker state to closed."""
        async with self._lock:
            self.circuit_breaker_open = False
            self.circuit_breaker_open_time = None
            self.consecutive_errors = 0
            logger.info("Circuit breaker CLOSED - resuming normal operation")

    async def get_wait_time(self) -> float:
        """
        Calculate wait time for circuit breaker with exponential backoff.

        Returns:
            Wait time in seconds based on number of consecutive errors
        """
        async with self._lock:
            # Exponential backoff: min(60 * 2^(errors-1), 600)
            errors = min(self.consecutive_errors, 10)  # Cap for calculation
            backoff = min(
                CircuitBreaker.BACKOFF_BASE * (2 ** (errors - 1)), CircuitBreaker.BACKOFF_MAX
            )
            return float(backoff)

    async def get_stats(self) -> CircuitBreakerStats:
        """
        Get current circuit breaker statistics.

        Returns:
            Dictionary with circuit breaker stats
        """
        async with self._lock:
            # Clean old errors for accurate count
            current_time = time.time()
            cutoff_time = current_time - CircuitBreaker.ERROR_TRACKING_WINDOW
            while self.total_errors and self.total_errors[0] < cutoff_time:
                self.total_errors.popleft()

            return {
                "consecutive_errors": self.consecutive_errors,
                "total_errors_in_window": len(self.total_errors),
                "is_open": self.circuit_breaker_open,
                "open_time": self.circuit_breaker_open_time,
            }
