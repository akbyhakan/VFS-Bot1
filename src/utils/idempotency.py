"""Idempotency key management for preventing duplicate operations."""

import asyncio
import hashlib
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from loguru import logger


class IdempotencyBackend(ABC):
    """Abstract base class for idempotency backends."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Get cached result for idempotency key.

        Args:
            key: Idempotency key

        Returns:
            Cached result if found and not expired, None otherwise
        """
        pass

    @abstractmethod
    async def set(self, key: str, result: Any, ttl_seconds: int) -> None:
        """
        Store result for idempotency key.

        Args:
            key: Idempotency key
            result: Result to store
            ttl_seconds: Time-to-live in seconds
        """
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """
        Remove expired entries.

        Returns:
            Number of entries removed
        """
        pass

    @property
    @abstractmethod
    def is_distributed(self) -> bool:
        """Check if backend uses distributed storage."""
        pass


@dataclass
class IdempotencyRecord:
    """Record of an idempotent operation."""

    key: str
    result: Any
    created_at: datetime
    expires_at: datetime


class InMemoryIdempotencyBackend(IdempotencyBackend):
    """In-memory idempotency backend (single-worker only)."""

    def __init__(self):
        """Initialize in-memory backend."""
        self._store: Dict[str, IdempotencyRecord] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Get cached result for idempotency key."""
        async with self._lock:
            record = self._store.get(key)
            if record:
                if datetime.now(timezone.utc) < record.expires_at:
                    logger.debug(f"Idempotency hit for key: {key[:16]}...")
                    return record.result
                else:
                    # Expired, remove it
                    del self._store[key]
            return None

    async def set(self, key: str, result: Any, ttl_seconds: int) -> None:
        """Store result for idempotency key."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            self._store[key] = IdempotencyRecord(
                key=key,
                result=result,
                created_at=now,
                expires_at=now + timedelta(seconds=ttl_seconds),
            )
            logger.debug(f"Idempotency stored for key: {key[:16]}...")

    async def cleanup_expired(self) -> int:
        """Remove expired entries."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            expired_keys = [k for k, v in self._store.items() if v.expires_at < now]
            for key in expired_keys:
                del self._store[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired idempotency records")

            return len(expired_keys)

    @property
    def is_distributed(self) -> bool:
        """Check if backend uses distributed storage."""
        return False


class RedisIdempotencyBackend(IdempotencyBackend):
    """Redis-based distributed idempotency backend."""

    def __init__(self, redis_client: Any):
        """
        Initialize Redis backend.

        Args:
            redis_client: Redis client instance
        """
        self._redis = redis_client

    async def get(self, key: str) -> Optional[Any]:
        """Get cached result for idempotency key."""
        redis_key = f"idempotency:{key}"
        data = await asyncio.to_thread(self._redis.get, redis_key)
        if data:
            try:
                logger.debug(f"Idempotency hit for key: {key[:16]}...")
                return json.loads(data)
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode idempotency data for key: {key[:16]}...")
                return None
        return None

    async def set(self, key: str, result: Any, ttl_seconds: int) -> None:
        """Store result for idempotency key."""
        redis_key = f"idempotency:{key}"
        # Serialize result to JSON
        data = json.dumps(result, default=str)
        # Use SETEX for atomic set with expiration
        await asyncio.to_thread(self._redis.setex, redis_key, ttl_seconds, data)
        logger.debug(f"Idempotency stored for key: {key[:16]}...")

    async def cleanup_expired(self) -> int:
        """
        Remove expired entries.

        Note: Redis auto-expires keys with TTL, so this is mostly a no-op.
        Returns 0 as cleanup is handled by Redis TTL.
        """
        return 0

    @property
    def is_distributed(self) -> bool:
        """Check if backend uses distributed storage."""
        return True


class IdempotencyStore:
    """
    Idempotency store for preventing duplicate operations.

    Supports both in-memory (single-worker) and Redis (multi-worker) backends.
    """

    def __init__(
        self, ttl_seconds: int = 86400, backend: Optional[IdempotencyBackend] = None
    ):  # 24 hours default
        """
        Initialize idempotency store.

        Args:
            ttl_seconds: Time-to-live for stored records in seconds
            backend: Optional backend instance (auto-detects if None)
        """
        self._ttl = ttl_seconds

        if backend is not None:
            self._backend = backend
        else:
            # Auto-detect backend
            self._backend = self._auto_detect_backend()

        logger.info(
            f"IdempotencyStore initialized (TTL: {ttl_seconds}s, "
            f"backend: {'Redis' if self._backend.is_distributed else 'in-memory'})"
        )

    def _auto_detect_backend(self) -> IdempotencyBackend:
        """
        Auto-detect and initialize appropriate backend.

        Uses RedisManager for a shared connection if available, falls back to in-memory.

        Returns:
            IdempotencyBackend instance
        """
        from src.core.infra.redis_manager import RedisManager

        client = RedisManager.get_client()

        if client is not None:
            logger.info("IdempotencyStore using Redis backend")
            return RedisIdempotencyBackend(client)

        if os.getenv("REDIS_URL"):
            logger.warning(
                "Failed to connect to Redis, falling back to in-memory backend. "
                "Idempotency will NOT be shared across workers!"
            )

        # Fallback to in-memory
        logger.info("IdempotencyStore using in-memory backend")
        return InMemoryIdempotencyBackend()

    def _generate_key(self, operation: str, params: Dict[str, Any]) -> str:
        """Generate idempotency key from operation and parameters."""
        # Sort params for consistent hashing
        param_str = json.dumps(params, sort_keys=True, default=str)
        content = f"{operation}:{param_str}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def get(self, key: str) -> Optional[Any]:
        """Get cached result for idempotency key."""
        return await self._backend.get(key)

    async def set(self, key: str, result: Any) -> None:
        """Store result for idempotency key."""
        await self._backend.set(key, result, self._ttl)

    async def check_and_set(
        self, operation: str, params: Dict[str, Any], execute_fn: Callable[[], Awaitable[Any]]
    ) -> tuple[Any, bool]:
        """
        Check for existing result, or execute and store.

        Args:
            operation: Operation identifier
            params: Operation parameters
            execute_fn: Async function to execute if not cached

        Returns:
            Tuple of (result, was_cached)
        """
        key = self._generate_key(operation, params)

        # Check for existing result
        existing = await self.get(key)
        if existing is not None:
            return existing, True

        # Execute operation
        result = await execute_fn()

        # Store result
        await self.set(key, result)

        return result, False

    async def cleanup_expired(self) -> int:
        """Remove expired entries."""
        return await self._backend.cleanup_expired()


# Global idempotency store
_idempotency_store: Optional[IdempotencyStore] = None


def get_idempotency_store() -> IdempotencyStore:
    """Get global idempotency store instance."""
    global _idempotency_store
    if _idempotency_store is None:
        _idempotency_store = IdempotencyStore()
    return _idempotency_store
