"""Kubernetes probe endpoints (liveness, readiness, startup)."""

import os
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Response

from web.dependencies import bot_state

router = APIRouter(tags=["health"])


def get_version() -> str:
    """
    Get application version from centralized source.

    Returns:
        Version string
    """
    from src import __version__

    return __version__


@router.get("/api/status")
async def get_status() -> Dict[str, Any]:
    """
    Get current bot status.

    Returns:
        Status dictionary
    """
    return {
        "running": bot_state.get_running(),
        "status": bot_state.get_status(),
        "last_check": bot_state.get_last_check(),
        "read_only": bot_state.get_read_only(),
        "stats": {
            "slots_found": bot_state.get_slots_found(),
            "appointments_booked": bot_state.get_appointments_booked(),
            "active_users": bot_state.get_active_users(),
        },
    }


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for monitoring and container orchestration.

    Returns:
        Health status with system information
    """
    from src.utils.metrics import get_metrics

    from .diagnostics import (
        check_database,
        check_notification_health,
        check_proxy_health,
        check_redis,
    )

    db_health_result = await check_database()
    db_healthy = db_health_result.get("status") == "healthy"
    bot_metrics = await get_metrics()

    # Check if bot is experiencing errors
    snapshot = await bot_metrics.get_snapshot()

    # Configurable health threshold (default 50%)
    health_threshold = float(os.getenv("BOT_HEALTH_THRESHOLD", "50.0"))
    bot_healthy = snapshot.success_rate > health_threshold

    circuit_breaker_healthy = not (snapshot.circuit_breaker_trips > 0 and bot_state.get_running())

    # Check notification service health
    notification_health = await check_notification_health()

    # Check Redis health
    redis_health = await check_redis()

    # Check proxy health
    proxy_health = await check_proxy_health()

    # Determine overall status based on component health
    # Redis unhealthy results in degraded status (not unhealthy) since it can fallback
    # Proxy is informational only - doesn't affect overall status unless all proxies are down
    if db_healthy and bot_healthy and circuit_breaker_healthy:
        if redis_health.get("status") == "unhealthy" or proxy_health.get("status") == "unhealthy":
            overall_status = "degraded"
        else:
            overall_status = "healthy"
    elif db_healthy:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": get_version(),
        "uptime_seconds": snapshot.uptime_seconds,
        "components": {
            "database": db_health_result,
            "redis": redis_health,
            "bot": {
                "status": "healthy" if bot_healthy else "degraded",
                "running": bot_state.get_running(),
                "success_rate": snapshot.success_rate,
            },
            "circuit_breaker": {
                "status": "healthy" if circuit_breaker_healthy else "open",
                "trips": snapshot.circuit_breaker_trips,
            },
            "notifications": notification_health,
            "proxy": proxy_health,
        },
        "metrics": {
            "total_checks": snapshot.total_checks,
            "slots_found": snapshot.slots_found,
            "appointments_booked": snapshot.appointments_booked,
            "active_users": snapshot.active_users,
        },
    }


@router.get("/health/live")
async def liveness_probe() -> Dict[str, str]:
    """
    Kubernetes liveness probe - checks if application is running.

    This endpoint always returns 200 if the app is running.
    Used to detect if the application needs to be restarted.

    Returns:
        Liveness status
    """
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/ready")
@router.get("/health/ready")
async def readiness_probe(response: Response) -> Dict[str, Any]:
    """
    Kubernetes readiness probe - checks if application is ready to serve traffic.

    This endpoint checks critical dependencies like database connectivity.
    Returns 503 if the service is not ready.

    Returns:
        Readiness status

    Raises:
        HTTPException: 503 if service is not ready
    """
    from .diagnostics import check_database, check_encryption, check_redis

    # Check critical services
    checks = {
        "database": await check_database(),
        "redis": await check_redis(),
        "encryption": await check_encryption(),
    }

    all_healthy = all(c.get("status") == "healthy" for c in checks.values())

    if not all_healthy:
        response.status_code = 503

    return {
        "status": "ready" if all_healthy else "not_ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@router.get("/health/startup")
async def startup_probe() -> Dict[str, str]:
    """
    Kubernetes startup probe - checks if application has started.

    Used by Kubernetes to know when the app has finished starting.

    Returns:
        Startup status
    """
    return {"status": "started", "timestamp": datetime.now(timezone.utc).isoformat()}
