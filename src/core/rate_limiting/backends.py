"""Rate limiter backend implementations for authentication endpoints."""

import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

# Lua script for atomic rate limiting (check + record in one operation)
# KEYS[1] = rate limit key
# ARGV[1] = max_attempts
# ARGV[2] = window_seconds
# ARGV[3] = current timestamp (now)
# ARGV[4] = unique attempt ID (uuid)
# Returns: 1 if rate limited (attempt NOT recorded), 0 if allowed (attempt recorded)
_RATE_LIMIT_LUA_SCRIPT = """
local key = KEYS[1]
local max_attempts = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local attempt_id = ARGV[4]
local cutoff = now - window

-- Remove expired entries
redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)

-- Check current count
local count = redis.call('ZCARD', key)

-- If already at or above limit, reject (don't record)
if count >= max_attempts then
    return 1
end

-- Under limit: record the attempt and set TTL
redis.call('ZADD', key, now, attempt_id)
redis.call('EXPIRE', key, window)
return 0
"""


class RateLimiterBackend(ABC):
    """Abstract base class for rate limiter backends."""

    @abstractmethod
    def clear_attempts(self, identifier: str) -> None:
        """
        Clear all attempts for an identifier.

        Args:
            identifier: Unique identifier to clear
        """
        pass

    @abstractmethod
    def cleanup_stale_entries(self, window_seconds: int) -> int:
        """
        Remove all stale entries outside the window.

        Args:
            window_seconds: Time window in seconds

        Returns:
            Number of identifiers cleaned up
        """
        pass

    @abstractmethod
    def check_and_record_attempt(
        self, identifier: str, max_attempts: int, window_seconds: int
    ) -> bool:
        """
        Atomically check rate limit and record attempt if not limited.

        This eliminates the TOCTOU race condition between is_rate_limited()
        and record_attempt() by performing both operations atomically.

        Args:
            identifier: Unique identifier (e.g., username, IP)
            max_attempts: Maximum attempts allowed in window
            window_seconds: Time window in seconds

        Returns:
            True if rate limited (attempt was NOT recorded),
            False if allowed (attempt WAS recorded)
        """
        pass

    @property
    @abstractmethod
    def is_distributed(self) -> bool:
        """Check if backend uses distributed storage."""
        pass


class InMemoryBackend(RateLimiterBackend):
    """In-memory rate limiter backend (single-worker only)."""

    MAX_IDENTIFIERS_BEFORE_CLEANUP = 10000

    def __init__(self):
        """Initialize in-memory backend."""
        self._attempts: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()

    def clear_attempts(self, identifier: str) -> None:
        """Clear all attempts for an identifier."""
        with self._lock:
            if identifier in self._attempts:
                del self._attempts[identifier]

    def cleanup_stale_entries(self, window_seconds: int) -> int:
        """Remove all stale entries outside the window."""
        with self._lock:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=window_seconds)

            stale_keys = []
            for identifier, attempts in self._attempts.items():
                # Filter to only recent attempts
                recent = [t for t in attempts if t > cutoff]
                if not recent:
                    stale_keys.append(identifier)
                else:
                    self._attempts[identifier] = recent

            for key in stale_keys:
                del self._attempts[key]

            return len(stale_keys)

    def check_and_record_attempt(
        self, identifier: str, max_attempts: int, window_seconds: int
    ) -> bool:
        """Atomically check rate limit and record attempt if not limited."""
        with self._lock:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=window_seconds)

            # Clean old attempts
            self._attempts[identifier] = [t for t in self._attempts[identifier] if t > cutoff]

            # Check if rate limited
            if len(self._attempts[identifier]) >= max_attempts:
                return True

            # Not limited - record the attempt
            self._attempts[identifier].append(now)
            return False

    @property
    def is_distributed(self) -> bool:
        """Check if backend uses distributed storage."""
        return False


class RedisBackend(RateLimiterBackend):
    """Redis-based distributed rate limiter backend."""

    def __init__(self, redis_client: Any):
        """
        Initialize Redis backend.

        Args:
            redis_client: Redis client instance
        """
        self._redis = redis_client
        # Register Lua script for atomic rate limiting
        self._rate_limit_script = self._redis.register_script(_RATE_LIMIT_LUA_SCRIPT)

    def clear_attempts(self, identifier: str) -> None:
        """Clear all attempts for an identifier."""
        key = f"auth_rl:{identifier}"
        self._redis.delete(key)

    def cleanup_stale_entries(self, window_seconds: int) -> int:
        """
        Remove stale entries from Redis.

        Note: Redis auto-expires keys with TTL, so this is mostly a no-op.
        Returns 0 as cleanup is handled by Redis TTL.
        """
        # Redis handles cleanup via EXPIRE, so no manual cleanup needed
        return 0

    def check_and_record_attempt(
        self, identifier: str, max_attempts: int, window_seconds: int
    ) -> bool:
        """Atomically check rate limit and record attempt if not limited."""
        key = f"auth_rl:{identifier}"
        # Use Unix timestamp (time.time()) for Redis operations for compatibility
        # with Redis ZADD score field which expects numeric values
        now = time.time()
        attempt_id = str(uuid.uuid4())

        result = self._rate_limit_script(
            keys=[key], args=[max_attempts, window_seconds, now, attempt_id]
        )
        return bool(result)

    @property
    def is_distributed(self) -> bool:
        """Check if backend uses distributed storage."""
        return True
