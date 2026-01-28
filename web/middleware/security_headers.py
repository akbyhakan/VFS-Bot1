"""Security headers middleware for VFS-Bot web application."""

import os
import secrets
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses with environment-aware CSP."""

    def __init__(self, app, strict_csp: bool = None):
        super().__init__(app)
        if strict_csp is None:
            env = os.getenv("ENV", "production").lower()
            self.strict_csp = env not in {"development", "dev", "testing", "test", "local"}
        else:
            self.strict_csp = strict_csp

    async def dispatch(self, request: Request, call_next):
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce
        
        response = await call_next(request)

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        if self.strict_csp:
            csp_policy = (
                "default-src 'self'; "
                f"script-src 'self' 'nonce-{nonce}'; "
                f"style-src 'self' 'nonce-{nonce}'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' ws: wss:; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "upgrade-insecure-requests;"
            )
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        else:
            csp_policy = (
                "default-src 'self'; "
                f"script-src 'self' 'nonce-{nonce}' 'unsafe-inline' 'unsafe-eval'; "
                f"style-src 'self' 'nonce-{nonce}' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' ws: wss: http://localhost:*; "
                "frame-ancestors 'none';"
            )

        response.headers["Content-Security-Policy"] = csp_policy
        return response
