"""Database connection pool management."""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

import asyncpg
from loguru import logger

from src.core.exceptions import (
    DatabaseNotConnectedError,
    DatabasePoolTimeoutError,
)
from src.utils.masking import _mask_database_url


class DatabaseConnectionManager:
    """Manages PostgreSQL connection pool lifecycle and health."""

    def __init__(self, database_url: Optional[str] = None, pool_size: Optional[int] = None):
        """
        Initialize database connection manager.

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
                try:
                    pool_size = int(env_pool_size)
                    if pool_size < 1:
                        raise ValueError(f"DB_POOL_SIZE must be >= 1, got: {pool_size}")
                except ValueError as e:
                    logger.warning(f"Invalid DB_POOL_SIZE: {e}. Using calculated optimal size")
                    pool_size = self._calculate_optimal_pool_size()
            else:
                pool_size = self._calculate_optimal_pool_size()
        self.pool_size = pool_size
        self._pool_lock = asyncio.Lock()

        # Migration requirement flag (default: True for safety)
        require_migrations_env = os.getenv("REQUIRE_MIGRATIONS", "true").lower()
        self.require_migrations = require_migrations_env not in ("false", "0", "no")

        # Track if migration check has been performed to avoid redundant checks
        self._migration_verified: bool = False

    def _get_container_cpu_count(self) -> Optional[int]:
        """
        Read CPU count from cgroups for container-aware resource detection.

        Attempts to detect CPU quota limits in the following order:
        1. cgroups v2: Reads /sys/fs/cgroup/cpu.max
        2. cgroups v1: Reads /sys/fs/cgroup/cpu/cpu.cfs_quota_us and cpu.cfs_period_us

        Returns:
            int: Number of CPUs available to the container (minimum 1)
            None: If running outside a container or cgroups files not found

        Examples:
            - Container with 2 CPU limit: returns 2
            - Container with 0.5 CPU limit: returns 1 (minimum enforced)
            - No container/quota: returns None (falls back to os.cpu_count())
        """
        # cgroups v2
        try:
            quota_path = Path("/sys/fs/cgroup/cpu.max")
            if quota_path.exists():
                content = quota_path.read_text().strip()
                parts = content.split()
                if parts[0] != "max":
                    quota = int(parts[0])
                    period = int(parts[1])
                    return max(1, quota // period)
        except (ValueError, IndexError, OSError):
            pass

        # cgroups v1
        try:
            quota_path = Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
            period_path = Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
            if quota_path.exists() and period_path.exists():
                quota = int(quota_path.read_text().strip())
                period = int(period_path.read_text().strip())
                if quota > 0:
                    return max(1, quota // period)
        except (ValueError, OSError):
            pass

        return None

    def _calculate_optimal_pool_size(self) -> int:
        """
        Calculate optimal pool size based on system resources.

        When running multiple workers/instances, set ``DB_MAX_CONNECTIONS``
        and ``DB_WORKER_COUNT`` environment variables to avoid exceeding
        PostgreSQL's ``max_connections`` limit.

        Formula when both are set::

            pool_size = min(int(DB_MAX_CONNECTIONS * 0.8) // DB_WORKER_COUNT, 20)

        Returns:
            Optimal pool size (min: 5, max: 20)
        """
        # Check for explicit max connections / worker count configuration
        max_conn_env = os.getenv("DB_MAX_CONNECTIONS")
        worker_count_env = os.getenv("DB_WORKER_COUNT")

        if max_conn_env and worker_count_env:
            try:
                max_connections = int(max_conn_env)
                worker_count = max(1, int(worker_count_env))
                # Reserve ~20% for admin/superuser connections
                available = int(max_connections * 0.8)
                per_worker = available // worker_count
                return min(max(per_worker, 2), 20)
            except (ValueError, ZeroDivisionError):
                logger.warning(
                    "Invalid DB_MAX_CONNECTIONS or DB_WORKER_COUNT, "
                    "falling back to CPU-based calculation"
                )

        cpu_count = self._get_container_cpu_count() or os.cpu_count() or 4
        # Use 2x CPU count as a reasonable default
        optimal_size = cpu_count * 2
        # Clamp between 5 and 20
        return min(max(optimal_size, 5), 20)

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

                logger.info(
                    f"Database connected with pool size {min_pool}-{self.pool_size}: "
                    f"{_mask_database_url(self.database_url)}"
                )

                # Record pool size metric
                from src.utils.prometheus_metrics import MetricsHelper
                MetricsHelper.set_db_pool_size(self.pool_size)

                # Verify Alembic migration status (only on first connect)
                if not self._migration_verified:
                    try:
                        async with self.pool.acquire() as conn:
                            has_alembic = await conn.fetchval(
                                "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                                "WHERE table_name = 'alembic_version')"
                            )
                            if not has_alembic:
                                error_msg = (
                                    "Alembic version table not found. "
                                    "Run 'alembic upgrade head' to initialize the database schema."
                                )
                                if self.require_migrations:
                                    raise RuntimeError(error_msg)
                                else:
                                    logger.warning(error_msg)
                            else:
                                current_rev = await conn.fetchval(
                                    "SELECT version_num FROM alembic_version LIMIT 1"
                                )
                                logger.info(f"Database schema at Alembic revision: {current_rev}")
                        
                        # Mark migration as verified after successful check
                        self._migration_verified = True
                    except RuntimeError:
                        # Don't catch RuntimeError - let it propagate for required migrations
                        raise
                    except Exception as e:
                        error_msg = f"Could not verify Alembic migration status: {e}"
                        if self.require_migrations:
                            raise RuntimeError(error_msg) from e
                        else:
                            logger.warning(error_msg)
                            # Mark as verified even on warning (non-critical failure)
                            self._migration_verified = True
                else:
                    logger.debug("Skipping migration check (already verified)")
            except Exception:
                # Clean up on error
                if self.pool:
                    await self.pool.close()
                    self.pool = None
                raise

    async def close(self) -> None:
        """Close database connection pool."""
        async with self._pool_lock:
            if self.pool:
                await self.pool.close()
                self.pool = None
            logger.info("Database connection pool closed")

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

            logger.info("Database reconnection successful")
            return True
        except Exception as e:
            logger.error(f"Database reconnection failed: {e}")
            return False

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
        
        import time
        from src.utils.prometheus_metrics import MetricsHelper
        
        start_time = time.time()
        try:
            async with self.pool.acquire() as conn:
                # Record successful acquisition time
                acquire_duration = time.time() - start_time
                MetricsHelper.record_db_pool_acquire(acquire_duration)
                yield conn
        except asyncio.TimeoutError:
            # Record timeout
            MetricsHelper.record_db_pool_timeout()
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
        if self.pool is None:
            raise DatabaseNotConnectedError()

        last_error = None
        conn = None

        for attempt in range(max_retries):
            try:
                conn = await asyncio.wait_for(self.pool.acquire(), timeout=timeout)
                break  # Connection acquired, exit loop
            except (asyncio.TimeoutError, DatabasePoolTimeoutError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = (2**attempt) * 0.5  # Exponential backoff
                    logger.warning(
                        f"Connection pool exhausted, retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)

        if conn is None:
            raise last_error or DatabasePoolTimeoutError(timeout=timeout, pool_size=self.pool_size)

        try:
            yield conn
        finally:
            await self.pool.release(conn)

    async def __aenter__(self) -> "DatabaseConnectionManager":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

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

    def get_pool_stats(self) -> Dict[str, Any]:
        """
        Get current database connection pool statistics.

        Returns:
            Dictionary containing pool statistics:
            - pool_size: Maximum pool size
            - pool_free: Number of idle connections
            - pool_used: Number of active connections
            - utilization: Pool utilization ratio (0.0 to 1.0)
        """
        if self.pool is None:
            return {
                "pool_size": self.pool_size,
                "pool_free": 0,
                "pool_used": 0,
                "utilization": 0.0,
            }
        
        pool_total = self.pool.get_size()
        pool_idle = self.pool.get_idle_size()
        pool_used = pool_total - pool_idle
        # Use pool_total (current pool size) as denominator for accurate utilization
        utilization = pool_used / pool_total if pool_total > 0 else 0.0
        
        # Update metrics
        from src.utils.prometheus_metrics import MetricsHelper
        MetricsHelper.set_db_pool_idle(pool_idle)
        MetricsHelper.set_db_pool_utilization(utilization)
        
        return {
            "pool_size": self.pool_size,
            "pool_free": pool_idle,
            "pool_used": pool_used,
            "utilization": round(utilization, 2),
        }
