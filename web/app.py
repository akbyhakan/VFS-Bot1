"""FastAPI web dashboard with WebSocket support for VFS-Bot."""

import logging
import os
from pathlib import Path
from typing import List
import ipaddress

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.services.otp_webhook_routes import router as otp_router
from src.middleware.request_tracking import RequestTrackingMiddleware
from src.middleware import CorrelationMiddleware
from src.middleware.error_handler import ErrorHandlerMiddleware
from web.middleware import SecurityHeadersMiddleware
from web.routes import (
    auth_router,
    users_router,
    appointments_router,
    payment_router,
    bot_router,
    health_router,
    dashboard_router,
    proxy_router,
    webhook_router,
)
from web.routes.bot import websocket_endpoint
from web.routes.dashboard import serve_react_app

logger = logging.getLogger(__name__)


def validate_cors_origins(origins_str: str) -> List[str]:
    """
    Validate and parse CORS origins, blocking wildcard and localhost in production.

    Args:
        origins_str: Comma-separated list of allowed origins

    Returns:
        List of validated origin strings

    Raises:
        ValueError: If wildcard is used in production environment
    """
    env = os.getenv("ENV", "production").lower()

    # Parse origins first
    origins = [origin.strip() for origin in origins_str.split(",") if origin.strip()]
    
    # Production-specific validation
    if env not in {"development", "dev", "testing", "test", "local"}:
        # More precise localhost detection
        invalid = []
        for o in origins:
            # Check for wildcard
            if o == "*":
                invalid.append(o)
            # Check for localhost (exact match or with port)
            elif o.startswith("http://localhost") or o.startswith("https://localhost"):
                invalid.append(o)
            # Check for 127.0.0.1
            elif "127.0.0.1" in o:
                invalid.append(o)
        
        if invalid:
            logger.warning(f"Removing insecure CORS origins in production: {invalid}")
            origins = [o for o in origins if o not in invalid]
            
            if not origins:
                logger.error("All CORS origins were insecure and removed. Using empty list.")
    
    # Additional check: fail-fast if wildcard in production
    if env == "production" and "*" in origins:
        raise ValueError("Wildcard CORS origin ('*') not allowed in production")

    return origins


def get_real_client_ip(request: Request) -> str:
    """
    Get real client IP with trusted proxy validation and IP format verification.
    
    Security: Only trust X-Forwarded-For from known proxies and validate
    IPs to prevent rate limit bypass attacks.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address
    """
    trusted_proxies_str = os.getenv("TRUSTED_PROXIES", "")
    trusted_proxies = set(p.strip() for p in trusted_proxies_str.split(",") if p.strip())
    
    client_host = request.client.host if request.client else "unknown"
    
    def is_valid_ip(ip_str: str) -> bool:
        """Validate IP address format."""
        try:
            ipaddress.ip_address(ip_str)
            return True
        except ValueError:
            return False
    
    # Only trust forwarded headers from known proxies
    if trusted_proxies and client_host in trusted_proxies:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Parse all IPs in X-Forwarded-For chain
            ips = [ip.strip() for ip in forwarded.split(",")]
            # Return the first IP that is NOT a trusted proxy (rightmost untrusted IP)
            for ip in reversed(ips):
                if ip not in trusted_proxies and is_valid_ip(ip):
                    return ip
        
        # Fallback to X-Real-IP if present and not a trusted proxy
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            real_ip = real_ip.strip()
            if real_ip not in trusted_proxies and is_valid_ip(real_ip):
                return real_ip
    
    # Return client_host if it's a valid IP, otherwise return "unknown"
    return client_host if is_valid_ip(client_host) else "unknown"


# Create FastAPI app
app = FastAPI(title="VFS-Bot Dashboard", version="2.0.0")


# Configure middleware (order matters!)
# 1. Error handling middleware first (catches all errors)
app.add_middleware(ErrorHandlerMiddleware)

# 2. Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# 3. Correlation ID middleware for request tracking
app.add_middleware(CorrelationMiddleware)

# 3. Configure CORS
allowed_origins_str = os.getenv(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
)
allowed_origins = validate_cors_origins(allowed_origins_str)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "X-CSRF-Token",
    ],
    expose_headers=["X-Total-Count", "X-Page", "X-Per-Page"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# 4. Add request tracking middleware
app.add_middleware(RequestTrackingMiddleware)


# Initialize rate limiter with improved IP detection
limiter = Limiter(key_func=get_real_client_ip)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Mount static files
static_dir = Path(__file__).parent / "static"
dist_dir = static_dir / "dist"

if dist_dir.exists():
    # Serve React app static assets
    app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")

if static_dir.exists():
    # Mount other static files (for backward compatibility)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Include routers
app.include_router(otp_router)  # OTP webhook routes
app.include_router(webhook_router)  # Per-user webhook routes
app.include_router(auth_router)  # /api/auth/*
app.include_router(users_router)  # /api/users/*
app.include_router(appointments_router)  # /api/appointment-requests/*, /api/countries/*
app.include_router(payment_router)  # /api/payment-card/*, /api/payment/*
app.include_router(proxy_router)  # /api/proxy/*
app.include_router(bot_router)  # /api/bot/*, /api/logs, /api/errors/*
app.include_router(health_router)  # /health, /ready, /metrics
app.include_router(dashboard_router)  # /errors.html


# WebSocket endpoint (must be added directly, not via router)
app.websocket("/ws")(websocket_endpoint)


# Catch-all route for React SPA - MUST be last!
@app.get("/", response_class=HTMLResponse)
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_frontend(request, full_path: str = ""):
    """Serve React SPA for all non-API routes."""
    return await serve_react_app(request, full_path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
