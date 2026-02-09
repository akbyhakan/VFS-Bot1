"""Database operations for VFS-Bot using PostgreSQL."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import wraps
from typing import Any, AsyncIterator, Awaitable, Callable, Optional, TypeVar

import asyncpg

from src.core.exceptions import (
    DatabaseNotConnectedError,
    DatabasePoolTimeoutError,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])

# Allowed fields for personal_details table (SQL injection prevention)
ALLOWED_PERSONAL_DETAILS_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "passport_number",
        "passport_expiry",
        "gender",
        "mobile_code",
        "mobile_number",
        "email",
        "nationality",
        "date_of_birth",
        "address_line1",
        "address_line2",
        "state",
        "city",
        "postcode",
    }
)

# Allowed fields for users table update (SQL injection prevention)
ALLOWED_USER_UPDATE_FIELDS = frozenset(
    {
        "email",
        "password",
        "centre",
        "category",
        "subcategory",
        "active",
    }
)


class DatabaseState:
    """Database connection state constants."""

    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"


def require_connection(func: F) -> F:
    """
    Decorator to ensure database connection exists before method execution.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function that checks for connection

    Raises:
        DatabaseNotConnectedError: If database connection is not established
    """

    @wraps(func)
    async def wrapper(self: "Database", *args: Any, **kwargs: Any) -> Any:
        if self.pool is None:
            raise DatabaseNotConnectedError()
        return await func(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


class Database:
    """PostgreSQL database manager for VFS-Bot with connection pooling."""

    def __init__(self, database_url: Optional[str] = None, pool_size: Optional[int] = None):
        """
        Initialize database connection pool.

        Args:
            database_url: PostgreSQL connection URL (defaults to DATABASE_URL env var)
            pool_size: Maximum number of concurrent connections (defaults to
                DB_POOL_SIZE env var or calculated optimal size)

        Raises:
            RuntimeError: If DATABASE_URL is not set and no database_url is provided
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise RuntimeError(
                "DATABASE_URL environment variable must be set. "
                "Example: postgresql://user:password@localhost:5432/vfs_bot"
            )
        self.pool: Optional[asyncpg.Pool] = None
        # Get pool size from parameter, env var, or calculate optimal size
        if pool_size is None:
            env_pool_size = os.getenv("DB_POOL_SIZE")
            if env_pool_size:
                pool_size = int(env_pool_size)
            else:
                pool_size = self._calculate_optimal_pool_size()
        self.pool_size = pool_size
        self._pool_lock = asyncio.Lock()

        # State tracking for graceful degradation
        # Note: _state is not stored; it's computed by the state property
        self._last_successful_query: Optional[datetime] = None
        self._consecutive_failures: int = 0
        self._max_failures_before_degraded: int = 3

    def _calculate_optimal_pool_size(self) -> int:
        """
        Calculate optimal pool size based on system resources.

        Returns:
            Optimal pool size (min: 5, max: 20)
        """
        cpu_count = os.cpu_count() or 4
        # Use 2x CPU count as a reasonable default
        optimal_size = cpu_count * 2
        # Clamp between 5 and 20
        return min(max(optimal_size, 5), 20)

    @staticmethod
    def _parse_command_tag(command_tag: str) -> int:
        """
        Parse PostgreSQL command tag to extract affected row count.

        PostgreSQL command tags follow the format 'COMMAND N' where N is the count.
        Examples: 'UPDATE 5', 'DELETE 3', 'INSERT 0 1'

        Args:
            command_tag: PostgreSQL command tag string

        Returns:
            Number of affected rows, or 0 if parsing fails
        """
        try:
            # Command tags format: 'COMMAND N' or 'INSERT oid N'
            parts = command_tag.split()
            if len(parts) >= 2:
                # For INSERT: 'INSERT 0 N' - return last part
                # For UPDATE/DELETE: 'UPDATE N' - return last part
                return int(parts[-1])
            return 0
        except (ValueError, IndexError):
            logger.warning(f"Failed to parse command tag: {command_tag}")
            return 0

    @property
    def state(self) -> str:
        """
        Get current database state.

        Returns:
            Current state (CONNECTED, DEGRADED, or DISCONNECTED)
        """
        if self.pool is None:
            return DatabaseState.DISCONNECTED

        if self._consecutive_failures >= self._max_failures_before_degraded:
            return DatabaseState.DEGRADED

        return DatabaseState.CONNECTED

    async def execute_with_fallback(
        self,
        query_func: Callable[[], Awaitable[Any]],
        fallback_value: Any = None,
        critical: bool = False,
    ) -> Any:
        """
        Execute a query with fallback support for graceful degradation.

        Args:
            query_func: Async function that executes the query
            fallback_value: Value to return on failure (default: None)
            critical: If True, re-raise exceptions; if False, return fallback_value

        Returns:
            Query result on success, fallback_value on non-critical failure

        Raises:
            Exception: If critical=True and query fails
        """
        try:
            result = await query_func()
            # Success - reset failure counter and update last successful query time
            self._consecutive_failures = 0
            self._last_successful_query = datetime.now(timezone.utc)
            return result
        except (DatabaseNotConnectedError, asyncpg.exceptions.PostgresError, Exception) as e:
            # Increment failure counter
            self._consecutive_failures += 1

            # Log warning if entering DEGRADED state
            if self._consecutive_failures == self._max_failures_before_degraded:
                logger.warning(
                    f"Database entering DEGRADED state after {self._consecutive_failures} "
                    f"consecutive failures: {e}"
                )

            # If critical, re-raise the exception
            if critical:
                raise

            # Otherwise, log and return fallback value
            logger.error(f"Database query failed (non-critical), returning fallback value: {e}")
            return fallback_value

    async def reconnect(self) -> bool:
        """
        Attempt to reconnect to the database.

        Returns:
            True if reconnection successful, False otherwise
        """
        try:
            # Close existing pool if it exists
            if self.pool is not None:
                await self.pool.close()
                self.pool = None

            # Attempt to reconnect
            await self.connect()

            # Reset failure counter on successful reconnection
            self._consecutive_failures = 0
            logger.info("Database reconnection successful")
            return True
        except Exception as e:
            logger.error(f"Database reconnection failed: {e}")
            return False

    async def connect(self) -> None:
        """Establish database connection pool."""
        async with self._pool_lock:
            try:
                # Calculate minimum pool size (at least 2, at most ceiling of half max)
                # Examples: pool=5 → min=3, pool=4 → min=2, pool=10 → min=5
                min_pool = max(2, (self.pool_size + 1) // 2)

                # Create connection pool
                self.pool = await asyncpg.create_pool(
                    self.database_url,
                    min_size=min_pool,
                    max_size=self.pool_size,
                    timeout=30.0,
                    command_timeout=60.0,
                    statement_cache_size=100,
                    max_inactive_connection_lifetime=300.0,
                )

                # Reset failure counter on successful connection
                self._consecutive_failures = 0

                logger.info(
                    f"Database connected with pool size {min_pool}-{self.pool_size}: "
                    f"{self.database_url.split('@')[-1] if '@' in self.database_url else 'localhost'}"
                )

                # Verify Alembic migration status (advisory only)
                try:
                    async with self.pool.acquire() as conn:
                        has_alembic = await conn.fetchval(
                            "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                            "WHERE table_name = 'alembic_version')"
                        )
                        if not has_alembic:
                            logger.warning(
                                "Alembic version table not found. "
                                "Run 'alembic upgrade head' to initialize the database schema."
                            )
                        else:
                            current_rev = await conn.fetchval(
                                "SELECT version_num FROM alembic_version LIMIT 1"
                            )
                            logger.info(f"Database schema at Alembic revision: {current_rev}")
                except Exception as e:
                    logger.warning(f"Could not verify Alembic migration status: {e}")
            except Exception:
                # Clean up on error
                if self.pool:
                    await self.pool.close()
                    self.pool = None
                raise

    async def close(self) -> None:
        """Close database connection pool."""
        async with self._pool_lock:
            # Close connection pool
            if self.pool:
                await self.pool.close()
            # Pool is None, so state property will return DISCONNECTED automatically
            logger.info("Database connection pool closed")

    async def __aenter__(self) -> "Database":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    @asynccontextmanager
    async def get_connection(self, timeout: float = 30.0) -> AsyncIterator[asyncpg.Connection]:
        """
        Get a connection from the pool with timeout.

        Args:
            timeout: Maximum time to wait for a connection

        Yields:
            Database connection from pool

        Raises:
            DatabasePoolTimeoutError: If connection cannot be acquired within timeout
        """
        if self.pool is None:
            raise DatabaseNotConnectedError()
        try:
            async with self.pool.acquire() as conn:
                yield conn
        except asyncio.TimeoutError:
            logger.error(
                f"Database connection pool exhausted "
                f"(timeout: {timeout}s, pool_size: {self.pool_size})"
            )
            raise DatabasePoolTimeoutError(timeout=timeout, pool_size=self.pool_size)

    @asynccontextmanager
    async def get_connection_with_retry(
        self, timeout: float = 30.0, max_retries: int = 3
    ) -> AsyncIterator[asyncpg.Connection]:
        """
        Get a connection from the pool with retry logic.

        Args:
            timeout: Maximum time to wait for a connection
            max_retries: Maximum retry attempts

        Yields:
            Database connection from pool

        Raises:
            DatabasePoolTimeoutError: If connection cannot be acquired after all retries
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                async with self.get_connection(timeout=timeout) as conn:
                    yield conn
                    return
            except DatabasePoolTimeoutError as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = (2**attempt) * 0.5  # Exponential backoff
                    logger.warning(
                        f"Connection pool exhausted, retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)

        raise last_error or DatabasePoolTimeoutError(timeout=timeout, pool_size=self.pool_size)

    async def health_check(self) -> bool:
        """
        Perform a health check on the database connection.

        Returns:
            True if database is healthy
        """
        try:
            async with self.get_connection(timeout=5.0) as conn:
                result = await conn.fetchval("SELECT 1")
                return result is not None
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

