"""Application configuration helpers for FastAPI app factory.

This module extracts middleware configuration, router registration,
OpenAPI metadata, exception handlers, static file mounting, and SPA
routing from create_app() into focused helper functions.

Follows the same decomposition pattern as VFSBot.stop() in
src/services/bot/vfs_bot.py and setup_versioned_routes() in
web/api_versioning.py.
"""

from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src import __version__
from web.middleware import (
    ErrorHandlerMiddleware,
    SecurityHeadersMiddleware,
)
from web.exception_handlers import http_exception_handler, validation_exception_handler


def get_openapi_tags() -> List[Dict[str, str]]:
    """
    Return the OpenAPI tag definitions for the API documentation.

    Returns:
        List of tag definition dicts with 'name' and 'description' keys
    """
    return [
        {
            "name": "auth",
            "description": "Authentication and authorization operations",
        },
        {
            "name": "vfs-accounts",
            "description": "VFS account management operations",
        },
        {
            "name": "appointments",
            "description": "Appointment request and booking operations",
        },
        {
            "name": "audit",
            "description": "Audit log and security monitoring operations",
        },
        {
            "name": "payment",
            "description": "Payment card and transaction management",
        },
        {
            "name": "bot",
            "description": "Bot control and status operations",
        },
        {
            "name": "config",
            "description": "Runtime configuration management",
        },
        {
            "name": "dropdown-sync",
            "description": "VFS dropdown data synchronization and status monitoring",
        },
        {
            "name": "proxy",
            "description": "Proxy server management",
        },
        {
            "name": "webhook-sms",
            "description": "SMS OTP webhook endpoints for appointment and payment verification",
        },
        {
            "name": "webhook-accounts",
            "description": "Per-user webhook token management (CRUD)",
        },
        {
            "name": "webhook-otp",
            "description": "Per-user OTP receiver via unique webhook token",
        },
        {
            "name": "webhook-sms-forwarder",
            "description": "Dynamic SMS webhook endpoints via SMS Forwarder app",
        },
        {
            "name": "health",
            "description": "Service health and monitoring",
        },
    ]


def get_openapi_metadata(is_dev: bool) -> Dict[str, Any]:
    """
    Return the OpenAPI metadata dict for FastAPI app instantiation.

    Args:
        is_dev: Whether the app is running in a development environment.
                Controls whether interactive docs are enabled.

    Returns:
        Dictionary of keyword arguments suitable for FastAPI(**kwargs)
    """
    return {
        "title": "VFS-Bot Dashboard API",
        "version": __version__,
        "docs_url": "/docs" if is_dev else None,
        "redoc_url": "/redoc" if is_dev else None,
        "openapi_url": "/openapi.json" if is_dev else None,
        "description": """
## VFS Global Appointment Booking Bot API

**VFS-Bot** is an automated appointment booking system for VFS Global visa application centers.

### Features

* 🔐 **Secure Authentication** - JWT-based authentication with token refresh
* 👥 **Multi-User Support** - Manage multiple user accounts and appointments
* 🤖 **Automated Booking** - Smart bot with anti-detection features
* 💳 **Payment Integration** - Secure payment card management (encrypted storage)
* 📧 **Notifications** - Telegram and webhook notifications for appointments
* 🔌 **Webhook Support** - Real-time updates via webhooks
* 🌐 **Proxy Support** - Rotating proxy management
* 📊 **Monitoring** - Health checks and metrics endpoints

### Authentication

All protected endpoints require a Bearer token in the Authorization header:

```
Authorization: Bearer <your-token>
```

Obtain a token via the `/api/v1/auth/login` endpoint.

### Rate Limiting

API endpoints are rate-limited to prevent abuse:
- Login: 5 requests per minute
- General API: 100 requests per minute
- WebSocket: 10 messages per second

### Security

- All sensitive data is encrypted at rest
- HTTPS required in production
- CORS protection enabled
- SQL injection prevention
- XSS protection headers
- CSRF token validation
    """,
        "contact": {
            "name": "VFS-Bot Support",
            "url": "https://github.com/akbyhakan/VFS-Bot1",
        },
        "license_info": {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
        "openapi_tags": get_openapi_tags(),
    }


def configure_middleware(app: FastAPI, allowed_origins: list, is_dev: bool) -> None:
    """
    Configure all middleware on the FastAPI application (order matters).

    Registers in order:
    1. ErrorHandlerMiddleware — catches all unhandled errors
    2. SecurityHeadersMiddleware — adds security response headers
    3. CORSMiddleware — cross-origin resource sharing

    Args:
        app: FastAPI application instance
        allowed_origins: Validated list of allowed CORS origins
        is_dev: Whether the app is running in a development environment
    """
    # 1. Error handling middleware (catches all errors)
    app.add_middleware(ErrorHandlerMiddleware)

    # 2. Security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
        ],
        expose_headers=[
            "X-Total-Count",
            "X-Page",
            "X-Per-Page",
        ],
        max_age=3600,  # Cache preflight requests for 1 hour
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register RFC 7807 Problem Details exception handlers on the application.

    Args:
        app: FastAPI application instance
    """
    app.exception_handler(HTTPException)(http_exception_handler)
    app.exception_handler(RequestValidationError)(validation_exception_handler)


def mount_static_files(app: FastAPI) -> None:
    """
    Mount React frontend static assets if the dist directory exists.

    Args:
        app: FastAPI application instance
    """
    static_dir = Path(__file__).parent / "static"
    dist_dir = static_dir / "dist"

    if dist_dir.exists():
        # Serve React app static assets
        app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")


def register_webhook_routers(app: FastAPI) -> None:
    """
    Register unversioned external webhook routers on the application.

    These routers are NOT under /api/v1 because they are called by external
    systems (SMS Forwarder, OTP providers) whose URLs are hardcoded in 150+
    field devices and cannot be versioned without breaking integrations.
    Auth is via webhook HMAC signature rather than JWT.

    Path map:
      /api/webhook/sms/appointment  → otp_router          (SMS provider → appointment OTP)
      /api/webhook/sms/payment      → otp_router          (SMS provider → payment OTP)
      /api/webhook/otp/wait         → otp_router          (Long-polling OTP retrieval)
      /api/webhook/otp/{token}      → webhook_otp_router   (Per-user OTP receiver)
      /webhook/sms/{token}          → sms_webhook_router   (SMS Forwarder app)
      /webhook/sms/{token}/status   → sms_webhook_router   (Webhook status check)
      /webhook/sms/{token}/test     → sms_webhook_router   (Webhook connectivity test)

    Args:
        app: FastAPI application instance
    """
    from src.services.otp_manager.otp_webhook_routes import router as otp_router
    from web.routes import sms_webhook_router, webhook_otp_router

    app.include_router(otp_router)
    app.include_router(webhook_otp_router)
    app.include_router(sms_webhook_router)


def register_infrastructure_routers(app: FastAPI) -> None:
    """
    Register unversioned infrastructure routers (health, dashboard).

    Args:
        app: FastAPI application instance
    """
    from web.routes import dashboard_router, health_router

    app.include_router(health_router)      # /health, /ready, /metrics
    app.include_router(dashboard_router)   # React SPA dashboard router


def register_websocket_and_spa(app: FastAPI) -> None:
    """
    Register the WebSocket endpoint and the React SPA catch-all route.

    The WebSocket endpoint must be added directly (not via router).
    The SPA catch-all MUST be registered last so it does not shadow
    any API or infrastructure routes.

    Args:
        app: FastAPI application instance
    """
    from web.routes.dashboard import serve_react_app
    from web.websocket.handler import websocket_endpoint

    # WebSocket endpoint (must be added directly, not via router)
    app.websocket("/ws")(websocket_endpoint)

    # Catch-all route for React SPA - MUST be last!
    @app.get("/", response_class=HTMLResponse)
    @app.get("/{full_path:path}", response_class=HTMLResponse)
    async def serve_frontend(request: Request, full_path: str = ""):
        """Serve React SPA for all non-API routes."""
        return await serve_react_app(request, full_path)
