"""API versioning support for VFS-Bot web application.

This module provides centralized API versioning to maintain backward compatibility
and allow for future API evolution without breaking existing integrations.
"""

from fastapi import APIRouter, FastAPI

# API v1 router - all versioned routes should be included here
api_v1_router = APIRouter(prefix="/api/v1")


def setup_versioned_routes(app: FastAPI) -> None:
    """
    Configure versioned API routes on the FastAPI application.

    This function should be called from the main app factory to register
    all versioned API routes under /api/v1 prefix.

    Args:
        app: FastAPI application instance
    """
    # Import routers here to avoid circular imports
    from web.routes import (
        appointments_router,
        audit_router,
        auth_router,
        bot_router,
        dropdown_sync_router,
        payment_router,
        proxy_router,
        vfs_accounts_router,
    )
    from web.routes.config import router as config_router

    # Include all API routers under v1
    api_v1_router.include_router(auth_router)
    api_v1_router.include_router(vfs_accounts_router)
    api_v1_router.include_router(appointments_router)
    api_v1_router.include_router(audit_router)
    api_v1_router.include_router(payment_router)
    api_v1_router.include_router(proxy_router)
    api_v1_router.include_router(bot_router)
    api_v1_router.include_router(dropdown_sync_router)
    api_v1_router.include_router(config_router)

    # Register the v1 router with the app
    app.include_router(api_v1_router)
