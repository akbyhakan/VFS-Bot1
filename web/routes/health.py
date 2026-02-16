"""Health check and metrics routes for VFS-Bot web application."""

import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse
from loguru import logger

from web.dependencies import bot_state, metrics

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

    db_health_result = await check_database()
    db_healthy = db_health_result.get("status") == "healthy"
    bot_metrics = await get_metrics()

    # Check if bot is experiencing errors
    snapshot = await bot_metrics.get_snapshot()

    # Configurable health threshold (default 50%)
    health_threshold = float(os.getenv("BOT_HEALTH_THRESHOLD", "50.0"))
    bot_healthy = snapshot.success_rate > health_threshold

    circuit_breaker_healthy = not (
        snapshot.circuit_breaker_trips > 0 and bot_state.get_running()
    )

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
        if redis_health.get("status") == "unhealthy":
            overall_status = "degraded"
        elif proxy_health.get("status") == "unhealthy":
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


async def check_database_health() -> bool:
    """
    Check database connectivity with actual query.

    Returns:
        True if database is healthy, False otherwise
    """
    import time

    try:
        from src.models.db_factory import DatabaseFactory

        db = await DatabaseFactory.ensure_connected()
        start_time = time.time()
        async with db.get_connection(timeout=5.0) as conn:
            result = await conn.fetchval("SELECT 1")
            latency_ms = (time.time() - start_time) * 1000
            logger.debug(f"Database health check latency: {latency_ms:.2f}ms")
            return result is not None
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


async def check_database() -> Dict[str, Any]:
    """Check database connectivity with latency measurement."""
    try:
        from src.models.db_factory import DatabaseFactory

        db = await DatabaseFactory.ensure_connected()
        start_time = time.time()
        async with db.get_connection(timeout=5.0) as conn:
            result = await conn.fetchval("SELECT 1")
            latency_ms = (time.time() - start_time) * 1000
            is_healthy = result is not None
        
        # Get pool stats
        pool_stats = db.get_pool_stats()
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "latency_ms": round(latency_ms, 2),
            "pool": {
                "size": pool_stats["pool_size"],
                "idle": pool_stats["pool_free"],
                "used": pool_stats["pool_used"],
                "utilization": pool_stats["utilization"],
            },
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "error": str(e), "latency_ms": 0}


async def check_redis() -> Dict[str, Any]:
    """
    Check Redis connectivity and health.

    Returns:
        Dictionary with Redis status, backend info, and optional latency
    """
    redis_url = os.getenv("REDIS_URL")

    if not redis_url:
        return {"status": "not_configured", "backend": "in-memory"}

    try:
        import redis

        start_time = time.time()
        client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5)

        # Test connection with PING
        result = client.ping()
        latency_ms = (time.time() - start_time) * 1000

        if result:
            return {"status": "healthy", "backend": "redis", "latency_ms": round(latency_ms, 2)}
        else:
            return {"status": "unhealthy", "backend": "redis", "error": "PING returned False"}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {"status": "unhealthy", "backend": "redis", "error": str(e)}


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


async def check_notification_health() -> Dict[str, Any]:
    """
    Check notification service health.

    Returns:
        Dictionary with notification service status
    """
    try:
        from src.services.notification import NotificationService

        # Check if notification service can be initialized
        # We don't actually send a notification, just check the service is available
        NotificationService(config={})

        # Basic health check - service is available
        return {
            "status": "healthy",
            "telegram_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
            "email_configured": bool(os.getenv("SMTP_SERVER")),
        }
    except Exception as e:
        logger.error(f"Notification health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


async def check_proxy_health() -> Dict[str, Any]:
    """
    Check proxy infrastructure health.

    Returns:
        Dictionary with proxy status and statistics
    """
    try:
        from src.models.db_factory import DatabaseFactory
        from src.repositories.proxy_repository import ProxyRepository

        db = await DatabaseFactory.ensure_connected()
        proxy_repo = ProxyRepository(db)
        
        # Get proxy statistics
        stats = await proxy_repo.get_stats()
        
        total = stats.get("total_proxies", 0)
        active = stats.get("active_proxies", 0)
        inactive = stats.get("inactive_proxies", 0)
        avg_failures = stats.get("avg_failure_count", 0.0)
        
        # Determine status based on proxy availability
        if total == 0:
            status = "not_configured"
        elif active == 0:
            status = "unhealthy"
        elif avg_failures > 5:  # High failure count threshold
            status = "degraded"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "total_proxies": total,
            "active_proxies": active,
            "inactive_proxies": inactive,
            "avg_failure_count": round(avg_failures, 2),
        }
    except Exception as e:
        # Proxy is optional infrastructure, so failures should not break health check
        logger.debug(f"Proxy health check failed (proxy is optional): {e}")
        return {
            "status": "not_configured",
            "total_proxies": 0,
        }


async def check_vfs_api_health() -> bool:
    """
    Check VFS API connectivity.

    Returns:
        True if VFS API is reachable
    """
    try:
        import aiohttp

        from src.services.vfs import get_vfs_api_base

        vfs_api_base = get_vfs_api_base()
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Just check if the base URL is reachable
            async with session.get(f"{vfs_api_base}/health", allow_redirects=False) as resp:
                return resp.status < 500
    except Exception as e:
        logger.debug(f"VFS API health check failed: {e}")
        return False


async def check_captcha_service() -> bool:
    """
    Check captcha service availability.

    Returns:
        True if captcha service is available
    """
    try:
        # Check if 2Captcha API key is configured
        api_key = os.getenv("CAPTCHA_API_KEY", "")
        if not api_key:
            logger.debug("Captcha service: No API key configured (manual mode)")
            return True  # Manual mode is still valid

        # If API key is configured, consider it healthy
        # (we don't actually call the API to avoid costs)
        return True
    except Exception as e:
        logger.debug(f"Captcha service health check failed: {e}")
        return False


async def check_external_services() -> Dict[str, Any]:
    """
    Check external service health.

    Returns:
        Dictionary of service names and their health status
    """
    proxy_health = await check_proxy_health()
    return {
        "vfs_api": await check_vfs_api_health(),
        "captcha_service": await check_captcha_service(),
        "notification_channels": (await check_notification_health()).get("status") == "healthy",
        "proxy": proxy_health,
    }


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


def increment_metric(name: str, count: int = 1) -> None:
    """Increment a metric counter."""
    if name in metrics:
        metrics[name] += count
