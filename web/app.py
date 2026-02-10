"""FastAPI web dashboard with WebSocket support for VFS-Bot."""

import asyncio
import ipaddress
import os
import re
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.core.auth import init_token_blacklist, get_token_blacklist
from src.core.auth.token_blacklist import PersistentTokenBlacklist
from src.core.startup_validator import log_security_warnings
from src.middleware import CorrelationMiddleware
from src.middleware.error_handler import ErrorHandlerMiddleware
from src.middleware.request_tracking import RequestTrackingMiddleware
from src.models.db_factory import DatabaseFactory
from src.services.otp_webhook_routes import router as otp_router
from src.utils.log_sanitizer import sanitize_log_value
from web.api_versioning import setup_versioned_routes
from web.middleware import SecurityHeadersMiddleware
from web.routes import (
    dashboard_router,
    health_router,
    sms_webhook_router,
    webhook_router,
)
from web.routes.bot import websocket_endpoint
from web.routes.dashboard import serve_react_app


def _is_valid_ip(ip_str: str) -> bool:
    """Validate IP address format."""
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown.

    Handles:
    - Database connection on startup
    - Database cleanup on shutdown
    - OTP service cleanup on shutdown
    """
    # Startup
    logger.info("FastAPI application starting up...")
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
    except Exception as e:
        logger.error(f"Failed to connect database during startup: {e}")
        raise

    yield

    # Shutdown
    logger.info("FastAPI application shutting down...")

    # Stop OTP cleanup scheduler
    try:
        from src.services.otp_webhook import get_otp_service

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


# Valid environment names (whitelist for security)
VALID_ENVIRONMENTS = frozenset(
    {"production", "staging", "development", "dev", "testing", "test", "local"}
)


def get_validated_environment() -> str:
    """
    Get and validate environment name with whitelist check.

    Returns:
        Validated environment name (defaults to 'production' for unknown values)
    """
    env = os.getenv("ENV", "production").lower()
    if env not in VALID_ENVIRONMENTS:
        logger.warning(
            f"Unknown environment '{sanitize_log_value(env, max_length=50)}', "
            f"defaulting to 'production' for security"
        )
        return "production"
    return env


# Comprehensive localhost detection pattern
_LOCALHOST_PATTERN = re.compile(
    r'^https?://'
    r'(localhost(\.|:|/|$)|127\.0\.0\.1|(\[::1\]|::1)|0\.0\.0\.0)'
    r'(:\d+)?'
    r'(/.*)?$',
    re.IGNORECASE
)


def _is_localhost_origin(origin: str) -> bool:
    """Check if origin is a localhost variant (including IPv6)."""
    # Check for localhost subdomains and variations
    # Extract hostname after protocol to avoid false positives
    if '://' in origin:
        # Extract the part after protocol (hostname and possibly port/path)
        after_protocol = origin.split('://', 1)[1]
        # Extract just the hostname (before port or path)
        hostname = after_protocol.split(':')[0].split('/')[0].lower()
        # Check if hostname starts with 'localhost.' or ends with '.localhost'
        if hostname.startswith('localhost.') or hostname.endswith('.localhost'):
            return True
    return bool(_LOCALHOST_PATTERN.match(origin))


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
    env = get_validated_environment()

    # Parse origins first
    origins = [origin.strip() for origin in origins_str.split(",") if origin.strip()]

    # Fail-fast: Block wildcard in production BEFORE filtering
    if env == "production" and "*" in origins:
        raise ValueError("Wildcard CORS origin ('*') not allowed in production")

    # Production-specific validation
    if env not in {"development", "dev", "testing", "test", "local"}:
        # More precise localhost detection
        invalid = []
        for o in origins:
            # Check for wildcard
            if o == "*":
                invalid.append(o)
            # Check for localhost variants (including IPv6, 0.0.0.0, subdomain bypass)
            elif _is_localhost_origin(o):
                invalid.append(o)

        if invalid:
            logger.warning(f"Removing insecure CORS origins in production: {invalid}")
            origins = [o for o in origins if o not in invalid]

            if not origins:
                logger.error("All CORS origins were insecure and removed. Using empty list.")

    return origins


@lru_cache(maxsize=1)
def _get_trusted_proxies() -> frozenset[str]:
    """Parse trusted proxies once and cache."""
    trusted_proxies_str = os.getenv("TRUSTED_PROXIES", "")
    return frozenset(p.strip() for p in trusted_proxies_str.split(",") if p.strip())


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
    trusted_proxies = _get_trusted_proxies()

    client_host = request.client.host if request.client else "unknown"

    # Only trust forwarded headers from known proxies
    if trusted_proxies and client_host in trusted_proxies:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Parse all IPs in X-Forwarded-For chain
            ips = [ip.strip() for ip in forwarded.split(",")]
            # Return the first IP that is NOT a trusted proxy (rightmost untrusted IP)
            for ip in reversed(ips):
                if ip not in trusted_proxies and _is_valid_ip(ip):
                    return ip

        # Fallback to X-Real-IP if present and not a trusted proxy
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            real_ip = real_ip.strip()
            if real_ip not in trusted_proxies and _is_valid_ip(real_ip):
                return real_ip

    # Return client_host if it's a valid IP, otherwise return "unknown"
    return client_host if _is_valid_ip(client_host) else "unknown"


def create_app(
    run_security_validation: bool = True,
    env_override: Optional[str] = None
) -> FastAPI:
    """
    Factory function to create FastAPI application instance.
    
    Args:
        run_security_validation: Whether to run security warnings check (default: True)
        env_override: Override environment name for testing (default: None)
    
    Returns:
        Configured FastAPI application instance
    """
    # Determine environment for OpenAPI configuration
    env = env_override if env_override is not None else get_validated_environment()
    _is_dev = env in ("development", "dev", "local", "testing", "test")

    # Create FastAPI app with enhanced OpenAPI documentation and lifespan
    app = FastAPI(
        title="VFS-Bot Dashboard API",
        version="2.0.0",
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
                "name": "users",
                "description": "User management operations",
            },
            {
                "name": "appointments",
                "description": "Appointment request and booking operations",
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
                "name": "webhooks",
                "description": "Webhook configuration and OTP delivery",
            },
            {
                "name": "SMS Webhook",
                "description": "Dynamic SMS webhook endpoints for VFS accounts",
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
    # 1. Error handling middleware first (catches all errors)
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

    # 5. Add request tracking middleware
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

    # Include non-versioned routers (webhooks, health, etc.)
    app.include_router(otp_router)  # OTP webhook routes
    app.include_router(webhook_router)  # Per-user webhook routes
    app.include_router(sms_webhook_router)  # SMS webhook routes for VFS accounts
    app.include_router(health_router)  # /health, /ready, /metrics
    app.include_router(dashboard_router)  # /errors.html
    
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


# Create module-level app for backward compatibility
app = create_app()


if __name__ == "__main__":
    import uvicorn

    from src.core.runners import parse_safe_port

    # Security: Default to localhost only. Set UVICORN_HOST=0.0.0.0 to bind to all interfaces.
    # Note: This is more secure by default. For production, use a proper WSGI server.
    host = os.getenv("UVICORN_HOST", "127.0.0.1")
    port = parse_safe_port()
    uvicorn.run(app, host=host, port=port)
