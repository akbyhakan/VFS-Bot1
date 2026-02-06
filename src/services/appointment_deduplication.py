"""Appointment deduplication service to prevent duplicate bookings.

This module provides a mechanism to prevent duplicate appointment bookings
for the same user, centre, category, and date combination within a configurable
time window.
"""

import asyncio
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class AppointmentDeduplication:
    """
    Prevents duplicate appointment bookings using in-memory TTL cache.

    This service tracks recent booking attempts and prevents duplicate bookings
    for the same user/centre/category/date combination within a configurable
    time window.
    """

    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize deduplication service.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds (default: 1 hour)
        """
        self._cache: Dict[str, float] = {}  # key -> timestamp
        self._lock = asyncio.Lock()
        self._ttl_seconds = ttl_seconds
        logger.info(f"Appointment deduplication initialized (TTL: {ttl_seconds}s)")

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

    async def is_duplicate(
        self, user_id: int, centre: str, category: str, date: str
    ) -> bool:
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
        current_time = time.time()

        async with self._lock:
            # Clean up expired entries first
            await self._cleanup_expired_unsafe(current_time)

            # Check if key exists and is still valid
            if key in self._cache:
                cached_time = self._cache[key]
                if current_time - cached_time < self._ttl_seconds:
                    logger.warning(
                        f"Duplicate booking attempt detected for user {user_id}: "
                        f"{centre}/{category}/{date}"
                    )
                    return True
                else:
                    # Entry expired, remove it
                    del self._cache[key]

        return False

    async def mark_booked(
        self, user_id: int, centre: str, category: str, date: str
    ) -> None:
        """
        Mark a booking as completed to prevent duplicates.

        Args:
            user_id: User ID
            centre: VFS centre name
            category: Visa category
            date: Appointment date (YYYY-MM-DD format)
        """
        key = self._make_key(user_id, centre, category, date)
        current_time = time.time()

        async with self._lock:
            self._cache[key] = current_time
            logger.info(
                f"Booking marked for user {user_id}: {centre}/{category}/{date} "
                f"(expires in {self._ttl_seconds}s)"
            )

    async def _cleanup_expired_unsafe(self, current_time: Optional[float] = None) -> int:
        """
        Clean up expired entries (internal, assumes lock is held).

        Args:
            current_time: Current timestamp (or use time.time())

        Returns:
            Number of entries removed
        """
        if current_time is None:
            current_time = time.time()

        expired_keys = [
            key
            for key, timestamp in self._cache.items()
            if current_time - timestamp >= self._ttl_seconds
        ]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired deduplication entries")

        return len(expired_keys)

    async def cleanup_expired(self) -> int:
        """
        Clean up expired cache entries (public, thread-safe).

        Returns:
            Number of entries removed
        """
        async with self._lock:
            return await self._cleanup_expired_unsafe()

    async def get_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        async with self._lock:
            current_time = time.time()
            active_entries = sum(
                1
                for timestamp in self._cache.values()
                if current_time - timestamp < self._ttl_seconds
            )
            return {
                "total_entries": len(self._cache),
                "active_entries": active_entries,
                "ttl_seconds": self._ttl_seconds,
            }

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {count} deduplication cache entries")


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
