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

    All frontend-facing, JWT-protected routes are registered under /api/v1.

    The following routers are intentionally NOT included here:
    - sms_webhook_router  → /webhook/sms/*       (SMS Forwarder app integration)
    - webhook_otp_router  → /api/webhook/otp/*    (Per-user OTP receiver)
    - otp_router          → /api/webhook/sms/*    (SMS provider webhooks)

    These serve external systems with fixed, published URLs and use
    HMAC webhook-signature authentication instead of JWT. Adding them
    under /api/v1 would break 150+ field-device configurations and
    the webhook URLs returned by webhook_accounts_router CRUD endpoints.

    Args:
        app: FastAPI application instance
    """
    # Import routers here to avoid circular imports
    from web.routes import (
        appointments_router,
        audit_router,
        auth_router,
        bot_router,
        config_router,
        dropdown_sync_router,
        payment_router,
        proxy_router,
        vfs_accounts_router,
        webhook_accounts_router,
    )

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
    api_v1_router.include_router(webhook_accounts_router)

    # Register the v1 router with the app
    app.include_router(api_v1_router)
