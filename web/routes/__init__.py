"""Routes package for VFS-Bot web application."""

from .auth import router as auth_router
from .users import router as users_router
from .appointments import router as appointments_router
from .payment import router as payment_router
from .bot import router as bot_router
from .health import router as health_router
from .dashboard import router as dashboard_router
from .proxy import router as proxy_router
from .webhook import router as webhook_router

__all__ = [
    "auth_router",
    "users_router",
    "appointments_router",
    "payment_router",
    "bot_router",
    "health_router",
    "dashboard_router",
    "proxy_router",
    "webhook_router",
]
