"""Request correlation ID middleware for tracking requests across logs."""

import uuid
from contextvars import ContextVar
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable to store correlation ID for the current request
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation ID to all requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and add correlation ID.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler

        Returns:
            HTTP response with correlation ID header
        """
        # Get or generate correlation ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Store in context variable for access in logs
        correlation_id.set(request_id)

        # Process request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


def get_correlation_id() -> str:
    """
    Get the current request's correlation ID.

    Returns:
        Correlation ID string, or empty string if not set
    """
    return correlation_id.get()
