"""Request correlation ID middleware for distributed tracing."""

import contextvars
import uuid
from typing import Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging

# Context variable for request ID
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar('request_id', default='')

logger = logging.getLogger(__name__)


def get_request_id() -> str:
    """Get current request ID from context."""
    return request_id_var.get()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add correlation ID to requests for distributed tracing.
    
    The correlation ID is:
    1. Read from X-Request-ID header if present
    2. Generated as UUID4 if not present
    3. Stored in context variable for use in logging
    4. Added to response headers
    """
    
    HEADER_NAME = "X-Request-ID"
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request with correlation ID.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response with correlation ID header
        """
        # Get or generate request ID
        req_id = request.headers.get(self.HEADER_NAME)
        if not req_id:
            req_id = str(uuid.uuid4())
        
        # Store in context variable
        token = request_id_var.set(req_id)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Add to response headers
            response.headers[self.HEADER_NAME] = req_id
            
            return response
        finally:
            # Reset context variable
            request_id_var.reset(token)


class CorrelationIdFilter(logging.Filter):
    """Logging filter to add correlation ID to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add correlation ID to log record.
        
        Args:
            record: Log record
            
        Returns:
            True to allow record through
        """
        record.correlation_id = get_request_id() or '-'
        return True


def setup_correlation_logging():
    """Setup logging with correlation ID."""
    # Add filter to root logger
    correlation_filter = CorrelationIdFilter()
    
    for handler in logging.root.handlers:
        handler.addFilter(correlation_filter)
    
    # Update format to include correlation ID
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s'
    )
    
    for handler in logging.root.handlers:
        handler.setFormatter(formatter)
