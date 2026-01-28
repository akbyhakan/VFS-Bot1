"""Security headers middleware for VFS-Bot web application."""

import secrets
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""
        # Generate unique nonce for this request
        nonce = secrets.token_urlsafe(16)
        
        # Store nonce in request state for templates
        request.state.csp_nonce = nonce
        
        response = await call_next(request)

        # Prevent clickjacking attacks
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS protection (for older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Content Security Policy with nonce-based security
        # Note: This project uses React/Vite SPA. The 'unsafe-inline' and 'unsafe-eval'
        # are kept for compatibility with the build system. For full nonce integration,
        # the build process needs to be updated to inject nonces into generated scripts.
        # TODO: Integrate nonce support into React/Vite build pipeline
        # For now, we keep 'unsafe-inline' and 'unsafe-eval' but provide nonce for future use
        csp_policy = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' 'unsafe-inline' 'unsafe-eval'; "
            f"style-src 'self' 'nonce-{nonce}' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none';"
        )
        response.headers["Content-Security-Policy"] = csp_policy

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        return response
