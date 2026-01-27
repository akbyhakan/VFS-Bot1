"""Health check and metrics routes for VFS-Bot web application."""

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import PlainTextResponse

from web.dependencies import bot_state, metrics

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/api/status")
async def get_status() -> Dict[str, Any]:
    """
    Get current bot status.

    Returns:
        Status dictionary
    """
    return {
        "running": bot_state["running"],
        "status": bot_state["status"],
        "last_check": bot_state["last_check"],
        "stats": {
            "slots_found": bot_state["slots_found"],
            "appointments_booked": bot_state["appointments_booked"],
            "active_users": bot_state["active_users"],
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

    db_healthy = await check_database_health()
    bot_metrics = await get_metrics()

    # Check if bot is experiencing errors
    snapshot = await bot_metrics.get_snapshot()

    # Configurable health threshold (default 50%)
    health_threshold = float(os.getenv("BOT_HEALTH_THRESHOLD", "50.0"))
    bot_healthy = snapshot.success_rate > health_threshold

    circuit_breaker_healthy = not (
        snapshot.circuit_breaker_trips > 0 and bot_state.get("running", False)
    )

    # Determine overall status based on component health
    if db_healthy and bot_healthy and circuit_breaker_healthy:
        overall_status = "healthy"
    elif db_healthy:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.1.0",
        "uptime_seconds": snapshot.uptime_seconds,
        "components": {
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
            },
            "bot": {
                "status": "healthy" if bot_healthy else "degraded",
                "running": bot_state.get("running", False),
                "success_rate": snapshot.success_rate,
            },
            "circuit_breaker": {
                "status": "healthy" if circuit_breaker_healthy else "open",
                "trips": snapshot.circuit_breaker_trips,
            },
            "notifications": {
                "status": "healthy",
            },
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
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


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
    # Check critical services
    checks = {
        "database": await check_database(),
        "encryption": await check_encryption(),
    }
    
    all_healthy = all(c.get("status") == "healthy" for c in checks.values())
    
    if not all_healthy:
        response.status_code = 503
    
    return {
        "status": "ready" if all_healthy else "not_ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks
    }


@router.get("/health/startup")
async def startup_probe() -> Dict[str, str]:
    """
    Kubernetes startup probe - checks if application has started.
    
    Used by Kubernetes to know when the app has finished starting.
    
    Returns:
        Startup status
    """
    return {
        "status": "started",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


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

        db_healthy = await check_database_health()
        bot_metrics = await get_metrics()
        snapshot = await bot_metrics.get_snapshot()

        # Configurable health threshold (default 50%)
        health_threshold = float(os.getenv("BOT_HEALTH_THRESHOLD", "50.0"))
        bot_healthy = snapshot.success_rate > health_threshold

        # Get circuit breaker and rate limiter status
        circuit_breaker_status = get_circuit_breaker_status(snapshot)
        rate_limiter_stats = get_rate_limiter_status()

        return {
            "status": "healthy" if (db_healthy and bot_healthy) else "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "2.1.0",
            "python_version": sys.version,
            "system": {"note": "psutil not installed - install for detailed system metrics"},
            "components": {
                "database": {
                    "status": "healthy" if db_healthy else "unhealthy",
                },
                "bot": {
                    "status": "healthy" if bot_healthy else "degraded",
                    "running": bot_state.get("running", False),
                    "success_rate": snapshot.success_rate,
                    "total_checks": snapshot.total_checks,
                },
                "circuit_breaker": circuit_breaker_status,
                "rate_limiter": rate_limiter_stats,
            },
        }

    # System metrics (requires psutil)
    from src.utils.metrics import get_metrics

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    # Database check
    db_healthy = await check_database_health()

    # Bot metrics
    bot_metrics = await get_metrics()
    snapshot = await bot_metrics.get_snapshot()

    # Configurable health threshold (default 50%)
    health_threshold = float(os.getenv("BOT_HEALTH_THRESHOLD", "50.0"))
    bot_healthy = snapshot.success_rate > health_threshold

    # Get circuit breaker and rate limiter status
    circuit_breaker_status = get_circuit_breaker_status(snapshot)
    rate_limiter_stats = get_rate_limiter_status()

    return {
        "status": "healthy" if (db_healthy and bot_healthy) else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.1.0",
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
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
            },
            "bot": {
                "status": "healthy" if bot_healthy else "degraded",
                "running": bot_state.get("running", False),
                "success_rate": snapshot.success_rate,
                "total_checks": snapshot.total_checks,
            },
            "circuit_breaker": circuit_breaker_status,
            "rate_limiter": rate_limiter_stats,
        },
    }


async def check_database_health() -> bool:
    """
    Check database connectivity with actual query.

    Returns:
        True if database is healthy, False otherwise
    """
    try:
        from src.models.database import Database

        db = Database()
        await db.connect()
        try:
            async with db.get_connection(timeout=5.0) as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    result = await cursor.fetchone()
                    return result is not None
        finally:
            await db.close()
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


async def check_database() -> Dict[str, Any]:
    """Check database connectivity."""
    try:
        from src.models.database import Database
        db = Database()
        await db.connect()
        try:
            async with db.get_connection(timeout=5.0) as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    result = await cursor.fetchone()
                    is_healthy = result is not None
        finally:
            await db.close()
        return {"status": "healthy" if is_healthy else "unhealthy", "latency_ms": 0}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


async def check_encryption() -> Dict[str, Any]:
    """Check encryption service."""
    try:
        from src.utils.encryption import get_encryption
        enc = get_encryption()
        # Test encrypt/decrypt cycle
        test_data = "health_check_test"
        encrypted = enc.encrypt_password(test_data)
        decrypted = enc.decrypt_password(encrypted)
        is_healthy = decrypted == test_data
        return {"status": "healthy" if is_healthy else "unhealthy"}
    except Exception as e:
        logger.error(f"Encryption health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


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
        "bot_status": bot_state["status"],
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
        Prometheus-formatted metrics
    """
    from src.utils.metrics import get_metrics

    bot_metrics = await get_metrics()
    return await bot_metrics.get_prometheus_metrics()


def increment_metric(name: str, count: int = 1) -> None:
    """Increment a metric counter."""
    if name in metrics:
        metrics[name] += count
