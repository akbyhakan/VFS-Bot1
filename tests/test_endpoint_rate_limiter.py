"""Tests for per-endpoint rate limiting."""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.security.endpoint_rate_limiter import EndpointRateLimiter


@pytest.mark.asyncio
async def test_endpoint_rate_limiter_initialization():
    """Test EndpointRateLimiter initializes with correct limits."""
    limiter = EndpointRateLimiter()

    # Check all endpoint limiters are created
    assert "login" in limiter._limiters
    assert "slot_check" in limiter._limiters
    assert "booking" in limiter._limiters
    assert "centres" in limiter._limiters
    assert "default" in limiter._limiters

    # Check default limits are correct
    assert limiter._limiters["login"].max_requests == 3
    assert limiter._limiters["slot_check"].max_requests == 30
    assert limiter._limiters["booking"].max_requests == 10
    assert limiter._limiters["centres"].max_requests == 5
    assert limiter._limiters["default"].max_requests == 60


@pytest.mark.asyncio
async def test_endpoint_rate_limiter_custom_limits():
    """Test EndpointRateLimiter can be initialized with custom limits."""
    limiter = EndpointRateLimiter(
        login_limit=5, slot_check_limit=50, booking_limit=20, centres_limit=10, default_limit=100
    )

    assert limiter._limiters["login"].max_requests == 5
    assert limiter._limiters["slot_check"].max_requests == 50
    assert limiter._limiters["booking"].max_requests == 20
    assert limiter._limiters["centres"].max_requests == 10
    assert limiter._limiters["default"].max_requests == 100


@pytest.mark.asyncio
async def test_endpoint_rate_limiter_acquire():
    """Test that acquire allows requests within limits."""
    limiter = EndpointRateLimiter(login_limit=3, time_window=60)

    # Should succeed for 3 requests
    start = time.time()
    await limiter.acquire("login")
    await limiter.acquire("login")
    await limiter.acquire("login")
    elapsed = time.time() - start

    # Should complete quickly (< 1 second)
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_endpoint_rate_limiter_independent_limits():
    """Test that different endpoints have independent rate limits."""
    limiter = EndpointRateLimiter(login_limit=2, slot_check_limit=5, time_window=60)

    # Exhaust login limit
    await limiter.acquire("login")
    await limiter.acquire("login")

    # slot_check should still work independently
    start = time.time()
    await limiter.acquire("slot_check")
    await limiter.acquire("slot_check")
    elapsed = time.time() - start

    # Should complete quickly (< 1 second)
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_endpoint_rate_limiter_on_rate_limited():
    """Test that on_rate_limited enforces VFS-imposed rate limits."""
    limiter = EndpointRateLimiter()

    # Simulate VFS returning 429 with Retry-After
    limiter.on_rate_limited("login", 2)  # Wait 2 seconds

    # Next acquire should wait
    start = time.time()
    await limiter.acquire("login")
    elapsed = time.time() - start

    # Should have waited approximately 2 seconds
    assert elapsed >= 1.9  # Allow small margin for timing


@pytest.mark.asyncio
async def test_endpoint_rate_limiter_default_endpoint():
    """Test that unknown endpoints use default limiter."""
    limiter = EndpointRateLimiter(default_limit=5, time_window=60)

    # Use unknown endpoint - should use default limiter
    await limiter.acquire("unknown_endpoint")
    await limiter.acquire("another_unknown")

    # Check that default limiter was used
    default_stats = limiter.get_stats("default")
    # Both unknown endpoints should use the default limiter
    assert default_stats["requests_in_window"] >= 2


@pytest.mark.asyncio
async def test_endpoint_rate_limiter_get_stats():
    """Test get_stats returns correct statistics."""
    limiter = EndpointRateLimiter(login_limit=3, time_window=60)

    # Make some requests
    await limiter.acquire("login")
    await limiter.acquire("login")

    stats = limiter.get_stats("login")

    assert stats["requests_in_window"] == 2
    assert stats["max_requests"] == 3
    assert stats["available"] == 1
    assert stats["vfs_rate_limited"] is False


@pytest.mark.asyncio
async def test_endpoint_rate_limiter_get_stats_with_vfs_limit():
    """Test get_stats includes VFS rate limit information."""
    limiter = EndpointRateLimiter()

    # Simulate VFS rate limit
    limiter.on_rate_limited("booking", 10)

    stats = limiter.get_stats("booking")

    assert stats["vfs_rate_limited"] is True
    assert stats["vfs_wait_remaining"] > 0
    assert stats["vfs_wait_remaining"] <= 10


@pytest.mark.asyncio
async def test_endpoint_rate_limiter_get_all_stats():
    """Test get_all_stats returns statistics for all endpoints."""
    limiter = EndpointRateLimiter()

    # Make requests to different endpoints
    await limiter.acquire("login")
    await limiter.acquire("slot_check")
    await limiter.acquire("booking")

    all_stats = limiter.get_all_stats()

    # Check all endpoints are present
    assert "login" in all_stats
    assert "slot_check" in all_stats
    assert "booking" in all_stats
    assert "centres" in all_stats
    assert "default" in all_stats

    # Check each has correct structure
    assert all_stats["login"]["requests_in_window"] == 1
    assert all_stats["slot_check"]["requests_in_window"] == 1
    assert all_stats["booking"]["requests_in_window"] == 1


@pytest.mark.asyncio
async def test_endpoint_rate_limiter_vfs_limit_expires():
    """Test that VFS-imposed rate limits expire after waiting."""
    limiter = EndpointRateLimiter()

    # Set a very short VFS rate limit
    limiter.on_rate_limited("centres", 1)  # 1 second

    # Wait for it to expire
    await asyncio.sleep(1.1)

    # Next acquire should not wait
    start = time.time()
    await limiter.acquire("centres")
    elapsed = time.time() - start

    # Should complete quickly (< 0.5 seconds)
    assert elapsed < 0.5
