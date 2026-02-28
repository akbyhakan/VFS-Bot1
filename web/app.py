"""FastAPI web dashboard with WebSocket support for VFS-Bot."""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from src import __version__
from src.core.auth import get_token_blacklist, init_token_blacklist
from src.core.auth.token_blacklist import PersistentTokenBlacklist
from src.core.config.settings import get_settings
from src.core.infra.startup_validator import log_security_warnings
from src.models.db_factory import DatabaseFactory
from src.services.otp_manager.otp_webhook_routes import router as otp_router
from web.api_versioning import setup_versioned_routes
from web.cors import validate_cors_origins
from web.middleware import (
    ErrorHandlerMiddleware,
    SecurityHeadersMiddleware,
)
from web.routes import (
    dashboard_router,
    health_router,
    sms_webhook_router,
    webhook_otp_router,
)
from web.routes.dashboard import serve_react_app
from web.websocket.handler import websocket_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown.

    Handles:
    - Database connection on startup
    - Database cleanup on shutdown
    - OTP service cleanup on shutdown
    - Dropdown sync scheduler startup and shutdown
    """
    # Startup
    logger.info("FastAPI application starting up...")
    dropdown_scheduler = None
    try:
        # Ensure database is connected
        db = await DatabaseFactory.ensure_connected()
        logger.info("Database connection established via DatabaseFactory")

        # Initialize persistent token blacklist with database
        init_token_blacklist(db)
        logger.info("Token blacklist initialized with database persistence")

        # Load existing blacklisted tokens from database
        # Non-critical: Allow app to start even if loading fails
        try:
            blacklist = get_token_blacklist()
            if isinstance(blacklist, PersistentTokenBlacklist):
                count = await blacklist.load_from_database()
                logger.info(f"Loaded {count} blacklisted tokens from database")
        except Exception as e:
            logger.warning(f"Failed to load blacklisted tokens from database: {e}")
            logger.info("Application will continue with empty blacklist")

        # Start dropdown sync scheduler
        # Non-critical: Allow app to start even if scheduler fails
        try:
            from src.services.data_sync.dropdown_sync_scheduler import DropdownSyncScheduler

            dropdown_scheduler = DropdownSyncScheduler(db)
            dropdown_scheduler.start()
            logger.info("Dropdown sync scheduler started (weekly Saturday 00:00 UTC)")
        except Exception as e:
            logger.warning(f"Failed to start dropdown sync scheduler: {e}")
            logger.info("Application will continue without automatic dropdown sync")
    except Exception as e:
        logger.error(f"Failed to connect database during startup: {e}")
        raise

    yield

    # Shutdown
    logger.info("FastAPI application shutting down...")

    # Stop dropdown sync scheduler
    if dropdown_scheduler:
        try:
            dropdown_scheduler.stop()
            logger.info("Dropdown sync scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping dropdown sync scheduler: {e}")

    # Stop OTP cleanup scheduler
    try:
        from src.services.otp_manager.otp_webhook import get_otp_service

        otp_service = get_otp_service()
        await asyncio.wait_for(otp_service.stop_cleanup_scheduler(), timeout=5)
        logger.info("OTP service cleanup completed")
    except asyncio.TimeoutError:
        logger.warning("OTP service cleanup timed out after 5s")
    except Exception as e:
        logger.error(f"Error cleaning up OTP service: {e}")

    # Close database with timeout protection
    try:
        await asyncio.wait_for(DatabaseFactory.close_instance(), timeout=10)
        logger.info("DatabaseFactory instance closed successfully")
    except asyncio.TimeoutError:
        logger.error("DatabaseFactory close timed out after 10s")
    except Exception as e:
        logger.error(f"Error closing DatabaseFactory: {e}")


def create_app(run_security_validation: bool = True, env_override: Optional[str] = None) -> FastAPI:
    """
    Factory function to create FastAPI application instance.

    Args:
        run_security_validation: Whether to run security warnings check (default: True)
        env_override: Override environment name for testing (default: None)

    Returns:
        Configured FastAPI application instance
    """
    from web.cors import get_validated_environment

    # Determine environment for OpenAPI configuration
    env = env_override if env_override is not None else get_validated_environment()
    _is_dev = env in ("development", "dev", "local", "testing", "test")

    # Create FastAPI app with enhanced OpenAPI documentation and lifespan
    app = FastAPI(
        title="VFS-Bot Dashboard API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if _is_dev else None,
        redoc_url="/redoc" if _is_dev else None,
        openapi_url="/openapi.json" if _is_dev else None,
        description="""
## VFS Global Appointment Booking Bot API

**VFS-Bot** is an automated appointment booking system for VFS Global visa application centers.

### Features

* 🔐 **Secure Authentication** - JWT-based authentication with token refresh
* 👥 **Multi-User Support** - Manage multiple user accounts and appointments
* 🤖 **Automated Booking** - Smart bot with anti-detection features
* 💳 **Payment Integration** - Secure payment card management (encrypted storage)
* 📧 **Notifications** - Email and webhook notifications for appointments
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
        contact={
            "name": "VFS-Bot Support",
            "url": "https://github.com/akbyhakan/VFS-Bot1",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
        openapi_tags=[
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
        ],
    )

    # Run startup security validation if enabled
    if run_security_validation:
        log_security_warnings(strict=True)

    # Configure middleware (order matters!)

    # 1. Error handling middleware (catches all errors)
    app.add_middleware(ErrorHandlerMiddleware)

    # 2. Security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Configure CORS
    allowed_origins = validate_cors_origins(get_settings().cors_allowed_origins)

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

    # Mount static files
    static_dir = Path(__file__).parent / "static"
    dist_dir = static_dir / "dist"

    if dist_dir.exists():
        # Serve React app static assets
        app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")

    # ──────────────────────────────────────────────────────────────
    # EXTERNAL WEBHOOK RECEIVERS (Unversioned — Intentional)
    # ──────────────────────────────────────────────────────────────
    # These routers are NOT under /api/v1 because:
    # - They are called by external systems (SMS Forwarder, OTP providers)
    # - Their URLs are hardcoded in 150+ field devices / external services
    # - Versioning would break all existing integrations
    # - Auth: Webhook HMAC signature (not JWT)
    #
    # Path map:
    #   /api/webhook/sms/appointment  → otp_router          (SMS provider → appointment OTP)
    #   /api/webhook/sms/payment      → otp_router          (SMS provider → payment OTP)
    #   /api/webhook/otp/wait         → otp_router          (Long-polling OTP retrieval)
    #   /api/webhook/otp/{token}      → webhook_otp_router   (Per-user OTP receiver)
    #   /webhook/sms/{token}          → sms_webhook_router   (SMS Forwarder app)
    #   /webhook/sms/{token}/status   → sms_webhook_router   (Webhook status check)
    #   /webhook/sms/{token}/test     → sms_webhook_router   (Webhook connectivity test)
    # ──────────────────────────────────────────────────────────────
    app.include_router(otp_router)
    app.include_router(webhook_otp_router)
    app.include_router(sms_webhook_router)

    # ──────────────────────────────────────────────────────────────
    # INFRASTRUCTURE (Unversioned — Standard practice)
    # ──────────────────────────────────────────────────────────────
    app.include_router(health_router)       # /health, /ready, /metrics
    app.include_router(dashboard_router)    # React SPA dashboard router

    # ──────────────────────────────────────────────────────────────
    # VERSIONED API (v1) — Used by the React frontend
    # ──────────────────────────────────────────────────────────────
    # All frontend-facing, JWT-protected routes live under /api/v1.
    # Includes webhook_accounts_router for CRUD (/api/v1/webhook/users/…).

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Convert FastAPI HTTPException to RFC 7807 Problem Details format."""
        status_code = exc.status_code

        error_types = {
            400: "urn:vfsbot:error:bad-request",
            401: "urn:vfsbot:error:unauthorized",
            403: "urn:vfsbot:error:forbidden",
            404: "urn:vfsbot:error:not-found",
            409: "urn:vfsbot:error:conflict",
            422: "urn:vfsbot:error:validation",
            429: "urn:vfsbot:error:rate-limit",
            500: "urn:vfsbot:error:internal-server",
            503: "urn:vfsbot:error:service-unavailable",
        }

        error_titles = {
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            409: "Conflict",
            422: "Validation Error",
            429: "Too Many Requests",
            500: "Internal Server Error",
            503: "Service Unavailable",
        }

        content = {
            "type": error_types.get(status_code, f"urn:vfsbot:error:http-{status_code}"),
            "title": error_titles.get(status_code, "Error"),
            "status": status_code,
            "detail": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "instance": request.url.path,
        }

        headers = getattr(exc, "headers", None) or {}

        return JSONResponse(
            status_code=status_code,
            content=content,
            headers=headers,
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Convert Pydantic validation errors to RFC 7807 format."""
        errors = {}
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
            errors[field] = error["msg"]

        return JSONResponse(
            status_code=422,
            content={
                "type": "urn:vfsbot:error:validation",
                "title": "Validation Error",
                "status": 422,
                "detail": "Request validation failed",
                "instance": request.url.path,
                "errors": errors,
            },
            media_type="application/problem+json",
        )

    setup_versioned_routes(app)

    # WebSocket endpoint (must be added directly, not via router)
    app.websocket("/ws")(websocket_endpoint)

    # Catch-all route for React SPA - MUST be last!
    @app.get("/", response_class=HTMLResponse)
    @app.get("/{full_path:path}", response_class=HTMLResponse)
    async def serve_frontend(request, full_path: str = ""):
        """Serve React SPA for all non-API routes."""
        return await serve_react_app(request, full_path)

    return app


if __name__ == "__main__":
    import uvicorn

    from src.core.infra.runners import parse_safe_port

    # Security: Default to localhost only. Set UVICORN_HOST=0.0.0.0 to bind to all interfaces.
    # Note: This is more secure by default. For production, use a proper WSGI server.
    host = os.getenv("UVICORN_HOST", "127.0.0.1")
    port = parse_safe_port()
    uvicorn.run("web.app:create_app", host=host, port=port, factory=True)
