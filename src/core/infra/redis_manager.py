"""Centralized Redis connection manager with singleton pattern."""

import os
import threading
from typing import TYPE_CHECKING, Optional

from loguru import logger

from src.utils.masking import mask_database_url

if TYPE_CHECKING:
    import redis as redis_module


class RedisManager:
    """
    Singleton factory for Redis connections.

    Provides a shared Redis client instance across the application.
    Auto-detects connection from REDIS_URL env var.
    Gracefully falls back to None when Redis is unavailable.

    Example:
        ```python
        client = RedisManager.get_client()
        if client is not None:
            client.ping()
        ```
    """

    _instance: "Optional[redis_module.Redis]" = None
    _lock = threading.Lock()
    _initialized = False

    @classmethod
    def get_client(cls) -> "Optional[redis_module.Redis]":
        """
        Get shared Redis client instance.

        Returns the same client on repeated calls (singleton).
        Returns None if Redis is not configured or unavailable.

        Returns:
            Redis client instance, or None if unavailable
        """
        if cls._initialized:
            return cls._instance

        with cls._lock:
            if cls._initialized:
                return cls._instance

            cls._instance = cls._create_client()
            cls._initialized = True

        return cls._instance

    @classmethod
    def _create_client(cls) -> "Optional[redis_module.Redis]":
        """
        Create Redis client from REDIS_URL env var.

        Returns:
            Redis client, or None if connection fails or URL not set
        """
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            logger.debug("REDIS_URL not set; Redis features will be disabled")
            return None

        try:
            import redis

            client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            try:
                client.ping()
            except Exception as ping_err:
                logger.warning(
                    f"RedisManager: connected to Redis "
                    f"({mask_database_url(redis_url)}) but ping failed: {ping_err}. "
                    "Redis-dependent features will be disabled."
                )
                return None
            logger.info(f"RedisManager connected: {mask_database_url(redis_url)}")
            return client
        except Exception as e:
            logger.warning(
                f"RedisManager: failed to connect to Redis "
                f"({mask_database_url(redis_url)}): {e}. "
                "Redis-dependent features will be disabled."
            )
            return None

    @classmethod
    def is_available(cls) -> bool:
        """
        Check whether a Redis connection is available.

        Returns:
            True if Redis client is connected, False otherwise
        """
        return cls.get_client() is not None

    @classmethod
    def health_check(cls) -> bool:
        """
        Perform a live health check against Redis.

        Returns:
            True if Redis responds to PING, False otherwise
        """
        client = cls.get_client()
        if client is None:
            return False
        try:
            client.ping()
            return True
        except Exception as e:
            logger.warning(f"RedisManager health check failed: {e}")
            return False

    @classmethod
    def reset(cls) -> None:
        """
        Reset the singleton (useful for testing).

        Closes the existing client if present and clears the instance.
        """
        with cls._lock:
            if cls._instance is not None:
                try:
                    cls._instance.close()
                except Exception as e:
                    logger.debug(f"RedisManager: error closing client during reset: {e}")
            cls._instance = None
            cls._initialized = False
