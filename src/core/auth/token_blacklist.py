"""Token blacklist for JWT revocation."""

import asyncio
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger


class TokenBlacklist:
    """
    Thread-safe token blacklist for JWT revocation.

    Uses OrderedDict for efficient memory management with automatic cleanup
    of expired tokens.
    """

    def __init__(self, max_size: int = 10000):
        """
        Initialize token blacklist.

        Args:
            max_size: Maximum number of tokens to keep in memory
        """
        self._blacklist: OrderedDict[str, datetime] = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    def add(self, jti: str, exp: datetime) -> None:
        """
        Add a token to the blacklist.

        Args:
            jti: JWT ID (jti claim)
            exp: Token expiration time
        """
        with self._lock:
            # Remove expired tokens first
            self._cleanup_expired()

            # Add new token
            self._blacklist[jti] = exp

            # Enforce max size by removing oldest entries
            while len(self._blacklist) > self._max_size:
                self._blacklist.popitem(last=False)

    def is_blacklisted(self, jti: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            jti: JWT ID to check

        Returns:
            True if token is blacklisted
        """
        with self._lock:
            # Cleanup expired tokens
            self._cleanup_expired()
            return jti in self._blacklist

    def _cleanup_expired(self) -> None:
        """Remove expired tokens from blacklist (must be called with lock held)."""
        now = datetime.now(timezone.utc)
        expired_keys = [jti for jti, exp in self._blacklist.items() if exp < now]
        for jti in expired_keys:
            del self._blacklist[jti]

    def size(self) -> int:
        """Get current blacklist size."""
        with self._lock:
            return len(self._blacklist)

    async def start_cleanup_task(self, interval: int = 300) -> None:
        """
        Start background cleanup task.

        Args:
            interval: Cleanup interval in seconds (default: 5 minutes)
        """
        self._running = True
        while self._running:
            await asyncio.sleep(interval)
            with self._lock:
                self._cleanup_expired()
                logger.debug(f"Token blacklist cleanup: {len(self._blacklist)} tokens remaining")

    def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        self._running = False


class PersistentTokenBlacklist(TokenBlacklist):
    """
    Database-backed token blacklist for production environments.
    Falls back to memory if database unavailable.
    """

    def __init__(self, db: Optional[Any] = None, max_size: int = 10000):
        """
        Initialize persistent blacklist.

        Args:
            db: Database instance (optional)
            max_size: Maximum size of in-memory cache
        """
        super().__init__(max_size)
        self._db = db
        self._use_db = db is not None

    async def add_async(self, jti: str, exp: datetime) -> None:
        """Add token to blacklist with database persistence."""
        # Always add to memory cache
        self.add(jti, exp)

        # Persist to database if available
        if self._use_db and self._db:
            try:
                await self._db.add_blacklisted_token(jti, exp)
            except Exception as e:
                logger.warning(f"Failed to persist blacklisted token: {e}")

    async def is_blacklisted_async(self, jti: str) -> bool:
        """Check if token is blacklisted (checks both memory and database)."""
        # Check memory first (fast path)
        if self.is_blacklisted(jti):
            return True

        # Check database if available
        if self._use_db and self._db:
            try:
                return bool(await self._db.is_token_blacklisted(jti))
            except Exception as e:
                logger.warning(f"Failed to check blacklist in database: {e}")

        return False

    async def load_from_database(self) -> int:
        """Load active blacklisted tokens from database on startup."""
        if not self._use_db or not self._db:
            return 0

        try:
            tokens = await self._db.get_active_blacklisted_tokens()
            for jti, exp in tokens:
                self.add(jti, exp)
            logger.info(f"Loaded {len(tokens)} blacklisted tokens from database")
            return len(tokens)
        except Exception as e:
            logger.error(f"Failed to load blacklist from database: {e}")
            return 0

    async def start_cleanup_task(self, interval: int = 300) -> None:
        """
        Start background cleanup task for both memory and database.

        This method completely overrides the parent's implementation to add
        database cleanup capability while maintaining in-memory cleanup.
        
        The parent's logic is reimplemented here to avoid complexity from
        coordination between parent's task and database cleanup scheduling.

        Args:
            interval: Cleanup interval in seconds (default: 5 minutes)
        """
        self._running = True
        db_cleanup_counter = 0

        while self._running:
            await asyncio.sleep(interval)

            # In-memory cleanup (every interval)
            with self._lock:
                self._cleanup_expired()
                logger.debug(
                    f"Token blacklist cleanup: {len(self._blacklist)} tokens remaining"
                )

            # Database cleanup (every 6th interval ≈ 30 minutes)
            db_cleanup_counter += 1
            if db_cleanup_counter >= 6 and self._use_db and self._db:
                db_cleanup_counter = 0
                try:
                    deleted = await self._db.cleanup_expired_tokens()
                    if deleted > 0:
                        logger.info(
                            f"Database token cleanup: removed {deleted} expired tokens"
                        )
                except Exception as e:
                    logger.warning(f"Database token cleanup failed: {e}")


# Global token blacklist instance
_token_blacklist: Optional[TokenBlacklist] = None
_blacklist_lock = threading.Lock()


def get_token_blacklist() -> TokenBlacklist:
    """
    Get global token blacklist instance (singleton).

    Returns:
        TokenBlacklist instance
    """
    global _token_blacklist
    with _blacklist_lock:
        if _token_blacklist is None:
            _token_blacklist = TokenBlacklist()
        return _token_blacklist
