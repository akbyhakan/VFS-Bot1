"""Adaptive rate limiter that backs off on failures."""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AdaptiveRateLimiter:
    """
    Intelligent rate limiter that adapts based on success/failure patterns.

    Features:
    - Exponential backoff on consecutive failures
    - Gradual recovery on successes
    - Per-endpoint tracking
    - Jitter to prevent thundering herd
    """

    base_delay: float = 30.0
    max_delay: float = 300.0
    min_delay: float = 10.0
    backoff_factor: float = 2.0
    recovery_factor: float = 0.8
    jitter_factor: float = 0.1

    _current_delay: float = field(default=0.0, init=False)
    _consecutive_failures: int = field(default=0, init=False)
    _last_request_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self):
        """Initialize current delay to base delay."""
        self._current_delay = self.base_delay

    async def wait(self) -> None:
        """Wait for the appropriate delay before next request."""
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time

            if elapsed < self._current_delay:
                wait_time = self._current_delay - elapsed
                # Add random jitter to prevent thundering herd
                jitter = wait_time * self.jitter_factor * random.uniform(-1, 1)
                wait_time = max(0, wait_time + jitter)

                logger.debug(
                    f"Rate limiter waiting {wait_time:.2f}s (delay: {self._current_delay:.2f}s)"
                )
                await asyncio.sleep(wait_time)

            self._last_request_time = time.time()

    def on_success(self) -> None:
        """Record a successful request and potentially decrease delay."""
        self._consecutive_failures = 0
        if self._current_delay > self.base_delay:
            self._current_delay = max(self.base_delay, self._current_delay * self.recovery_factor)
            logger.debug(f"Rate limiter recovered to {self._current_delay:.2f}s delay")

    def on_failure(self, is_rate_limited: bool = False) -> None:
        """Record a failed request and increase delay."""
        self._consecutive_failures += 1

        if is_rate_limited:
            # More aggressive backoff for rate limit errors
            self._current_delay = min(
                self.max_delay, self._current_delay * (self.backoff_factor * 2)
            )
        else:
            self._current_delay = min(
                self.max_delay,
                self.base_delay * (self.backoff_factor**self._consecutive_failures),
            )

        logger.warning(
            f"Rate limiter backed off to {self._current_delay:.2f}s "
            f"(failures: {self._consecutive_failures})"
        )

    def reset(self) -> None:
        """Reset the rate limiter to initial state."""
        self._current_delay = self.base_delay
        self._consecutive_failures = 0
        self._last_request_time = 0.0

    @property
    def current_delay(self) -> float:
        return self._current_delay

    @property
    def is_backed_off(self) -> bool:
        return self._current_delay > self.base_delay * 1.5
