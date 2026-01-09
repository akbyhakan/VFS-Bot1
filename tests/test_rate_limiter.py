"""Tests for rate limiter module."""

import asyncio
import time

import pytest

from src.rate_limiter import RateLimiter, get_rate_limiter


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_init(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(max_requests=10, time_window=60)
        
        assert limiter.max_requests == 10
        assert limiter.time_window == 60
        assert len(limiter.requests) == 0

    @pytest.mark.asyncio
    async def test_acquire_allows_requests_under_limit(self):
        """Test that requests under limit are allowed."""
        limiter = RateLimiter(max_requests=5, time_window=60)
        
        start_time = time.time()
        
        # Make 5 requests (under limit)
        for _ in range(5):
            await limiter.acquire()
        
        elapsed = time.time() - start_time
        
        # Should complete quickly (no waiting)
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_acquire_waits_when_limit_reached(self):
        """Test that rate limiter waits when limit is reached."""
        limiter = RateLimiter(max_requests=3, time_window=2)
        
        # Make 3 requests to reach limit
        for _ in range(3):
            await limiter.acquire()
        
        # This request should wait
        start_time = time.time()
        await limiter.acquire()
        elapsed = time.time() - start_time
        
        # Should have waited for old requests to expire
        assert elapsed >= 1.5  # Some wait time

    @pytest.mark.asyncio
    async def test_acquire_removes_old_requests(self):
        """Test that old requests are removed from the window."""
        limiter = RateLimiter(max_requests=2, time_window=1)
        
        # Make 2 requests
        await limiter.acquire()
        await limiter.acquire()
        
        # Wait for time window to pass
        await asyncio.sleep(1.1)
        
        # Should be able to make new requests without waiting
        start_time = time.time()
        await limiter.acquire()
        elapsed = time.time() - start_time
        
        assert elapsed < 0.5

    def test_get_stats(self):
        """Test getting rate limiter statistics."""
        limiter = RateLimiter(max_requests=10, time_window=60)
        
        stats = limiter.get_stats()
        
        assert stats["requests_in_window"] == 0
        assert stats["max_requests"] == 10
        assert stats["time_window"] == 60
        assert stats["available"] == 10

    @pytest.mark.asyncio
    async def test_get_stats_with_requests(self):
        """Test statistics after making requests."""
        limiter = RateLimiter(max_requests=5, time_window=60)
        
        # Make 3 requests
        for _ in range(3):
            await limiter.acquire()
        
        stats = limiter.get_stats()
        
        assert stats["requests_in_window"] == 3
        assert stats["max_requests"] == 5
        assert stats["available"] == 2

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test that concurrent requests are properly limited."""
        # Use shorter time window for testing
        limiter = RateLimiter(max_requests=5, time_window=2)
        
        # Try to make 10 concurrent requests
        tasks = [limiter.acquire() for _ in range(10)]
        
        start_time = time.time()
        await asyncio.gather(*tasks)
        elapsed = time.time() - start_time
        
        # Should complete (5 immediately, 5 after waiting ~2 seconds)
        assert elapsed >= 1.5  # Some wait time for second batch
        
        # All requests should be processed
        stats = limiter.get_stats()
        assert stats["requests_in_window"] == 10


class TestGetRateLimiter:
    """Tests for get_rate_limiter function."""

    def test_get_rate_limiter_singleton(self):
        """Test that get_rate_limiter returns a singleton."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        
        assert limiter1 is limiter2

    def test_get_rate_limiter_defaults(self):
        """Test that default rate limiter has correct settings."""
        limiter = get_rate_limiter()
        
        assert limiter.max_requests == 60
        assert limiter.time_window == 60
