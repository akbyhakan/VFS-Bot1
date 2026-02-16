"""Routes package for VFS-Bot web application."""

from .appointments import router as appointments_router
from .audit import router as audit_router
from .auth import router as auth_router
from .bot import router as bot_router
from .dashboard import router as dashboard_router
from .dropdown_sync import router as dropdown_sync_router
from .health import router as health_router
from .payment import router as payment_router
from .proxy import router as proxy_router
from .sms_webhook import router as sms_webhook_router
from .users import router as users_router
from .webhook import router as webhook_router

__all__ = [
    "auth_router",
    "users_router",
    "appointments_router",
    "audit_router",
    "payment_router",
    "bot_router",
    "health_router",
    "dashboard_router",
    "dropdown_sync_router",
    "proxy_router",
    "webhook_router",
    "sms_webhook_router",
]
