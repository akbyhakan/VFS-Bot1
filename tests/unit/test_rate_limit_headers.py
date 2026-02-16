"""Tests for rate limit headers middleware."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from src.core.rate_limiting import RateLimiter
from web.middleware.rate_limit_headers import RateLimitHeadersMiddleware


@pytest.fixture
def app_with_middleware():
    """Create FastAPI app with RateLimitHeadersMiddleware."""
    app = FastAPI()

    # Add middleware
    app.add_middleware(RateLimitHeadersMiddleware)

    # Add custom rate limiter to app state
    app.state.custom_rate_limiter = RateLimiter(max_requests=100, time_window=60)

    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}

    return app


def test_rate_limit_headers_added(app_with_middleware):
    """Test rate limit headers are added to response."""
    client = TestClient(app_with_middleware)

    response = client.get("/test")

    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers


def test_rate_limit_headers_values(app_with_middleware):
    """Test rate limit header values are correct."""
    client = TestClient(app_with_middleware)

    response = client.get("/test")

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "100"
    # Remaining should be 99 after one request
    assert int(response.headers["X-RateLimit-Remaining"]) == 99
    # Reset should be a valid timestamp
    assert int(response.headers["X-RateLimit-Reset"]) > 0


def test_rate_limit_headers_decrements(app_with_middleware):
    """Test rate limit remaining decrements with each request."""
    client = TestClient(app_with_middleware)

    response1 = client.get("/test")
    remaining1 = int(response1.headers["X-RateLimit-Remaining"])

    response2 = client.get("/test")
    remaining2 = int(response2.headers["X-RateLimit-Remaining"])

    # Remaining should decrement
    assert remaining2 < remaining1


def test_rate_limit_headers_without_custom_limiter():
    """Test middleware works without custom_rate_limiter in app state."""
    app = FastAPI()
    app.add_middleware(RateLimitHeadersMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}

    client = TestClient(app)

    response = client.get("/test")

    # Should work but not add headers
    assert response.status_code == 200
    # Headers should not be present
    assert "X-RateLimit-Limit" not in response.headers


@pytest.mark.asyncio
async def test_get_rate_limit_info():
    """Test RateLimiter.get_rate_limit_info method."""
    limiter = RateLimiter(max_requests=50, time_window=60)

    # Get rate limit info
    info = await limiter.get_rate_limit_info("test_client")

    assert info["limit"] == 50
    assert info["remaining"] == 50  # No requests made yet
    assert info["reset"] > 0  # Valid timestamp


@pytest.mark.asyncio
async def test_get_rate_limit_info_after_requests():
    """Test rate limit info after making requests."""
    limiter = RateLimiter(max_requests=50, time_window=60)

    # Make some requests
    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()

    # Get rate limit info
    info = await limiter.get_rate_limit_info("test_client")

    assert info["limit"] == 50
    assert info["remaining"] == 47  # 50 - 3 = 47
    assert info["reset"] > 0


@pytest.mark.asyncio
async def test_rate_limit_headers_middleware_exception_handling():
    """Test middleware handles exceptions gracefully."""
    app = FastAPI()
    app.add_middleware(RateLimitHeadersMiddleware)

    # Set a mock limiter that raises exception
    mock_limiter = Mock()
    mock_limiter.get_rate_limit_info = AsyncMock(side_effect=Exception("Test error"))
    app.state.custom_rate_limiter = mock_limiter

    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}

    client = TestClient(app)

    # Should not crash despite exception
    response = client.get("/test")
    assert response.status_code == 200
