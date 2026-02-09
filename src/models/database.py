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
        """Establish database connection pool and create tables."""
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

                await self._create_tables()

                # Reset failure counter on successful connection
                self._consecutive_failures = 0

                logger.info(
                    f"Database connected with pool size {min_pool}-{self.pool_size}: "
                    f"{self.database_url.split('@')[-1] if '@' in self.database_url else 'localhost'}"
                )
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

    async def _create_tables(self) -> None:
        """
        Create database tables if they don't exist.

        Note: Schema changes should be managed via Alembic migrations.
        Run 'alembic upgrade head' to apply pending migrations.
        This method creates baseline tables for initial setup only.

        For production: Use Alembic CLI commands in Makefile:
        - make db-upgrade: Apply pending migrations
        - make db-migrate msg="description": Create new migration
        - make db-history: View migration history
        """
        if self.pool is None:
            raise RuntimeError("Database connection is not established.")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Users table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id BIGSERIAL PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        centre TEXT NOT NULL,
                        category TEXT NOT NULL,
                        subcategory TEXT NOT NULL,
                        active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)

                # Personal details table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS personal_details (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        first_name TEXT NOT NULL,
                        last_name TEXT NOT NULL,
                        passport_number TEXT NOT NULL,
                        passport_expiry TEXT,
                        gender TEXT,
                        mobile_code TEXT,
                        mobile_number TEXT,
                        email TEXT NOT NULL,
                        nationality TEXT,
                        date_of_birth TEXT,
                        address_line1 TEXT,
                        address_line2 TEXT,
                        state TEXT,
                        city TEXT,
                        postcode TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW(),
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)

                # Appointments table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS appointments (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        centre TEXT NOT NULL,
                        category TEXT NOT NULL,
                        subcategory TEXT NOT NULL,
                        appointment_date TEXT,
                        appointment_time TEXT,
                        status TEXT DEFAULT 'pending',
                        reference_number TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)

                # Logs table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS logs (
                        id BIGSERIAL PRIMARY KEY,
                        level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        user_id BIGINT,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
                    )
                """)

                # Payment card table (single card for all payments)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS payment_card (
                        id BIGSERIAL PRIMARY KEY,
                        card_holder_name TEXT NOT NULL,
                        card_number_encrypted TEXT NOT NULL,
                        expiry_month TEXT NOT NULL,
                        expiry_year TEXT NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)

                # Admin secret usage tracking table (multi-worker safe)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS admin_secret_usage (
                        id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
                        consumed BOOLEAN NOT NULL DEFAULT false,
                        consumed_at TIMESTAMPTZ
                    )
                """)

                # Appointment requests table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS appointment_requests (
                        id BIGSERIAL PRIMARY KEY,
                        country_code TEXT NOT NULL,
                        visa_category TEXT NOT NULL,
                        visa_subcategory TEXT NOT NULL,
                        centres TEXT NOT NULL,
                        preferred_dates TEXT NOT NULL,
                        person_count INTEGER NOT NULL CHECK(person_count >= 1 AND person_count <= 6),
                        status TEXT DEFAULT 'pending',
                        completed_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)

                # Appointment persons table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS appointment_persons (
                        id BIGSERIAL PRIMARY KEY,
                        request_id BIGINT NOT NULL,
                        first_name TEXT NOT NULL,
                        last_name TEXT NOT NULL,
                        gender TEXT NOT NULL,
                        nationality TEXT NOT NULL DEFAULT 'Turkey',
                        birth_date TEXT NOT NULL,
                        passport_number TEXT NOT NULL,
                        passport_issue_date TEXT NOT NULL,
                        passport_expiry_date TEXT NOT NULL,
                        phone_code TEXT NOT NULL DEFAULT '90',
                        phone_number TEXT NOT NULL,
                        email TEXT NOT NULL,
                        is_child_with_parent BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        FOREIGN KEY (request_id) REFERENCES appointment_requests (id) ON DELETE CASCADE
                    )
                """)

                # Audit log table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id BIGSERIAL PRIMARY KEY,
                        action TEXT NOT NULL,
                        user_id BIGINT,
                        username TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        details TEXT,
                        timestamp TEXT NOT NULL,
                        success BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
                    )
                """)

                # Audit log indexes
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id)
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)
                """)

                # Appointment history table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS appointment_history (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        centre TEXT NOT NULL,
                        mission TEXT NOT NULL,
                        category TEXT,
                        slot_date TEXT,
                        slot_time TEXT,
                        status TEXT NOT NULL DEFAULT 'pending',
                        attempt_count INTEGER DEFAULT 1,
                        error_message TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW(),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)

                # Index for faster queries
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_appointment_history_user_status
                    ON appointment_history(user_id, status)
                """)

                # User webhooks table - per-user OTP webhook tokens
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_webhooks (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL UNIQUE,
                        webhook_token VARCHAR(64) UNIQUE NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)

                # Index for faster webhook token lookups
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_webhooks_token
                    ON user_webhooks(webhook_token)
                """)

                # Proxy endpoints table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS proxy_endpoints (
                        id BIGSERIAL PRIMARY KEY,
                        server TEXT NOT NULL,
                        port INTEGER NOT NULL,
                        username TEXT NOT NULL,
                        password_encrypted TEXT NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        last_used TIMESTAMPTZ,
                        failure_count INTEGER DEFAULT 0,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW(),
                        UNIQUE(server, port, username)
                    )
                """)

                # Index for active proxies lookup
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_proxy_endpoints_active
                    ON proxy_endpoints(is_active)
                """)

                # Token blacklist table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS token_blacklist (
                        jti VARCHAR(64) PRIMARY KEY,
                        exp TIMESTAMPTZ NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)

                # Index for cleanup
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_token_blacklist_exp
                    ON token_blacklist(exp)
                """)

                # Schema migrations table for versioned migrations
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        description TEXT NOT NULL,
                        applied_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)

            # Wrap trigger and index creation in transaction for atomicity
            async with conn.transaction():
                # Auto-update updated_at trigger function
                await conn.execute("""
                    CREATE OR REPLACE FUNCTION update_updated_at_column()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        NEW.updated_at = NOW();
                        RETURN NEW;
                    END;
                    $$ language 'plpgsql';
                """)

                # Create triggers for tables with updated_at column
                # Table names are validated against a whitelist for security
                TABLES_WITH_UPDATED_AT = frozenset(
                    [
                        "users",
                        "personal_details",
                        "payment_card",
                        "appointment_requests",
                        "appointment_history",
                        "proxy_endpoints",
                    ]
                )
                for table in TABLES_WITH_UPDATED_AT:
                    # Table names come from a hardcoded frozenset above - safe from SQL injection
                    # We use f-string here because asyncpg doesn't support parameterized identifiers
                    # and the table names are compile-time constants
                    await conn.execute(f"""
                        DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};
                        CREATE TRIGGER update_{table}_updated_at
                            BEFORE UPDATE ON {table}
                            FOR EACH ROW
                            EXECUTE FUNCTION update_updated_at_column();
                    """)

                # Add missing critical indexes
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_active ON users(active)")
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_appointments_user_id ON appointments(user_id)"
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status)"
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_personal_details_user_id ON personal_details(user_id)"
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at)"
                )
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_user_id ON logs(user_id)")

            logger.info("Database tables created/verified")
