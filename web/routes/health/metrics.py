"""Prometheus export, bot metrics, and system metrics endpoints."""

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from web.dependencies import bot_state, metrics

from .diagnostics import (
    check_database,
    check_external_services,
    check_redis,
)
from .probes import get_version

router = APIRouter(tags=["health"])


def get_uptime() -> float:
    """
    Get service uptime in seconds.

    Returns:
        Uptime in seconds
    """
    from web.dependencies import metrics

    if "start_time" in metrics:
        uptime = (datetime.now(timezone.utc) - metrics["start_time"]).total_seconds()
        return uptime
    return 0.0


def get_circuit_breaker_status(snapshot: Any) -> Dict[str, Any]:
    """
    Get circuit breaker status from metrics snapshot.

    Args:
        snapshot: Metrics snapshot object

    Returns:
        Dictionary with circuit breaker status
    """
    return {
        "status": "closed" if snapshot.circuit_breaker_trips == 0 else "open",
        "total_trips": snapshot.circuit_breaker_trips,
        "healthy": snapshot.circuit_breaker_trips == 0,
    }


def get_rate_limiter_status() -> Dict[str, Any]:
    """
    Get rate limiter status.

    Returns:
        Dictionary with rate limiter status
    """
    return {
        "available": True,
        "note": "Rate limiter is active",
    }


def increment_metric(name: str, count: int = 1) -> None:
    """Increment a metric counter."""
    if name in metrics:
        metrics[name] += count


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed health check with component diagnostics.

    Returns:
        Comprehensive health status with system metrics
    """
    try:
        import psutil
    except ImportError:
        # If psutil is not installed, provide basic health check
        from src.utils.metrics import get_metrics

        db_health_result = await check_database()
        db_healthy = db_health_result.get("status") == "healthy"
        bot_metrics = await get_metrics()
        snapshot = await bot_metrics.get_snapshot()

        # Configurable health threshold (default 50%)
        health_threshold = float(os.getenv("BOT_HEALTH_THRESHOLD", "50.0"))
        bot_healthy = snapshot.success_rate > health_threshold

        # Get circuit breaker and rate limiter status
        circuit_breaker_status = get_circuit_breaker_status(snapshot)
        rate_limiter_stats = get_rate_limiter_status()

        # Check external services
        external_services = await check_external_services()

        # Check Redis health
        redis_health = await check_redis()

        return {
            "status": "healthy" if (db_healthy and bot_healthy) else "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": get_version(),
            "python_version": sys.version,
            "system": {"note": "psutil not installed - install for detailed system metrics"},
            "components": {
                "database": db_health_result,
                "redis": redis_health,
                "bot": {
                    "status": "healthy" if bot_healthy else "degraded",
                    "running": bot_state.get("running", False),
                    "success_rate": snapshot.success_rate,
                    "total_checks": snapshot.total_checks,
                },
                "circuit_breaker": circuit_breaker_status,
                "rate_limiter": rate_limiter_stats,
            },
            "external_services": external_services,
        }

    # System metrics (requires psutil)
    from src.utils.metrics import get_metrics

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    # Database check
    db_health_result = await check_database()
    db_healthy = db_health_result.get("status") == "healthy"

    # Bot metrics
    bot_metrics = await get_metrics()
    snapshot = await bot_metrics.get_snapshot()

    # Configurable health threshold (default 50%)
    health_threshold = float(os.getenv("BOT_HEALTH_THRESHOLD", "50.0"))
    bot_healthy = snapshot.success_rate > health_threshold

    # Get circuit breaker and rate limiter status
    circuit_breaker_status = get_circuit_breaker_status(snapshot)
    rate_limiter_stats = get_rate_limiter_status()

    # Check external services
    external_services = await check_external_services()

    # Check Redis health
    redis_health = await check_redis()

    return {
        "status": "healthy" if (db_healthy and bot_healthy) else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": get_version(),
        "python_version": sys.version,
        "system": {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "percent_used": memory.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent_used": disk.percent,
            },
        },
        "components": {
            "database": db_health_result,
            "redis": redis_health,
            "bot": {
                "status": "healthy" if bot_healthy else "degraded",
                "running": bot_state.get_running(),
                "success_rate": snapshot.success_rate,
                "total_checks": snapshot.total_checks,
            },
            "circuit_breaker": circuit_breaker_status,
            "rate_limiter": rate_limiter_stats,
        },
        "external_services": external_services,
    }


@router.get("/api/metrics")
async def get_bot_metrics() -> Dict[str, Any]:
    """
    Get detailed bot metrics.

    Returns:
        Comprehensive metrics dictionary
    """
    from src.utils.metrics import get_metrics

    bot_metrics = await get_metrics()
    return await bot_metrics.get_metrics_dict()


@router.get("/metrics")
async def get_metrics_endpoint() -> Dict[str, Any]:
    """
    Prometheus-compatible metrics endpoint.

    Returns:
        Metrics dictionary
    """
    from src.utils.metrics import get_metrics as get_bot_metrics_instance

    bot_metrics = await get_bot_metrics_instance()
    snapshot = await bot_metrics.get_snapshot()

    # Legacy compatibility with existing metrics structure
    uptime = (datetime.now(timezone.utc) - metrics["start_time"]).total_seconds()

    return {
        "uptime_seconds": uptime,
        "requests_total": metrics["requests_total"],
        "requests_success": metrics["requests_success"],
        "requests_failed": metrics["requests_failed"],
        "success_rate": metrics["requests_success"] / max(metrics["requests_total"], 1),
        "slots_checked": snapshot.total_checks,
        "slots_found": snapshot.slots_found,
        "appointments_booked": snapshot.appointments_booked,
        "captchas_solved": metrics["captchas_solved"],
        "errors_by_type": metrics["errors"],
        "bot_status": bot_state.get_status(),
        # New metrics from BotMetrics
        "circuit_breaker_trips": snapshot.circuit_breaker_trips,
        "active_users": snapshot.active_users,
        "avg_response_time_ms": snapshot.avg_response_time_ms,
        "requests_per_minute": snapshot.requests_per_minute,
    }


@router.get("/metrics/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics() -> str:
    """
    Prometheus text format metrics.

    Returns:
        Prometheus-formatted metrics using prometheus_client registry
    """
    from src.utils.prometheus_metrics import get_metrics

    # Get metrics from prometheus_client registry
    return get_metrics().decode("utf-8")
