"""Security headers middleware for VFS-Bot web application."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.environment import Environment


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses.

    Headers follow OWASP 2025 recommendations.
    Adapted for single-user deployment.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # HSTS — force HTTPS for 1 year, include subdomains
        # No 'preload' — single-user app doesn't need Google preload list submission
        # Only in production to avoid breaking local dev with self-signed certs
        if Environment.is_production():
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Content Security Policy
        # 'self' for default; 'unsafe-inline' for style-src needed by React/Tailwind
        # connect-src includes wss:/ws: for WebSocket endpoint (/ws)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self' wss: ws:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        # Prevent Adobe Flash/Acrobat cross-domain policy loading
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        return response
