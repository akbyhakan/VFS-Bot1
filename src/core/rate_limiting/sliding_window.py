"""Rate limiting for API requests."""

import asyncio
import threading
import time
from collections import deque
from typing import Optional

from loguru import logger

from src.constants import RateLimits


class RateLimiter:
    """
    Token bucket rate limiter for API calls.

    NOTE: This rate limiter is designed for single-process VFS API call throttling.
    For distributed/multi-worker deployments, see src/core/auth.py which provides
    Redis-backed rate limiting via AuthRateLimiter with InMemoryBackend/RedisBackend.
    """

    def __init__(self, max_requests: int = 60, time_window: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        # maxlen prevents memory leak by automatically removing old items
        self.requests: deque = deque(maxlen=max_requests * 2)
        self._lock = asyncio.Lock()
        logger.info(f"RateLimiter initialized: {max_requests} req/{time_window}s")

    async def acquire(self) -> None:
        """Wait until rate limit allows a request."""
        while True:
            async with self._lock:
                current_time = time.time()

                # Remove requests outside time window
                while self.requests and self.requests[0] < current_time - self.time_window:
                    self.requests.popleft()

                # Check if we can make a request
                if len(self.requests) < self.max_requests:
                    # Add current request and return
                    self.requests.append(current_time)
                    return

                # Calculate wait time
                oldest_request = self.requests[0]
                wait_time = (oldest_request + self.time_window) - current_time

            # Wait outside the lock so other requests can proceed
            if wait_time > 0:
                logger.warning(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
            else:
                # Small delay to avoid busy waiting
                await asyncio.sleep(0.01)

    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        current_time = time.time()

        # Count requests in current window
        recent_requests = sum(
            1 for req_time in self.requests if req_time > current_time - self.time_window
        )

        return {
            "requests_in_window": recent_requests,
            "max_requests": self.max_requests,
            "time_window": self.time_window,
            "available": self.max_requests - recent_requests,
        }

    async def get_rate_limit_info(self, client_id: str) -> dict:
        """
        Get rate limit information for a client.

        This method provides rate limit headers information compatible with
        the RateLimitHeadersMiddleware.

        Args:
            client_id: Client identifier (IP address or user ID)

        Returns:
            Dictionary with limit, remaining, and reset timestamp
        """
        async with self._lock:
            current_time = time.time()

            # Clean old requests
            while self.requests and self.requests[0] < current_time - self.time_window:
                self.requests.popleft()

            # Calculate remaining requests
            recent_requests = len(self.requests)
            remaining = max(0, self.max_requests - recent_requests)

            # Calculate reset timestamp (when oldest request expires)
            if self.requests:
                oldest_request = self.requests[0]
                reset_timestamp = int(oldest_request + self.time_window)
            else:
                reset_timestamp = int(current_time + self.time_window)

            return {
                "limit": self.max_requests,
                "remaining": remaining,
                "reset": reset_timestamp,
            }


# Global rate limiter instance
_global_limiter: Optional[RateLimiter] = None
_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """
    Get global rate limiter instance (singleton) - thread-safe.

    Uses double-checked locking pattern for efficiency.

    Returns:
        RateLimiter instance
    """
    global _global_limiter
    if _global_limiter is None:
        with _limiter_lock:
            if _global_limiter is None:  # Double-checked locking
                _global_limiter = RateLimiter(
                    max_requests=RateLimits.MAX_REQUESTS,
                    time_window=RateLimits.TIME_WINDOW_SECONDS,
                )
    return _global_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter instance. Thread-safe."""
    global _global_limiter
    with _limiter_lock:
        _global_limiter = None
