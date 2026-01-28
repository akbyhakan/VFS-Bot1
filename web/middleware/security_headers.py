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

        # Content Security Policy with nonce support
        # IMPORTANT: Currently 'unsafe-inline' and 'unsafe-eval' are still present for 
        # React/Vite compatibility. The nonce is generated and available in request.state.csp_nonce
        # for future use, but provides NO security benefit while 'unsafe-inline' is present.
        # According to CSP spec, 'unsafe-inline' is ignored when nonces are present in CSP2+ browsers,
        # but 'unsafe-eval' still allows arbitrary code execution.
        # 
        # TODO: Remove 'unsafe-inline' and 'unsafe-eval' once the React/Vite build pipeline
        # is updated to inject nonces into generated scripts and styles.
        # Until then, this provides infrastructure for future security improvements.
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
