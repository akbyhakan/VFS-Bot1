"""Appointment deduplication service to prevent duplicate bookings.

This module provides a mechanism to prevent duplicate appointment bookings
for the same user, centre, category, and date combination within a configurable
time window.
"""

import asyncio
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from loguru import logger


class DeduplicationBackend(ABC):
    """Abstract base class for deduplication backends."""

    @abstractmethod
    async def is_duplicate(self, key: str, ttl_seconds: int) -> bool:
        """
        Check if a key exists and is still valid.

        Args:
            key: Cache key
            ttl_seconds: Time-to-live in seconds

        Returns:
            True if this is a duplicate (key exists and not expired)
        """
        pass

    @abstractmethod
    async def mark_booked(self, key: str, ttl_seconds: int) -> None:
        """
        Mark a booking as completed.

        Args:
            key: Cache key
            ttl_seconds: Time-to-live in seconds
        """
        pass

    @abstractmethod
    async def cleanup_expired(self, ttl_seconds: int) -> int:
        """
        Clean up expired entries.

        Args:
            ttl_seconds: Time-to-live in seconds

        Returns:
            Number of entries removed
        """
        pass

    @abstractmethod
    async def get_stats(self, ttl_seconds: int) -> Dict[str, int]:
        """
        Get cache statistics.

        Args:
            ttl_seconds: Time-to-live in seconds

        Returns:
            Dictionary with cache statistics
        """
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""
        pass

    @property
    @abstractmethod
    def is_distributed(self) -> bool:
        """Check if backend uses distributed storage."""
        pass


class InMemoryDeduplicationBackend(DeduplicationBackend):
    """In-memory deduplication backend (single-worker only)."""

    def __init__(self):
        """Initialize in-memory backend."""
        self._cache: Dict[str, float] = {}  # key -> timestamp
        self._lock = asyncio.Lock()

    async def is_duplicate(self, key: str, ttl_seconds: int) -> bool:
        """Check if a key exists and is still valid."""
        current_time = time.time()

        async with self._lock:
            # Clean up expired entries first
            await self._cleanup_expired_unsafe(current_time, ttl_seconds)

            # Check if key exists and is still valid
            if key in self._cache:
                cached_time = self._cache[key]
                if current_time - cached_time < ttl_seconds:
                    return True
                else:
                    # Entry expired, remove it
                    del self._cache[key]

        return False

    async def mark_booked(self, key: str, ttl_seconds: int) -> None:
        """Mark a booking as completed."""
        current_time = time.time()

        async with self._lock:
            self._cache[key] = current_time

    async def _cleanup_expired_unsafe(self, current_time: float, ttl_seconds: int) -> int:
        """
        Clean up expired entries (internal, assumes lock is held).

        Args:
            current_time: Current timestamp
            ttl_seconds: Time-to-live in seconds

        Returns:
            Number of entries removed
        """
        expired_keys = [
            key for key, timestamp in self._cache.items() if current_time - timestamp >= ttl_seconds
        ]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired deduplication entries")

        return len(expired_keys)

    async def cleanup_expired(self, ttl_seconds: int) -> int:
        """Clean up expired cache entries (public, thread-safe)."""
        async with self._lock:
            current_time = time.time()
            return await self._cleanup_expired_unsafe(current_time, ttl_seconds)

    async def get_stats(self, ttl_seconds: int) -> Dict[str, int]:
        """Get cache statistics."""
        async with self._lock:
            current_time = time.time()
            active_entries = sum(
                1 for timestamp in self._cache.values() if current_time - timestamp < ttl_seconds
            )
            return {
                "total_entries": len(self._cache),
                "active_entries": active_entries,
                "ttl_seconds": ttl_seconds,
            }

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {count} deduplication cache entries")

    @property
    def is_distributed(self) -> bool:
        """Check if backend uses distributed storage."""
        return False


class RedisDeduplicationBackend(DeduplicationBackend):
    """Redis-based distributed deduplication backend."""

    def __init__(self, redis_client: Any):
        """
        Initialize Redis backend.

        Args:
            redis_client: Redis client instance
        """
        self._redis = redis_client

    async def is_duplicate(self, key: str, ttl_seconds: int) -> bool:
        """Check if a key exists and is still valid."""
        redis_key = f"dedup:{key}"
        # Redis GET returns None if key doesn't exist or is expired
        exists = await asyncio.to_thread(self._redis.exists, redis_key)
        return bool(exists)

    async def mark_booked(self, key: str, ttl_seconds: int) -> None:
        """Mark a booking as completed."""
        redis_key = f"dedup:{key}"
        # Use SETEX for atomic set with expiration
        await asyncio.to_thread(self._redis.setex, redis_key, ttl_seconds, "1")

    async def cleanup_expired(self, ttl_seconds: int) -> int:
        """
        Clean up expired entries.

        Note: Redis auto-expires keys with TTL, so this is mostly a no-op.
        Returns 0 as cleanup is handled by Redis TTL.
        """
        return 0

    async def get_stats(self, ttl_seconds: int) -> Dict[str, int]:
        """Get cache statistics."""
        # Count all dedup keys
        keys = await asyncio.to_thread(self._redis.keys, "dedup:*")
        return {
            "total_entries": len(keys),
            "active_entries": len(keys),  # All keys in Redis are active (TTL handles expiry)
            "ttl_seconds": ttl_seconds,
        }

    async def clear(self) -> None:
        """Clear all cache entries."""
        keys = await asyncio.to_thread(self._redis.keys, "dedup:*")
        if keys:
            await asyncio.to_thread(self._redis.delete, *keys)
            logger.info(f"Cleared {len(keys)} deduplication cache entries")

    @property
    def is_distributed(self) -> bool:
        """Check if backend uses distributed storage."""
        return True


class AppointmentDeduplication:
    """
    Prevents duplicate appointment bookings using configurable backend.

    This service tracks recent booking attempts and prevents duplicate bookings
    for the same user/centre/category/date combination within a configurable
    time window.

    Supports both in-memory (single-worker) and Redis (multi-worker) backends.
    """

    def __init__(self, ttl_seconds: int = 3600, backend: Optional[DeduplicationBackend] = None):
        """
        Initialize deduplication service.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds (default: 1 hour)
            backend: Optional backend instance (auto-detects if None)
        """
        self._ttl_seconds = ttl_seconds

        if backend is not None:
            self._backend = backend
        else:
            # Auto-detect backend
            self._backend = self._auto_detect_backend()

        logger.info(
            f"Appointment deduplication initialized (TTL: {ttl_seconds}s, "
            f"backend: {'Redis' if self._backend.is_distributed else 'in-memory'})"
        )

    def _auto_detect_backend(self) -> DeduplicationBackend:
        """
        Auto-detect and initialize appropriate backend.

        Tries to connect to Redis if REDIS_URL is set, falls back to in-memory.

        Returns:
            DeduplicationBackend instance
        """
        redis_url = os.getenv("REDIS_URL")

        if redis_url:
            try:
                import redis

                client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5)
                # Test connection
                client.ping()
                logger.info(f"AppointmentDeduplication using Redis backend")
                return RedisDeduplicationBackend(client)
            except Exception as e:
                logger.warning(
                    f"Failed to connect to Redis, falling back to in-memory backend. "
                    f"Deduplication will NOT be shared across workers! Error: {e}"
                )

        # Fallback to in-memory
        logger.info("AppointmentDeduplication using in-memory backend")
        return InMemoryDeduplicationBackend()

    def _make_key(self, user_id: int, centre: str, category: str, date: str) -> str:
        """
        Create cache key from booking parameters.

        Args:
            user_id: User ID
            centre: VFS centre name
            category: Visa category
            date: Appointment date (YYYY-MM-DD format)

        Returns:
            Cache key string
        """
        return f"{user_id}:{centre}:{category}:{date}"

    async def is_duplicate(self, user_id: int, centre: str, category: str, date: str) -> bool:
        """
        Check if booking attempt is a duplicate.

        Args:
            user_id: User ID
            centre: VFS centre name
            category: Visa category
            date: Appointment date (YYYY-MM-DD format)

        Returns:
            True if this is a duplicate booking attempt
        """
        key = self._make_key(user_id, centre, category, date)

        is_dup = await self._backend.is_duplicate(key, self._ttl_seconds)

        if is_dup:
            logger.warning(
                f"Duplicate booking attempt detected for user {user_id}: "
                f"{centre}/{category}/{date}"
            )

        return is_dup

    async def mark_booked(self, user_id: int, centre: str, category: str, date: str) -> None:
        """
        Mark a booking as completed to prevent duplicates.

        Args:
            user_id: User ID
            centre: VFS centre name
            category: Visa category
            date: Appointment date (YYYY-MM-DD format)
        """
        key = self._make_key(user_id, centre, category, date)
        await self._backend.mark_booked(key, self._ttl_seconds)

        logger.info(
            f"Booking marked for user {user_id}: {centre}/{category}/{date} "
            f"(expires in {self._ttl_seconds}s)"
        )

    async def cleanup_expired(self) -> int:
        """
        Clean up expired cache entries (public, thread-safe).

        Returns:
            Number of entries removed
        """
        return await self._backend.cleanup_expired(self._ttl_seconds)

    async def get_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return await self._backend.get_stats(self._ttl_seconds)

    async def clear(self) -> None:
        """Clear all cache entries."""
        await self._backend.clear()


# Global singleton instance
_deduplication_service: Optional[AppointmentDeduplication] = None
_deduplication_lock = asyncio.Lock()


async def get_deduplication_service(
    ttl_seconds: int = 3600,
) -> AppointmentDeduplication:
    """
    Get or create the global deduplication service instance.

    Args:
        ttl_seconds: TTL for cache entries (only used when creating new instance)

    Returns:
        AppointmentDeduplication instance
    """
    global _deduplication_service

    async with _deduplication_lock:
        if _deduplication_service is None:
            _deduplication_service = AppointmentDeduplication(ttl_seconds=ttl_seconds)

    return _deduplication_service
