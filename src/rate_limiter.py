"""Rate limiting for API requests."""

import asyncio
import time
import logging
from typing import Optional
from collections import deque

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API calls."""
    
    def __init__(self, max_requests: int = 60, time_window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: deque = deque()
        self._lock = asyncio.Lock()
        logger.info(f"RateLimiter initialized: {max_requests} req/{time_window}s")
    
    async def acquire(self) -> None:
        """Wait until rate limit allows a request."""
        async with self._lock:
            current_time = time.time()
            
            # Remove requests outside time window
            while self.requests and self.requests[0] < current_time - self.time_window:
                self.requests.popleft()
            
            # Check if we can make a request
            if len(self.requests) >= self.max_requests:
                # Calculate wait time
                oldest_request = self.requests[0]
                wait_time = (oldest_request + self.time_window) - current_time
                
                if wait_time > 0:
                    logger.warning(f"Rate limit reached, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                
                # Remove old request
                self.requests.popleft()
            
            # Add current request
            self.requests.append(current_time)
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        current_time = time.time()
        
        # Count requests in current window
        recent_requests = sum(
            1 for req_time in self.requests 
            if req_time > current_time - self.time_window
        )
        
        return {
            "requests_in_window": recent_requests,
            "max_requests": self.max_requests,
            "time_window": self.time_window,
            "available": self.max_requests - recent_requests
        }


# Global rate limiter instance
_global_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = RateLimiter(max_requests=60, time_window=60)
    return _global_limiter
