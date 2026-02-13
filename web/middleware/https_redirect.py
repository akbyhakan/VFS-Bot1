"""HTTPS redirect middleware for production environments."""

import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from fastapi import Request


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Redirect HTTP requests to HTTPS in production.
    
    Respects X-Forwarded-Proto header for reverse proxy setups.
    Excludes health check endpoints to avoid breaking load balancer checks.
    """

    EXCLUDED_PATHS = frozenset({"/health", "/ready"})

    async def dispatch(self, request: Request, call_next):
        # Skip if already HTTPS (direct or via proxy)
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        
        if proto == "https" or request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)
        
        # Redirect to HTTPS
        url = request.url.replace(scheme="https")
        return RedirectResponse(url=str(url), status_code=301)
