"""Health check, diagnostics, and metrics routes package."""

from fastapi import APIRouter

from .diagnostics import (
    check_captcha_service,
    check_database,
    check_database_health,
    check_encryption,
    check_external_services,
    check_notification_health,
    check_proxy_health,
    check_redis,
    check_vfs_api_health,
)
from .metrics import (
    get_circuit_breaker_status,
    get_rate_limiter_status,
    get_uptime,
    increment_metric,
)
from .probes import get_version

# Combine all sub-routers into a single router
router = APIRouter()

# Import sub-routers
from . import metrics as _metrics_module  # noqa: E402
from . import probes as _probes_module  # noqa: E402

router.include_router(_probes_module.router)
router.include_router(_metrics_module.router)

__all__ = [
    "router",
    "check_database",
    "check_database_health",
    "check_redis",
    "check_encryption",
    "check_notification_health",
    "check_proxy_health",
    "check_vfs_api_health",
    "check_captcha_service",
    "check_external_services",
    "get_version",
    "get_uptime",
    "get_circuit_breaker_status",
    "get_rate_limiter_status",
    "increment_metric",
]
