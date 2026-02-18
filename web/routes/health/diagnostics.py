"""Detailed health checks for database, Redis, encryption, notifications, proxies, and external services."""

import os
import time
from typing import Any, Dict

from loguru import logger


async def check_database_health() -> bool:
    """
    Check database connectivity with actual query.

    Returns:
        True if database is healthy, False otherwise
    """
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
        from src.services.notification.notification import NotificationService

        # Check if notification service can be initialized
        # We don't actually send a notification, just check the service is available
        NotificationService(config={})

        # Basic health check - service is available
        return {
            "status": "healthy",
            "telegram_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
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
