"""Rate limiter for authentication endpoints to prevent brute-force attacks."""

import asyncio
import os
import threading
from typing import Optional

from loguru import logger

from src.constants import RateLimits
from src.utils.masking import mask_database_url

from .backends import RateLimiterBackend, InMemoryBackend, RedisBackend


class AuthRateLimiter:
    """
    Rate limiter for authentication endpoints to prevent brute-force attacks.

    Supports both in-memory (single worker) and Redis (multi-worker) backends.
    """

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 60,
        backend: Optional[RateLimiterBackend] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            max_attempts: Maximum authentication attempts allowed in window
            window_seconds: Time window in seconds
            backend: Optional backend instance (auto-detects if None)
        """
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

        if backend is not None:
            self._backend = backend
        else:
            # Auto-detect backend
            self._backend = self._auto_detect_backend()

    def _auto_detect_backend(self) -> RateLimiterBackend:
        """
        Auto-detect and initialize appropriate backend.

        Tries to connect to Redis if REDIS_URL is set, falls back to in-memory.

        Returns:
            RateLimiterBackend instance
        """
        redis_url = os.getenv("REDIS_URL")

        if redis_url:
            try:
                import redis

                client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5)
                # Test connection
                client.ping()
                logger.info(f"AuthRateLimiter using Redis backend: {mask_database_url(redis_url)}")
                return RedisBackend(client)
            except Exception as e:
                logger.critical(
                    f"🚨 REDIS FALLBACK: Failed to connect to Redis ({mask_database_url(redis_url)}), "
                    f"falling back to in-memory backend. Rate limiting will NOT be shared across workers! Error: {e}"
                )
                # Attempt to send notification alert
                self._notify_redis_fallback(redis_url, str(e))

        # Fallback to in-memory
        logger.info("AuthRateLimiter using in-memory backend")
        return InMemoryBackend()

    def _notify_redis_fallback(self, redis_url: str, error: str) -> None:
        """
        Send notification alert when Redis fallback occurs.

        Args:
            redis_url: The Redis URL that failed
            error: Error message
        """
        try:
            from src.services.notification.notification import NotificationService

            # Create notification message
            message = (
                f"⚠️ Redis Connection Failed - Fallback to In-Memory\n\n"
                f"Redis URL: {mask_database_url(redis_url)}\n"
                f"Error: {error}\n\n"
                f"⚠️ WARNING: Rate limiting is NOT shared across workers in fallback mode!"
            )

            # Try to send notification using helper method
            self._schedule_notification(message)
        except Exception as e:
            logger.error(f"Failed to initialize notification for Redis fallback: {e}")

    def _schedule_notification(self, message: str) -> None:
        """
        Helper to schedule notification in event loop if available.

        Args:
            message: Notification message to send
        """
        try:
            # Try to get a running event loop
            loop = asyncio.get_running_loop()
            # If we're in a running loop, create a task
            loop.create_task(self._send_fallback_notification(message))
        except RuntimeError:
            # No running loop, try to run the coroutine synchronously
            try:
                asyncio.run(self._send_fallback_notification(message))
            except Exception as run_err:
                logger.error(f"Failed to send Redis fallback notification: {run_err}")
        except Exception as notify_err:
            logger.error(f"Failed to schedule Redis fallback notification: {notify_err}")

    async def _send_fallback_notification(self, message: str) -> None:
        """
        Async helper to send Redis fallback notification.

        Args:
            message: Notification message
        """
        try:
            from src.services.notification.notification import NotificationService

            # Build notification config from environment
            config = {
                "telegram": {
                    "enabled": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
                    "bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
                    "chat_id": os.getenv("TELEGRAM_ADMIN_CHAT_ID"),
                },
                "email": {
                    "enabled": bool(os.getenv("SMTP_SERVER")),
                },
            }

            notifier = NotificationService(config)
            await notifier.send_notification(
                title="🚨 Redis Connection Failed - Rate Limiter Fallback",
                message=message,
                priority="high",
            )
        except Exception as e:
            logger.error(f"Failed to send Redis fallback notification: {e}")

    @property
    def is_distributed(self) -> bool:
        """
        Check if rate limiter is using distributed storage.

        Returns:
            True if using distributed backend (e.g., Redis)
        """
        return self._backend.is_distributed

    def check_and_record_attempt(self, identifier: str) -> bool:
        """
        Atomically check if rate limited and record attempt if not.

        This is the preferred method over separate is_rate_limited() + record_attempt()
        calls, as it eliminates the TOCTOU race condition in distributed environments.

        Args:
            identifier: Unique identifier (e.g., username, IP address)

        Returns:
            True if rate limited (attempt NOT recorded),
            False if allowed (attempt WAS recorded)
        """
        return self._backend.check_and_record_attempt(
            identifier, self.max_attempts, self.window_seconds
        )

    def clear_attempts(self, identifier: str) -> None:
        """
        Clear all attempts for an identifier.

        Args:
            identifier: Unique identifier to clear
        """
        self._backend.clear_attempts(identifier)

    def cleanup_stale_entries(self) -> int:
        """
        Remove all stale entries that have no attempts within the current window.

        Returns:
            Number of identifiers cleaned up
        """
        return self._backend.cleanup_stale_entries(self.window_seconds)


# Global rate limiter instance
_auth_rate_limiter: Optional[AuthRateLimiter] = None
_rate_limiter_lock = threading.Lock()


def get_auth_rate_limiter() -> AuthRateLimiter:
    """
    Get or create auth rate limiter singleton.

    Returns:
        AuthRateLimiter instance
    """
    global _auth_rate_limiter
    if _auth_rate_limiter is not None:
        return _auth_rate_limiter
    with _rate_limiter_lock:
        if _auth_rate_limiter is None:
            # Get rate limit config from environment or use defaults
            max_attempts = RateLimits.AUTH_RATE_LIMIT_ATTEMPTS
            window_seconds = RateLimits.AUTH_RATE_LIMIT_WINDOW
            _auth_rate_limiter = AuthRateLimiter(
                max_attempts=max_attempts, window_seconds=window_seconds
            )

            # Check for multi-worker environment and log error if not using distributed backend
            workers = os.getenv("WEB_CONCURRENCY") or os.getenv("UVICORN_WORKERS")
            if workers:
                try:
                    worker_count = int(workers)
                    if worker_count > 1 and not _auth_rate_limiter.is_distributed:
                        logger.critical(
                            f"🚨 SECURITY RISK: Auth rate limiter running with {worker_count} workers "
                            "but using in-memory backend. Rate limiting is NOT shared across workers. "
                            "Set REDIS_URL environment variable to enable distributed rate limiting."
                        )
                except (ValueError, TypeError):
                    # Invalid worker count - log debug message but don't fail
                    logger.debug(f"Invalid worker count in environment: {workers}")
        return _auth_rate_limiter
