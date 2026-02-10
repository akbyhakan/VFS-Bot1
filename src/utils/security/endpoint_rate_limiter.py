"""Per-endpoint rate limiting for VFS API calls."""

import asyncio
import time
from typing import Dict, Optional

from loguru import logger

from .rate_limiter import RateLimiter


class EndpointRateLimiter:
    """
    Per-endpoint rate limiter that maintains separate rate limits for different API endpoints.
    
    VFS Global applies different rate limits to different endpoints:
    - Login: More restrictive (3 req/60s)
    - Slot checks: Moderate (30 req/60s)
    - Booking: Restrictive (10 req/60s)
    - Centres/categories: Light (5 req/60s)
    - Default: Standard (60 req/60s)
    
    NOTE: This rate limiter is designed for single-process VFS API call throttling.
    For distributed/multi-worker deployments, see src/core/auth.py which provides
    Redis-backed rate limiting via AuthRateLimiter with InMemoryBackend/RedisBackend.
    """

    def __init__(
        self,
        login_limit: int = 3,
        slot_check_limit: int = 30,
        booking_limit: int = 10,
        centres_limit: int = 5,
        default_limit: int = 60,
        time_window: int = 60,
    ):
        """
        Initialize per-endpoint rate limiter.

        Args:
            login_limit: Max requests for login endpoint
            slot_check_limit: Max requests for slot check endpoint
            booking_limit: Max requests for booking endpoint
            centres_limit: Max requests for centres/categories endpoints
            default_limit: Max requests for unknown endpoints
            time_window: Time window in seconds (default: 60)
        """
        self.time_window = time_window
        self._limiters: Dict[str, RateLimiter] = {
            "login": RateLimiter(max_requests=login_limit, time_window=time_window),
            "slot_check": RateLimiter(max_requests=slot_check_limit, time_window=time_window),
            "booking": RateLimiter(max_requests=booking_limit, time_window=time_window),
            "centres": RateLimiter(max_requests=centres_limit, time_window=time_window),
            "default": RateLimiter(max_requests=default_limit, time_window=time_window),
        }
        # Track VFS-imposed rate limits (from 429 responses)
        self._vfs_rate_limits: Dict[str, float] = {}  # endpoint -> retry_after_timestamp
        logger.info(
            f"EndpointRateLimiter initialized: "
            f"login={login_limit}, slot_check={slot_check_limit}, "
            f"booking={booking_limit}, centres={centres_limit}, "
            f"default={default_limit} (per {time_window}s)"
        )

    async def acquire(self, endpoint: str = "default") -> None:
        """
        Acquire permission to make a request to the specified endpoint.
        
        Waits if rate limit is reached or if VFS has imposed a rate limit via 429 response.
        
        Args:
            endpoint: Endpoint category ("login", "slot_check", "booking", "centres", "default")
        """
        # Check VFS-imposed rate limit first
        if endpoint in self._vfs_rate_limits:
            wait_until = self._vfs_rate_limits[endpoint]
            current_time = time.time()
            if current_time < wait_until:
                wait_time = wait_until - current_time
                logger.warning(
                    f"VFS rate limit active for {endpoint}, waiting {wait_time:.2f}s "
                    "(429 Retry-After)"
                )
                await asyncio.sleep(wait_time)
                # Remove expired limit
                del self._vfs_rate_limits[endpoint]

        # Get appropriate limiter
        limiter = self._limiters.get(endpoint, self._limiters["default"])
        
        # Acquire from the endpoint-specific limiter
        await limiter.acquire()

    def on_rate_limited(self, endpoint: str, retry_after: int) -> None:
        """
        Record a 429 rate limit response from VFS.
        
        Args:
            endpoint: Endpoint category that was rate limited
            retry_after: Seconds to wait before retrying (from Retry-After header)
        """
        retry_until = time.time() + retry_after
        self._vfs_rate_limits[endpoint] = retry_until
        logger.warning(
            f"VFS rate limit (429) received for {endpoint}, "
            f"enforcing {retry_after}s wait"
        )

    def get_all_stats(self) -> Dict[str, dict]:
        """
        Get statistics for all endpoint limiters.
        
        Returns:
            Dictionary mapping endpoint names to their rate limiter stats
        """
        stats = {}
        for endpoint, limiter in self._limiters.items():
            limiter_stats = limiter.get_stats()
            # Add VFS rate limit info if active
            if endpoint in self._vfs_rate_limits:
                current_time = time.time()
                wait_until = self._vfs_rate_limits[endpoint]
                vfs_wait_remaining = max(0, wait_until - current_time)
                limiter_stats["vfs_rate_limited"] = True
                limiter_stats["vfs_wait_remaining"] = vfs_wait_remaining
            else:
                limiter_stats["vfs_rate_limited"] = False
            stats[endpoint] = limiter_stats
        return stats

    def get_stats(self, endpoint: str = "default") -> dict:
        """
        Get statistics for a specific endpoint limiter.
        
        Args:
            endpoint: Endpoint category to get stats for
            
        Returns:
            Rate limiter statistics dictionary
        """
        limiter = self._limiters.get(endpoint, self._limiters["default"])
        stats = limiter.get_stats()
        
        # Add VFS rate limit info if active
        if endpoint in self._vfs_rate_limits:
            current_time = time.time()
            wait_until = self._vfs_rate_limits[endpoint]
            vfs_wait_remaining = max(0, wait_until - current_time)
            stats["vfs_rate_limited"] = True
            stats["vfs_wait_remaining"] = vfs_wait_remaining
        else:
            stats["vfs_rate_limited"] = False
            
        return stats
