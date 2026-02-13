"""Database operations for VFS-Bot using PostgreSQL."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

import asyncpg
from loguru import logger

from src.core.exceptions import (
    DatabaseNotConnectedError,
)
from src.models.db_connection import DatabaseConnectionManager
from src.models.db_state import DatabaseState

# Re-export DatabaseState for backward compatibility
__all__ = ["Database", "DatabaseState"]


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
        # Initialize connection manager
        self._connection_manager = DatabaseConnectionManager(database_url, pool_size)

        # State tracking for graceful degradation
        # Note: _state is not stored; it's computed by the state property
        self._last_successful_query: Optional[datetime] = None
        self._consecutive_failures: int = 0
        self._max_failures_before_degraded: int = 3

    @property
    def pool(self) -> Optional[asyncpg.Pool]:
        """Get the connection pool from the connection manager."""
        return self._connection_manager.pool

    @property
    def pool_size(self) -> int:
        """Get the pool size from the connection manager."""
        return self._connection_manager.pool_size

    @property
    def database_url(self) -> str:
        """Get the database URL from the connection manager."""
        return self._connection_manager.database_url

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
        except Exception as e:
            # Increment failure counter
            self._consecutive_failures += 1

            # Determine error type for logging
            error_type = (
                "database"
                if isinstance(e, (DatabaseNotConnectedError, asyncpg.exceptions.PostgresError))
                else "unexpected"
            )

            # Log warning if entering DEGRADED state
            if self._consecutive_failures == self._max_failures_before_degraded:
                logger.warning(
                    f"Database entering DEGRADED state after {self._consecutive_failures} "
                    f"consecutive failures ({error_type} error): {e}"
                )

            # If critical, re-raise the exception
            if critical:
                raise

            # Otherwise, log and return fallback value
            logger.error(f"Database query failed ({error_type} error, non-critical): {e}")
            return fallback_value

    async def reconnect(self) -> bool:
        """
        Attempt to reconnect to the database.

        Returns:
            True if reconnection successful, False otherwise
        """
        result = await self._connection_manager.reconnect()
        # Reset failure counter on successful reconnection
        if result:
            self._consecutive_failures = 0
        return result

    async def connect(self) -> None:
        """Establish database connection pool."""
        await self._connection_manager.connect()
        # Reset failure counter on successful connection
        self._consecutive_failures = 0

    async def close(self) -> None:
        """Close database connection pool."""
        await self._connection_manager.close()

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
        async with self._connection_manager.get_connection(timeout=timeout) as conn:
            yield conn

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
        async with self._connection_manager.get_connection_with_retry(
            timeout=timeout, max_retries=max_retries
        ) as conn:
            yield conn

    async def health_check(self) -> bool:
        """
        Perform a health check on the database connection.

        Returns:
            True if database is healthy
        """
        result = await self._connection_manager.health_check()
        if result:
            # Reset failure counter — connection is proven healthy
            self._consecutive_failures = 0
            self._last_successful_query = datetime.now(timezone.utc)
        return result
