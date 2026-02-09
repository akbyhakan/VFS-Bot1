"""API redirect middleware for backward compatibility.

Redirects legacy /api/* routes to /api/v1/* for backward compatibility
while allowing clients to migrate to versioned endpoints.
"""

import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

logger = logging.getLogger(__name__)


class APIVersionRedirectMiddleware(BaseHTTPMiddleware):
    """
    Middleware to redirect legacy API calls to versioned endpoints.
    
    Redirects /api/* (not /api/v1/*) to /api/v1/* with HTTP 308 (Permanent Redirect)
    to maintain backward compatibility while encouraging migration to versioned endpoints.
    
    Preserves query parameters and uses 308 to maintain the HTTP method (POST, PUT, etc.).
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and redirect if necessary.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint in the chain
            
        Returns:
            Response object (redirect or normal response)
        """
        path = request.url.path
        
        # Check if path starts with /api/ but NOT /api/v1/
        if path.startswith("/api/") and not path.startswith("/api/v1/"):
            # Build new versioned path
            new_path = path.replace("/api/", "/api/v1/", 1)
            
            # Preserve query parameters
            query_string = str(request.url.query)
            new_url = new_path
            if query_string:
                new_url = f"{new_path}?{query_string}"
            
            logger.info(f"Redirecting legacy API call: {path} -> {new_path}")
            
            # Use 308 Permanent Redirect to preserve HTTP method and body
            return RedirectResponse(url=new_url, status_code=308)
        
        # Not an API route or already versioned - continue normally
        return await call_next(request)
