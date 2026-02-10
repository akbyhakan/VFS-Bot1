"""Rate limiting headers middleware for API responses."""

from typing import Callable, Optional

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class RateLimitHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add rate limit information to response headers.

    Adds the following headers:
    - X-RateLimit-Limit: Maximum requests allowed in the window
    - X-RateLimit-Remaining: Remaining requests in current window
    - X-RateLimit-Reset: Unix timestamp when the rate limit resets
    """

    def __init__(self, app: ASGIApp):
        """
        Initialize rate limit headers middleware.

        Args:
            app: ASGI application
        """
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add rate limit headers to response.

        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain

        Returns:
            Response with rate limit headers
        """
        # Process the request
        response = await call_next(request)

        # Check if rate limiter is available in app state
        if hasattr(request.app.state, "limiter"):
            try:
                from src.utils.security.rate_limiter import RateLimiter

                limiter: Optional[RateLimiter] = getattr(request.app.state, "limiter", None)

                if limiter and hasattr(limiter, "get_rate_limit_info"):
                    # Get client identifier (IP address or user ID)
                    client_id = request.client.host if request.client else "unknown"

                    # Get rate limit info for this client
                    rate_info = await limiter.get_rate_limit_info(client_id)

                    if rate_info:
                        # Add headers
                        response.headers["X-RateLimit-Limit"] = str(rate_info.get("limit", 100))
                        response.headers["X-RateLimit-Remaining"] = str(
                            rate_info.get("remaining", 0)
                        )
                        response.headers["X-RateLimit-Reset"] = str(rate_info.get("reset", 0))

                        logger.debug(
                            f"Rate limit headers added for {client_id}: "
                            f"{rate_info.get('remaining')}/{rate_info.get('limit')}"
                        )
            except Exception as e:
                # Don't fail the request if rate limit header addition fails
                logger.debug(f"Could not add rate limit headers: {e}")

        return response
