"""Idempotency key management for preventing duplicate operations."""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from loguru import logger


@dataclass
class IdempotencyRecord:
    """Record of an idempotent operation."""

    key: str
    result: Any
    created_at: datetime
    expires_at: datetime


class IdempotencyStore:
    """
    In-memory idempotency store for preventing duplicate operations.

    For production, consider using Redis or database storage.
    """

    def __init__(self, ttl_seconds: int = 86400):  # 24 hours default
        """
        Initialize idempotency store.

        Args:
            ttl_seconds: Time-to-live for stored records in seconds
        """
        self._store: Dict[str, IdempotencyRecord] = {}
        self._lock = asyncio.Lock()
        self._ttl = ttl_seconds

    def _generate_key(self, operation: str, params: Dict[str, Any]) -> str:
        """Generate idempotency key from operation and parameters."""
        # Sort params for consistent hashing
        param_str = json.dumps(params, sort_keys=True, default=str)
        content = f"{operation}:{param_str}"
        return hashlib.sha256(content.encode()).hexdigest()

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

    async def set(self, key: str, result: Any) -> None:
        """Store result for idempotency key."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            self._store[key] = IdempotencyRecord(
                key=key,
                result=result,
                created_at=now,
                expires_at=now + timedelta(seconds=self._ttl),
            )
            logger.debug(f"Idempotency stored for key: {key[:16]}...")

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
        async with self._lock:
            now = datetime.now(timezone.utc)
            expired_keys = [k for k, v in self._store.items() if v.expires_at < now]
            for key in expired_keys:
                del self._store[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired idempotency records")

            return len(expired_keys)


# Global idempotency store
_idempotency_store: Optional[IdempotencyStore] = None


def get_idempotency_store() -> IdempotencyStore:
    """Get global idempotency store instance."""
    global _idempotency_store
    if _idempotency_store is None:
        _idempotency_store = IdempotencyStore()
    return _idempotency_store
