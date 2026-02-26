"""FastAPI web dashboard with WebSocket support for VFS-Bot."""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src import __version__
from src.core.auth import get_token_blacklist, init_token_blacklist
from src.core.auth.token_blacklist import PersistentTokenBlacklist
from src.core.infra.startup_validator import log_security_warnings
from src.middleware import CorrelationMiddleware
from src.middleware.error_handler import ErrorHandlerMiddleware
from src.middleware.request_tracking import RequestTrackingMiddleware
from src.models.db_factory import DatabaseFactory
from src.services.otp_manager.otp_webhook_routes import router as otp_router
from web.api_versioning import setup_versioned_routes
from web.cors import validate_cors_origins
from web.ip_utils import get_real_client_ip
from web.middleware import (
    HTTPSRedirectMiddleware,
    RateLimitHeadersMiddleware,
    SecurityHeadersMiddleware,
)
from web.routes import (
    dashboard_router,
    health_router,
    sms_webhook_router,
    webhook_router,
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
* 💳 **Payment Integration** - Secure payment card management (PCI-DSS compliant)
* 📧 **Notifications** - Email and webhook notifications for appointments
* 🔌 **Webhook Support** - Real-time updates via webhooks
* 🌐 **Proxy Support** - Rotating proxy management
* 📊 **Monitoring** - Health checks and metrics endpoints

### Authentication

All protected endpoints require a Bearer token in the Authorization header:

```
Authorization: Bearer <your-token>
```

Obtain a token via the `/api/auth/login` endpoint.

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

    # 0. HTTPS redirect - must be FIRST (before any other middleware)
    # Only active in production environments
    if not _is_dev:
        app.add_middleware(HTTPSRedirectMiddleware)

    # 1. Error handling middleware (catches all errors)
    app.add_middleware(ErrorHandlerMiddleware)

    # 2. Security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Correlation ID middleware for request tracking
    app.add_middleware(CorrelationMiddleware)

    # 4. Configure CORS
    allowed_origins_str = os.getenv(
        "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
    )
    allowed_origins = validate_cors_origins(allowed_origins_str)

    if not allowed_origins:
        if env not in ("development", "dev", "local", "testing", "test"):
            raise RuntimeError(
                "CRITICAL: No valid CORS origins configured for production. "
                "Set CORS_ALLOWED_ORIGINS in .env (e.g., 'https://yourdomain.com'). "
                "Application cannot start without valid CORS configuration in production."
            )

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
            "X-CSRF-Token",
        ],
        expose_headers=[
            "X-Total-Count",
            "X-Page",
            "X-Per-Page",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
        max_age=3600,  # Cache preflight requests for 1 hour
    )

    # 5. Add request tracking middleware
    app.add_middleware(RequestTrackingMiddleware)

    # 6. Add rate limit headers middleware
    app.add_middleware(RateLimitHeadersMiddleware)

    # Initialize rate limiter with improved IP detection
    limiter = Limiter(key_func=get_real_client_ip)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Initialize custom rate limiter for rate limit headers
    from src.core.rate_limiting import get_rate_limiter

    app.state.custom_rate_limiter = get_rate_limiter()

    # Mount static files
    static_dir = Path(__file__).parent / "static"
    dist_dir = static_dir / "dist"

    if dist_dir.exists():
        # Serve React app static assets
        app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")

    # Include non-versioned routers
    app.include_router(otp_router)       # External: SMS OTP webhooks (/api/webhook/sms/*)
    app.include_router(webhook_router)   # Per-user webhook CRUD + OTP receiver (/api/webhook/*)
                                         # Note: CRUD endpoints use JWT auth but are kept under
                                         # /api/webhook/ (not /api/v1/) for URL consistency
                                         # with the OTP receiver endpoint
    app.include_router(sms_webhook_router)  # External: SMS Forwarder webhooks (/webhook/sms/*)
    app.include_router(health_router)    # /health, /ready, /metrics
    app.include_router(dashboard_router) # /errors.html

    # Setup versioned API routes (v1)
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
