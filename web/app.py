"""FastAPI web dashboard with WebSocket support for VFS-Bot."""

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.services.otp_webhook_routes import router as otp_router
from src.middleware.request_tracking import RequestTrackingMiddleware
from src.middleware import CorrelationMiddleware
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
)
from web.routes.bot import websocket_endpoint
from web.routes.dashboard import serve_react_app

logger = logging.getLogger(__name__)


def get_real_client_ip(request: Request) -> str:
    """
    Get real client IP considering reverse proxies.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Client IP address
    """
    # Check X-Forwarded-For header (set by reverse proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in the list is the original client
        return forwarded.split(",")[0].strip()
    
    # Check X-Real-IP header (alternative)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback to direct connection
    return request.client.host if request.client else "unknown"


# Create FastAPI app
app = FastAPI(title="VFS-Bot Dashboard", version="2.0.0")


# Configure middleware (order matters!)
# 1. Security headers middleware first
app.add_middleware(SecurityHeadersMiddleware)

# 2. Correlation ID middleware for request tracking
app.add_middleware(CorrelationMiddleware)

# 3. Configure CORS
allowed_origins_str = os.getenv(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
)
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]

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
