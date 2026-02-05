"""Circuit breaker service for fault tolerance and error tracking."""

import asyncio
import logging
from typing import Optional, TypedDict

from ...constants import CircuitBreaker as CircuitBreakerConfig
from ...core.circuit_breaker import CircuitBreaker, CircuitState

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

    This is a thin wrapper around the core CircuitBreaker that maintains
    backward compatibility with the bot's existing API.

    Tracks errors and opens circuit when thresholds are exceeded,
    preventing cascading failures. Supports exponential backoff and
    automatic recovery.
    """

    def __init__(self):
        """Initialize circuit breaker with default settings."""
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=CircuitBreakerConfig.MAX_CONSECUTIVE_ERRORS,
            timeout_seconds=CircuitBreakerConfig.RESET_TIMEOUT_SECONDS,
            name="BotCircuitBreaker",
            half_open_threshold=CircuitBreakerConfig.HALF_OPEN_SUCCESS_THRESHOLD,
            max_errors_per_hour=CircuitBreakerConfig.MAX_TOTAL_ERRORS_PER_HOUR,
            error_tracking_window=CircuitBreakerConfig.ERROR_TRACKING_WINDOW,
            backoff_base=CircuitBreakerConfig.BACKOFF_BASE,
            backoff_max=CircuitBreakerConfig.BACKOFF_MAX,
        )
        self._lock = asyncio.Lock()  # For backward compatibility

    async def is_available(self) -> bool:
        """
        Check if circuit breaker allows requests.

        Returns:
            True if circuit is closed (requests allowed), False if open
        """
        return await self._circuit_breaker.can_execute()

    async def record_success(self) -> None:
        """Record successful operation and close circuit if open."""
        await self._circuit_breaker.record_success()

    async def record_failure(self) -> None:
        """
        Record failed operation and potentially open circuit breaker.

        Opens circuit if consecutive errors or total errors in window exceed thresholds.
        """
        await self._circuit_breaker.record_failure()
        
        # Record circuit breaker trip in metrics if it just opened
        if self._circuit_breaker.state == CircuitState.OPEN:
            try:
                from ...utils.metrics import get_metrics

                metrics = await get_metrics()
                await metrics.record_circuit_breaker_trip()
            except Exception as e:
                logger.debug(f"Failed to record circuit breaker trip metric: {e}")

    async def reset(self) -> None:
        """Reset circuit breaker state to closed."""
        await self._circuit_breaker.reset()
        logger.info("Circuit breaker CLOSED - resuming normal operation")

    async def get_wait_time(self) -> float:
        """
        Calculate wait time for circuit breaker with exponential backoff.

        Returns:
            Wait time in seconds based on number of consecutive errors
        """
        return await self._circuit_breaker.get_wait_time()

    async def get_stats(self) -> CircuitBreakerStats:
        """
        Get current circuit breaker statistics.

        Returns:
            Dictionary with circuit breaker stats
        """
        stats = self._circuit_breaker.get_stats()
        
        # Convert to backward-compatible format
        return {
            "consecutive_errors": stats["failure_count"],
            "total_errors_in_window": stats["total_errors_in_window"],
            "is_open": stats["state"] == CircuitState.OPEN.value,
            "open_time": None,  # Core circuit breaker tracks last_failure_time instead
        }

