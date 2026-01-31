"""Request tracking middleware for distributed tracing."""

import uuid
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """Add request ID to all requests for tracing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with tracking ID.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/route handler

        Returns:
            Response with request ID header
        """
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Store in request state
        request.state.request_id = request_id

        # Add to logging context
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
            },
        )

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
            },
        )

        return response
