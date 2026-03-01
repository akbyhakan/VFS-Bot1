"""FastAPI web dashboard with WebSocket support for VFS-Bot."""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from loguru import logger

from src.core.auth import get_token_blacklist, init_token_blacklist
from src.core.auth.token_blacklist import PersistentTokenBlacklist
from src.core.config.settings import get_settings
from src.core.infra.startup_validator import log_security_warnings
from src.models.db_factory import DatabaseFactory
from web.api_versioning import setup_versioned_routes
from web.app_config import (
    configure_middleware,
    get_openapi_metadata,
    mount_static_files,
    register_exception_handlers,
    register_infrastructure_routers,
    register_webhook_routers,
    register_websocket_and_spa,
)
from web.cors import validate_cors_origins


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

    # Guard: env_override must not bypass production security
    if env_override is not None:
        actual_env = get_validated_environment()
        if actual_env not in ("development", "dev", "local", "testing", "test"):
            logger.warning(
                f"env_override='{env_override}' ignored in {actual_env} environment"
            )
            env_override = None

    # Determine environment for OpenAPI configuration
    env = env_override if env_override is not None else get_validated_environment()
    _is_dev = env in ("development", "dev", "local", "testing", "test")

    # Create FastAPI app with OpenAPI documentation and lifespan
    app = FastAPI(lifespan=lifespan, **get_openapi_metadata(_is_dev))

    # Run startup security validation if enabled
    if run_security_validation:
        log_security_warnings(strict=True)

    # Configure middleware (order matters!)
    allowed_origins = validate_cors_origins(get_settings().cors_allowed_origins)
    configure_middleware(app, allowed_origins, _is_dev)

    # Mount React frontend static assets
    mount_static_files(app)

    # ──────────────────────────────────────────────────────────────
    # EXTERNAL WEBHOOK RECEIVERS (Unversioned — Intentional)
    # ──────────────────────────────────────────────────────────────
    # Not under /api/v1: URLs are hardcoded in 150+ field devices.
    # Auth: Webhook HMAC signature (not JWT).
    register_webhook_routers(app)

    # ──────────────────────────────────────────────────────────────
    # INFRASTRUCTURE (Unversioned — Standard practice)
    # ──────────────────────────────────────────────────────────────
    register_infrastructure_routers(app)

    # ──────────────────────────────────────────────────────────────
    # VERSIONED API (v1) — Used by the React frontend
    # ──────────────────────────────────────────────────────────────
    setup_versioned_routes(app)

    # RFC 7807 exception handlers
    register_exception_handlers(app)

    # WebSocket endpoint + React SPA catch-all (MUST be last)
    register_websocket_and_spa(app)

    return app


if __name__ == "__main__":
    import uvicorn

    from src.core.infra.runners import parse_safe_port

    # Security: Default to localhost only. Set UVICORN_HOST=0.0.0.0 to bind to all interfaces.
    # Note: This is more secure by default. For production, use a proper WSGI server.
    host = os.getenv("UVICORN_HOST", "127.0.0.1")
    port = parse_safe_port()
    uvicorn.run("web.app:create_app", host=host, port=port, factory=True)
