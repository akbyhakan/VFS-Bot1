"""Database operations for VFS-Bot using PostgreSQL."""

import asyncio
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import wraps
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, TypeVar

import asyncpg

from src.core.exceptions import (
    BatchOperationError,
    DatabaseNotConnectedError,
    DatabasePoolTimeoutError,
    ValidationError,
)
from src.utils.encryption import decrypt_password, encrypt_password
from src.utils.validators import validate_email, validate_phone

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


async def _migrate_encrypt_passport_numbers(conn: asyncpg.Connection) -> None:
    """
    Data migration: Encrypt existing passport numbers in personal_details table.
    
    Args:
        conn: Database connection
    """
    # Fetch all rows with unencrypted passport numbers
    rows = await conn.fetch(
        """
        SELECT id, passport_number 
        FROM personal_details 
        WHERE passport_number IS NOT NULL 
          AND passport_number != '' 
          AND (passport_number_encrypted IS NULL OR passport_number_encrypted = '')
        """
    )
    
    if not rows:
        logger.info("No passport numbers to encrypt")
        return
    
    encrypted_count = 0
    failed_count = 0
    
    for row in rows:
        try:
            encrypted_passport = encrypt_password(row["passport_number"])
            await conn.execute(
                """
                UPDATE personal_details 
                SET passport_number_encrypted = $1, passport_number = ''
                WHERE id = $2
                """,
                encrypted_passport,
                row["id"]
            )
            encrypted_count += 1
        except Exception as e:
            logger.error(f"Failed to encrypt passport for record {row['id']}: {e}")
            failed_count += 1
    
    logger.info(
        f"Passport encryption migration completed: "
        f"{encrypted_count} encrypted, {failed_count} failed"
    )


class Database:
    """PostgreSQL database manager for VFS-Bot with connection pooling."""

    # Define migrations as a class-level constant to avoid duplication
    MIGRATIONS = [
        {
            "version": 1,
            "description": "Add visa_category to appointment_requests",
            "table": "appointment_requests",
            "column": "visa_category",
            "sql": "ALTER TABLE appointment_requests ADD COLUMN IF NOT EXISTS visa_category TEXT",
            "default_sql": "UPDATE appointment_requests SET visa_category = '' WHERE visa_category IS NULL",
            "rollback_sql": "ALTER TABLE appointment_requests DROP COLUMN IF EXISTS visa_category",
        },
        {
            "version": 2,
            "description": "Add visa_subcategory to appointment_requests",
            "table": "appointment_requests",
            "column": "visa_subcategory",
            "sql": "ALTER TABLE appointment_requests ADD COLUMN IF NOT EXISTS visa_subcategory TEXT",
            "default_sql": "UPDATE appointment_requests SET visa_subcategory = '' WHERE visa_subcategory IS NULL",
            "rollback_sql": "ALTER TABLE appointment_requests DROP COLUMN IF EXISTS visa_subcategory",
        },
        {
            "version": 3,
            "description": "Add gender to appointment_persons",
            "table": "appointment_persons",
            "column": "gender",
            "sql": "ALTER TABLE appointment_persons ADD COLUMN IF NOT EXISTS gender TEXT",
            "default_sql": "UPDATE appointment_persons SET gender = 'male' WHERE gender IS NULL",
            "rollback_sql": "ALTER TABLE appointment_persons DROP COLUMN IF EXISTS gender",
        },
        {
            "version": 4,
            "description": "Add is_child_with_parent to appointment_persons",
            "table": "appointment_persons",
            "column": "is_child_with_parent",
            "sql": "ALTER TABLE appointment_persons ADD COLUMN IF NOT EXISTS is_child_with_parent BOOLEAN",
            "default_sql": "UPDATE appointment_persons SET is_child_with_parent = FALSE WHERE is_child_with_parent IS NULL",
            "rollback_sql": "ALTER TABLE appointment_persons DROP COLUMN IF EXISTS is_child_with_parent",
        },
        {
            "version": 5,
            "description": "Add passport_number_encrypted to personal_details for PII encryption",
            "table": "personal_details",
            "column": "passport_number_encrypted",
            "sql": "ALTER TABLE personal_details ADD COLUMN IF NOT EXISTS passport_number_encrypted TEXT",
            "default_sql": "",  # No default needed, will be populated by migration
            "data_migration_func": _migrate_encrypt_passport_numbers,
            "rollback_sql": "ALTER TABLE personal_details DROP COLUMN IF EXISTS passport_number_encrypted",
        },

    ]

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
            logger.error(
                f"Database query failed (non-critical), returning fallback value: {e}"
            )
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
                await conn.execute(
                    """
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
                """
                )

                # Personal details table
                await conn.execute(
                    """
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
                """
                )

                # Appointments table
                await conn.execute(
                    """
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
                """
                )

                # Logs table
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS logs (
                        id BIGSERIAL PRIMARY KEY,
                        level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        user_id BIGINT,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
                    )
                """
                )

                # Payment card table (single card for all payments)
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS payment_card (
                        id BIGSERIAL PRIMARY KEY,
                        card_holder_name TEXT NOT NULL,
                        card_number_encrypted TEXT NOT NULL,
                        expiry_month TEXT NOT NULL,
                        expiry_year TEXT NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """
                )

                # Admin secret usage tracking table (multi-worker safe)
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS admin_secret_usage (
                        id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
                        consumed BOOLEAN NOT NULL DEFAULT false,
                        consumed_at TIMESTAMPTZ
                    )
                """
                )

                # Appointment requests table
                await conn.execute(
                    """
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
                """
                )

                # Appointment persons table
                await conn.execute(
                    """
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
                """
                )

                # Audit log table
                await conn.execute(
                    """
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
                """
                )

                # Audit log indexes
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)
                """
                )
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id)
                """
                )
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)
                """
                )

                # Appointment history table
                await conn.execute(
                    """
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
                """
                )

                # Index for faster queries
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_appointment_history_user_status
                    ON appointment_history(user_id, status)
                """
                )

                # User webhooks table - per-user OTP webhook tokens
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_webhooks (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL UNIQUE,
                        webhook_token VARCHAR(64) UNIQUE NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """
                )

                # Index for faster webhook token lookups
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_user_webhooks_token
                    ON user_webhooks(webhook_token)
                """
                )

                # Proxy endpoints table
                await conn.execute(
                    """
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
                """
                )

                # Index for active proxies lookup
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_proxy_endpoints_active
                    ON proxy_endpoints(is_active)
                """
                )

                # Token blacklist table
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS token_blacklist (
                        jti VARCHAR(64) PRIMARY KEY,
                        exp TIMESTAMPTZ NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """
                )

                # Index for cleanup
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_token_blacklist_exp
                    ON token_blacklist(exp)
                """
                )

                # Schema migrations table for versioned migrations
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        description TEXT NOT NULL,
                        applied_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """
                )

            # Migration: Add new columns if they don't exist (versioned)
            await self._run_versioned_migrations()

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
                TABLES_WITH_UPDATED_AT = frozenset(['users', 'personal_details', 'payment_card', 
                                                     'appointment_requests', 'appointment_history', 'proxy_endpoints'])
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
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_appointments_user_id ON appointments(user_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_personal_details_user_id ON personal_details(user_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_user_id ON logs(user_id)")

            logger.info("Database tables created/verified")

    async def _run_versioned_migrations(self) -> None:
        """
        Run versioned database migrations.

        This method implements a versioning system for database migrations.
        Each migration is tracked in the schema_migrations table to ensure
        it only runs once. Provides backward compatibility with existing
        databases by detecting already-applied changes.
        
        Note: Requires PostgreSQL 9.6+ for ADD COLUMN IF NOT EXISTS syntax.
        """
        if self.pool is None:
            raise RuntimeError("Database connection is not established.")

        # Whitelist of valid table names for security
        VALID_TABLES = frozenset({
            "appointment_requests",
            "appointment_persons",
            "payment_card",
            "users",
            "personal_details",
            "appointments",
            "logs",
            "audit_log",
            "appointment_history",
            "user_webhooks",
            "proxy_endpoints",
            "token_blacklist",
        })

        # Use class-level migrations constant
        migrations = self.MIGRATIONS

        # Validate all migration table names against whitelist
        for migration in migrations:
            if migration["table"] not in VALID_TABLES:
                raise ValueError(
                    f"Invalid table name in migration v{migration['version']}: "
                    f"{migration['table']}"
                )

        async with self.pool.acquire() as conn:
            # Get applied migrations
            applied_versions = {
                row["version"]
                for row in await conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
            }

            # Backward compatibility: Check if migrations already applied
            # If schema_migrations is empty but columns exist, mark as applied
            if not applied_versions:
                for migration in migrations:
                    # Check if column exists in PostgreSQL
                    column_exists = await conn.fetchval(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = $1 AND column_name = $2
                        )
                        """,
                        migration["table"],
                        migration["column"],
                    )

                    if column_exists:
                        # Column exists, mark migration as applied
                        await conn.execute(
                            """INSERT INTO schema_migrations (version, description)
                               VALUES ($1, $2)""",
                            migration["version"],
                            migration["description"],
                        )
                        applied_versions.add(migration["version"])
                        logger.info(
                            f"Migration v{migration['version']} already applied "
                            f"(backward compatibility): {migration['description']}"
                        )

            # Determine pending migrations
            pending_migrations = [m for m in migrations if m["version"] not in applied_versions]

            # Apply pending migrations
            for migration in pending_migrations:

                # Run migration in its own transaction
                try:
                    logger.info(f"Applying migration v{migration['version']}: {migration['description']}")

                    async with conn.transaction():
                        # Execute the migration SQL
                        await conn.execute(migration["sql"])

                        # Execute default value update if provided
                        if migration.get("default_sql"):
                            await conn.execute(migration["default_sql"])

                        # Execute custom data migration function if provided
                        if migration.get("data_migration_func"):
                            logger.info(f"Running custom data migration for v{migration['version']}")
                            await migration["data_migration_func"](conn)

                        # Record migration
                        await conn.execute(
                            """INSERT INTO schema_migrations (version, description)
                               VALUES ($1, $2)""",
                            migration["version"],
                            migration["description"],
                        )

                    logger.info(f"Migration v{migration['version']} completed successfully")

                except Exception as e:
                    logger.error(f"Migration v{migration['version']} failed: {e}")
                    # Re-raise to prevent partial migration state
                    raise

            logger.info("All schema migrations completed")

    def _get_migration_by_version(self, version: int) -> Optional[Dict[str, Any]]:
        """
        Get migration definition by version number.

        Args:
            version: Migration version number

        Returns:
            Migration dict if found, None otherwise
        """
        # Use class-level migrations constant
        for migration in self.MIGRATIONS:
            if migration["version"] == version:
                return migration
        return None

    async def rollback_migration(self, target_version: int) -> None:
        """
        Rollback migrations to a target version.

        This method rolls back all migrations with versions greater than target_version.
        Migrations are rolled back in reverse order (highest version first).

        Args:
            target_version: Target version to rollback to (exclusive)

        Raises:
            RuntimeError: If database connection is not established
            ValueError: If a migration lacks rollback_sql
        """
        if self.pool is None:
            raise RuntimeError("Database connection is not established.")

        async with self.pool.acquire() as conn:
            # Get applied migrations greater than target version (DESC order)
            applied_migrations = await conn.fetch(
                """
                SELECT version, description
                FROM schema_migrations
                WHERE version > $1
                ORDER BY version DESC
                """,
                target_version,
            )

            if not applied_migrations:
                logger.info(
                    f"No migrations to rollback (target version: {target_version})"
                )
                return

            # Rollback each migration in reverse order
            for row in applied_migrations:
                version = row["version"]
                description = row["description"]

                # Get migration definition
                migration = self._get_migration_by_version(version)
                if migration is None:
                    raise ValueError(
                        f"Migration definition not found for version {version}"
                    )

                # Get rollback SQL
                rollback_sql = migration.get("rollback_sql")
                if not rollback_sql:
                    raise ValueError(
                        f"Migration v{version} does not have rollback_sql defined"
                    )

                # Execute rollback in transaction
                try:
                    logger.info(f"Rolling back migration v{version}: {description}")

                    async with conn.transaction():
                        # Execute rollback SQL
                        await conn.execute(rollback_sql)

                        # Remove migration record
                        await conn.execute(
                            "DELETE FROM schema_migrations WHERE version = $1",
                            version,
                        )

                    logger.info(f"Migration v{version} rolled back successfully")

                except Exception as e:
                    logger.error(f"Rollback of migration v{version} failed: {e}")
                    raise

            logger.info(
                f"Rollback completed. Current version: {target_version}"
            )

    async def _migrate_schema(self) -> None:
        """Migrate database schema for new columns (legacy method for backward compatibility)."""
        # This method is now handled by _run_versioned_migrations
        # Keep for backward compatibility but make it a no-op
        logger.info("Schema migration handled by versioned migrations")
        pass

    @require_connection
    async def add_user(
        self, email: str, password: str, centre: str, category: str, subcategory: str
    ) -> int:
        """
        Add a new user to the database.

        Args:
            email: User email
            password: User password (will be encrypted before storage)
            centre: VFS centre
            category: Visa category
            subcategory: Visa subcategory

        Returns:
            User ID

        Raises:
            ValidationError: If email format is invalid
        """
        # Validate email format
        if not validate_email(email):
            raise ValidationError(f"Invalid email format: {email}", field="email")

        # Encrypt password before storing (NOT hashing - we need plaintext for VFS login)
        encrypted_password = encrypt_password(password)

        async with self.get_connection() as conn:
            user_id = await conn.fetchval(
                """
                INSERT INTO users (email, password, centre, category, subcategory)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """,
                email,
                encrypted_password,
                centre,
                category,
                subcategory,
            )
            logger.info(f"User added: {email}")
            if user_id is None:
                raise RuntimeError("Failed to fetch user ID after insert")
            return int(user_id)

    @require_connection
    async def get_active_users(self) -> List[Dict[str, Any]]:
        """
        Get all active users.

        Returns:
            List of user dictionaries
        """
        async with self.get_connection() as conn:
            rows = await conn.fetch("SELECT * FROM users WHERE active = true")
            return [dict(row) for row in rows]

    @require_connection
    async def get_user_with_decrypted_password(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user with decrypted password for VFS login.

        Args:
            user_id: User ID

        Returns:
            User dictionary with decrypted password or None

        Raises:
            ValueError: If user_id is invalid (negative or zero)
        """
        # Validate user_id parameter
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}. Must be a positive integer.")

        async with self.get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
            if row:
                user = dict(row)
                # Decrypt password for VFS login
                try:
                    user["password"] = decrypt_password(user["password"])
                except Exception as e:
                    logger.error(f"Failed to decrypt password for user {user_id}: {e}")
                    raise
                return user
            return None

    @require_connection
    async def get_active_users_with_decrypted_passwords(self) -> List[Dict[str, Any]]:
        """
        Get all active users with decrypted passwords for VFS login.

        Returns:
            List of user dictionaries with decrypted passwords
        """
        async with self.get_connection() as conn:
            rows = await conn.fetch("SELECT * FROM users WHERE active = true")
            users = []
            failed_users = []
            for row in rows:
                user = dict(row)
                # Decrypt password for VFS login
                try:
                    user["password"] = decrypt_password(user["password"])
                    users.append(user)
                except Exception as e:
                    logger.error(
                        f"Failed to decrypt password for user "
                        f"{user['id']} ({user['email']}): {e}. "
                        f"User needs to re-register with new password."
                    )
                    failed_users.append(user["email"])

            # Alert if users failed decryption
            if failed_users:
                logger.warning(
                    f"⚠️  {len(failed_users)} user(s) have invalid "
                    f"encrypted passwords and will be skipped: "
                    f"{', '.join(failed_users)}. They need to re-register."
                )

            return users

    @require_connection
    async def add_personal_details(self, user_id: int, details: Dict[str, Any]) -> int:
        """
        Add personal details for a user.

        Args:
            user_id: User ID
            details: Personal details dictionary

        Returns:
            Personal details ID

        Raises:
            ValidationError: If email or phone format is invalid
            ValueError: If user_id is invalid
        """
        # Validate user_id parameter
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}. Must be a positive integer.")

        # Validate email if provided
        email = details.get("email")
        if email and not validate_email(email):
            raise ValidationError(f"Invalid email format: {email}", field="email")

        # Validate phone if provided
        mobile_number = details.get("mobile_number")
        if mobile_number and not validate_phone(mobile_number):
            raise ValidationError(
                f"Invalid phone number format: {mobile_number}", field="mobile_number"
            )

        # Encrypt passport number if provided
        passport_number = details.get("passport_number")
        passport_number_encrypted = None
        if passport_number:
            passport_number_encrypted = encrypt_password(passport_number)

        async with self.get_connection() as conn:
            personal_id = await conn.fetchval(
                """
                INSERT INTO personal_details
                (user_id, first_name, last_name, passport_number, passport_number_encrypted, passport_expiry,
                 gender, mobile_code, mobile_number, email, nationality, date_of_birth,
                 address_line1, address_line2, state, city, postcode)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                RETURNING id
            """,
                user_id,
                details.get("first_name"),
                details.get("last_name"),
                "",  # Keep old passport_number empty for backward compatibility
                passport_number_encrypted,
                details.get("passport_expiry"),
                details.get("gender"),
                details.get("mobile_code"),
                details.get("mobile_number"),
                details.get("email"),
                details.get("nationality"),
                details.get("date_of_birth"),
                details.get("address_line1"),
                details.get("address_line2"),
                details.get("state"),
                details.get("city"),
                details.get("postcode"),
            )
            logger.info(f"Personal details added for user {user_id}")
            if personal_id is None:
                raise RuntimeError("Failed to fetch ID after insert")
            return int(personal_id)

    @require_connection
    async def get_personal_details(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get personal details for a user.

        Args:
            user_id: User ID

        Returns:
            Personal details dictionary or None

        Raises:
            ValueError: If user_id is invalid
        """
        # Validate user_id parameter
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}. Must be a positive integer.")

        async with self.get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM personal_details WHERE user_id = $1", user_id)
            if not row:
                return None
            
            details = dict(row)
            
            # Decrypt passport number if encrypted version exists
            if details.get("passport_number_encrypted"):
                try:
                    details["passport_number"] = decrypt_password(details["passport_number_encrypted"])
                except Exception as e:
                    logger.warning(f"Failed to decrypt passport number for user {user_id}: {e}")
                    # Fall back to old unencrypted value if available
                    if not details.get("passport_number"):
                        details["passport_number"] = None
            
            return details

    @require_connection
    async def get_personal_details_batch(self, user_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """
        Get personal details for multiple users in a single query (N+1 query prevention).

        Args:
            user_ids: List of user IDs

        Returns:
            Dictionary mapping user_id to personal details dictionary

        Raises:
            ValueError: If user_ids is empty or contains invalid IDs
        """
        if not user_ids:
            return {}

        # Validate all user_ids
        for user_id in user_ids:
            if not isinstance(user_id, int) or user_id <= 0:
                raise ValueError(f"Invalid user_id: {user_id}. Must be a positive integer.")

        async with self.get_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM personal_details WHERE user_id = ANY($1::bigint[])",
                user_ids
            )

            # Map results by user_id
            result = {}
            for row in rows:
                details = dict(row)
                
                # Decrypt passport number if encrypted version exists
                if details.get("passport_number_encrypted"):
                    try:
                        details["passport_number"] = decrypt_password(details["passport_number_encrypted"])
                    except Exception as e:
                        logger.warning(f"Failed to decrypt passport number for user {details['user_id']}: {e}")
                        # Fall back to old unencrypted value if available
                        if not details.get("passport_number"):
                            details["passport_number"] = None
                
                result[details["user_id"]] = details

            return result

    @require_connection
    async def get_all_users_with_details(self) -> List[Dict[str, Any]]:
        """
        Get all users with their personal details joined.

        Returns:
            List of user dictionaries with personal details
        """
        async with self.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    u.id, u.email, u.centre as center_name,
                    u.category as visa_category, u.subcategory as visa_subcategory,
                    u.active as is_active, u.created_at, u.updated_at,
                    p.first_name, p.last_name, p.mobile_number as phone
                FROM users u
                LEFT JOIN personal_details p ON u.id = p.user_id
                ORDER BY u.created_at DESC
            """
            )
            return [dict(row) for row in rows]

    @require_connection
    async def get_user_with_details_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single user with their personal details joined by user ID.

        This method provides better performance than fetching all users
        and filtering in Python when you only need one user.

        Args:
            user_id: User ID to retrieve

        Returns:
            User dictionary with personal details or None if not found

        Raises:
            ValueError: If user_id is invalid
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}")
        
        async with self.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT u.id, u.email, u.centre as center_name,
                       u.category as visa_category, u.subcategory as visa_subcategory,
                       u.active as is_active, u.created_at, u.updated_at,
                       p.first_name, p.last_name, p.mobile_number as phone
                FROM users u
                LEFT JOIN personal_details p ON u.id = p.user_id
                WHERE u.id = $1
                """, user_id
            )
            return dict(row) if row else None

    @require_connection
    async def update_user(
        self,
        user_id: int,
        email: Optional[str] = None,
        password: Optional[str] = None,
        centre: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> bool:
        """
        Update user information with explicit field whitelist.

        Only allows updating specific whitelisted fields to prevent SQL injection.

        Args:
            user_id: User ID
            email: New email (optional)
            password: New password (optional, will be encrypted)
            centre: New centre (optional)
            category: New visa category (optional)
            subcategory: New visa subcategory (optional)
            active: New active status (optional)

        Returns:
            True if user was updated, False if not found

        Raises:
            ValidationError: If email format is invalid
        """
        # Validate email if provided
        if email and not validate_email(email):
            raise ValidationError(f"Invalid email format: {email}", field="email")

        # Build dynamic update query
        updates: List[str] = []
        params: List[Any] = []
        param_num = 1

        if email is not None:
            updates.append(f"email = ${param_num}")
            params.append(email)
            param_num += 1
        if password is not None:
            # Encrypt password before storage
            encrypted_password = encrypt_password(password)
            updates.append(f"password = ${param_num}")
            params.append(encrypted_password)
            param_num += 1
        if centre is not None:
            updates.append(f"centre = ${param_num}")
            params.append(centre)
            param_num += 1
        if category is not None:
            updates.append(f"category = ${param_num}")
            params.append(category)
            param_num += 1
        if subcategory is not None:
            updates.append(f"subcategory = ${param_num}")
            params.append(subcategory)
            param_num += 1
        if active is not None:
            updates.append(f"active = ${param_num}")
            params.append(active)
            param_num += 1

        if not updates:
            return True  # Nothing to update

        updates.append("updated_at = NOW()")
        params.append(user_id)

        async with self.get_connection() as conn:
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ${param_num}"
            result = await conn.execute(query, *params)

            if result == "UPDATE 0":
                return False

            logger.info(f"User {user_id} updated")
            return True

    @require_connection
    async def update_personal_details(
        self,
        user_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        mobile_number: Optional[str] = None,
        **other_fields: Any,
    ) -> bool:
        """
        Update personal details for a user with SQL injection protection.

        Args:
            user_id: User ID
            first_name: New first name (optional)
            last_name: New last name (optional)
            mobile_number: New mobile number (optional)
            **other_fields: Other personal detail fields

        Returns:
            True if updated, False if not found

        Raises:
            ValidationError: If phone format is invalid
            ValueError: If user_id is invalid
        """
        # Validate user_id
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("Invalid user_id")

        # Validate phone if provided
        if mobile_number and not validate_phone(mobile_number):
            raise ValidationError(
                f"Invalid phone number format: {mobile_number}", field="mobile_number"
            )

        # Build dynamic update query
        updates: List[str] = []
        params: List[Any] = []
        param_num = 1

        if first_name is not None:
            updates.append(f"first_name = ${param_num}")
            params.append(first_name)
            param_num += 1
        if last_name is not None:
            updates.append(f"last_name = ${param_num}")
            params.append(last_name)
            param_num += 1
        if mobile_number is not None:
            updates.append(f"mobile_number = ${param_num}")
            params.append(mobile_number)
            param_num += 1

        # Filter only allowed fields and log rejected fields in a single pass
        valid_fields = {}
        rejected = set()

        for field, value in other_fields.items():
            if value is not None:
                if field in ALLOWED_PERSONAL_DETAILS_FIELDS:
                    valid_fields[field] = value
                else:
                    rejected.add(field)

        # Log rejected fields (potential attack attempt)
        if rejected:
            logger.warning(f"Rejected disallowed fields for user {user_id}: {rejected}")

        # Add valid fields to update
        for field, value in valid_fields.items():
            # Encrypt passport_number if present
            if field == "passport_number" and value is not None:
                # Encrypt and store in passport_number_encrypted
                encrypted_value = encrypt_password(value)
                updates.append(f"passport_number_encrypted = ${param_num}")
                params.append(encrypted_value)
                param_num += 1
                # Clear old unencrypted field
                updates.append(f"passport_number = ${param_num}")
                params.append("")
                param_num += 1
            else:
                updates.append(f"{field} = ${param_num}")
                params.append(value)
                param_num += 1

        if not updates:
            return True  # Nothing to update (success case)

        # Add updated_at timestamp and user_id
        updates.append(f"updated_at = ${param_num}")
        params.append(datetime.now(timezone.utc))
        param_num += 1
        params.append(user_id)

        async with self.get_connection() as conn:
            query = f"UPDATE personal_details SET {', '.join(updates)} WHERE user_id = ${param_num}"
            result = await conn.execute(query, *params)

            if result == "UPDATE 0":
                return False

            logger.info(f"Personal details updated for user {user_id}")
            return True

    @require_connection
    async def delete_user(self, user_id: int) -> bool:
        """
        Delete a user and all associated data (cascading).

        Args:
            user_id: User ID

        Returns:
            True if user was deleted, False if not found

        Raises:
            ValueError: If user_id is invalid
        """
        # Validate user_id parameter
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}. Must be a positive integer.")

        async with self.get_connection() as conn:
            result = await conn.execute("DELETE FROM users WHERE id = $1", user_id)

            if result == "DELETE 0":
                return False

            logger.info(f"User {user_id} deleted")
            return True

    @require_connection
    async def add_users_batch(self, users: List[Dict[str, Any]]) -> List[int]:
        """
        Add multiple users in a single transaction for improved performance.

        Args:
            users: List of user dictionaries with keys:
                email, password, centre, category, subcategory

        Returns:
            List of user IDs for successfully added users

        Raises:
            ValidationError: If any email format is invalid
            BatchOperationError: If batch operation fails
        """
        if not users:
            return []

        # Validate all emails first (fail fast)
        for user in users:
            email = user.get("email")
            if not email or not validate_email(email):
                raise ValidationError(f"Invalid email format: {email}", field="email")

        user_ids: List[int] = []
        failed_count = 0

        async with self.get_connection() as conn:
            try:
                async with conn.transaction():
                    # Insert users one by one with RETURNING to get IDs
                    for user in users:
                        # Encrypt password before storing
                        encrypted_password = encrypt_password(user["password"])
                        
                        user_id = await conn.fetchval(
                            """
                            INSERT INTO users (email, password, centre, category, subcategory)
                            VALUES ($1, $2, $3, $4, $5)
                            RETURNING id
                            """,
                            user["email"],
                            encrypted_password,
                            user["centre"],
                            user["category"],
                            user["subcategory"],
                        )
                        if user_id:
                            user_ids.append(user_id)

                    logger.info(f"Batch added {len(user_ids)} users")
                    return user_ids

            except Exception as e:
                failed_count = len(users) - len(user_ids)
                logger.error(f"Batch user insert failed: {e}")
                raise BatchOperationError(
                    f"Failed to add users in batch: {e}",
                    operation="add_users_batch",
                    failed_count=failed_count,
                    total_count=len(users),
                ) from e

    @require_connection
    async def update_users_batch(self, updates: List[Dict[str, Any]]) -> int:
        """
        Update multiple users in a single transaction for improved performance.

        Each update dict should contain 'id' and the fields to update.
        Field names are validated against ALLOWED_USER_UPDATE_FIELDS whitelist.

        Args:
            updates: List of update dictionaries with 'id' and optional fields:
                    email, password, centre, category, subcategory, active

        Returns:
            Number of users successfully updated

        Raises:
            ValidationError: If any email format is invalid or invalid field name
            BatchOperationError: If batch operation fails
        """
        if not updates:
            return 0

        # Validate all emails first and check field names (fail fast)
        for update in updates:
            email = update.get("email")
            if email and not validate_email(email):
                raise ValidationError(f"Invalid email format: {email}", field="email")
            
            # Validate field names against whitelist (excluding 'id')
            for field_name in update.keys():
                if field_name != "id" and field_name not in ALLOWED_USER_UPDATE_FIELDS:
                    raise ValidationError(
                        f"Invalid field name for user update: {field_name}",
                        field=field_name
                    )

        updated_count = 0

        async with self.get_connection() as conn:
            try:
                async with conn.transaction():
                    # Process each update individually but within a single transaction
                    for update in updates:
                        user_id = update.get("id")
                        if not user_id:
                            logger.warning("Skipping update without user_id")
                            continue

                        # Build dynamic update query
                        fields: List[str] = []
                        params: List[Any] = []
                        param_num = 1

                        if "email" in update:
                            fields.append(f"email = ${param_num}")
                            params.append(update["email"])
                            param_num += 1
                        if "password" in update:
                            # Encrypt password before storage
                            encrypted_password = encrypt_password(update["password"])
                            fields.append(f"password = ${param_num}")
                            params.append(encrypted_password)
                            param_num += 1
                        if "centre" in update:
                            fields.append(f"centre = ${param_num}")
                            params.append(update["centre"])
                            param_num += 1
                        if "category" in update:
                            fields.append(f"category = ${param_num}")
                            params.append(update["category"])
                            param_num += 1
                        if "subcategory" in update:
                            fields.append(f"subcategory = ${param_num}")
                            params.append(update["subcategory"])
                            param_num += 1
                        if "active" in update:
                            fields.append(f"active = ${param_num}")
                            params.append(update["active"])
                            param_num += 1

                        if not fields:
                            continue

                        fields.append("updated_at = NOW()")
                        params.append(user_id)

                        query = f"UPDATE users SET {', '.join(fields)} WHERE id = ${param_num}"
                        result = await conn.execute(query, *params)

                        if result != "UPDATE 0":
                            updated_count += 1

                    logger.info(f"Batch updated {updated_count} users")
                    return updated_count

            except Exception as e:
                logger.error(f"Batch user update failed: {e}")
                raise BatchOperationError(
                    f"Failed to update users in batch: {e}",
                    operation="update_users_batch",
                    failed_count=len(updates) - updated_count,
                    total_count=len(updates),
                ) from e

    @require_connection
    async def add_appointment(
        self,
        user_id: int,
        centre: str,
        category: str,
        subcategory: str,
        date: Optional[str] = None,
        time: Optional[str] = None,
        reference: Optional[str] = None,
    ) -> int:
        """
        Add an appointment record.

        Args:
            user_id: User ID
            centre: VFS centre
            category: Visa category
            subcategory: Visa subcategory
            date: Appointment date
            time: Appointment time
            reference: Reference number

        Returns:
            Appointment ID
        """
        async with self.get_connection() as conn:
            appt_id = await conn.fetchval(
                """
                INSERT INTO appointments
                (user_id, centre, category, subcategory, appointment_date,
                 appointment_time, reference_number)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
            """,
                user_id, centre, category, subcategory, date, time, reference,
            )
            logger.info(f"Appointment added for user {user_id}")
            if appt_id is None:
                raise RuntimeError("Failed to fetch ID after insert")
            return int(appt_id)

    @require_connection
    async def get_appointments(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get appointments, optionally filtered by user.

        Args:
            user_id: Optional user ID filter

        Returns:
            List of appointment dictionaries
        """
        async with self.get_connection() as conn:
            if user_id:
                rows = await conn.fetch("SELECT * FROM appointments WHERE user_id = $1", user_id)
            else:
                rows = await conn.fetch("SELECT * FROM appointments")
            return [dict(row) for row in rows]

    @require_connection
    async def add_log(self, level: str, message: str, user_id: Optional[int] = None) -> None:
        """
        Add a log entry.

        Args:
            level: Log level (INFO, WARNING, ERROR)
            message: Log message
            user_id: Optional user ID
        """
        async with self.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO logs (level, message, user_id)
                VALUES ($1, $2, $3)
            """,
                level, message, user_id,
            )

    @require_connection
    async def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent log entries.

        Args:
            limit: Maximum number of logs to retrieve

        Returns:
            List of log dictionaries
        """
        async with self.get_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM logs ORDER BY created_at DESC LIMIT $1", limit
            )
            return [dict(row) for row in rows]

    @require_connection
    async def add_blacklisted_token(self, jti: str, exp: datetime) -> None:
        """
        Add a token to the blacklist.

        Args:
            jti: JWT ID (jti claim)
            exp: Token expiration time
        """
        async with self.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO token_blacklist (jti, exp)
                VALUES ($1, $2)
                ON CONFLICT (jti) DO UPDATE SET exp = EXCLUDED.exp
                """,
                jti, exp.isoformat(),
            )

    @require_connection
    async def is_token_blacklisted(self, jti: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            jti: JWT ID to check

        Returns:
            True if token is blacklisted and not expired
        """
        async with self.get_connection() as conn:
            now = datetime.now(timezone.utc).isoformat()
            result = await conn.fetchval(
                """
                SELECT 1 FROM token_blacklist
                WHERE jti = $1 AND exp > $2
                """,
                jti, now,
            )
            return result is not None

    @require_connection
    async def get_active_blacklisted_tokens(self) -> List[tuple[str, datetime]]:
        """
        Get all active (non-expired) blacklisted tokens.

        Returns:
            List of (jti, exp) tuples
        """
        async with self.get_connection() as conn:
            now = datetime.now(timezone.utc).isoformat()
            rows = await conn.fetch(
                """
                SELECT jti, exp FROM token_blacklist
                WHERE exp > $1
                """,
                now,
            )
            return [(row[0], datetime.fromisoformat(row[1])) for row in rows]

    @require_connection
    async def cleanup_expired_tokens(self) -> int:
        """
        Remove expired tokens from blacklist.

        Returns:
            Number of tokens removed
        """
        async with self.get_connection() as conn:
            now = datetime.now(timezone.utc).isoformat()
            result = await conn.execute(
                """
                DELETE FROM token_blacklist
                WHERE exp <= $1
                """,
                now,
            )
            count = self._parse_command_tag(result)
            return count

    @require_connection
    async def save_payment_card(self, card_data: Dict[str, str]) -> int:
        """
        Save or update payment card.

        Note: CVV is NOT stored per PCI-DSS Requirement 3.2.
        Card holder must enter CVV at payment time.

        Args:
            card_data: Dictionary containing card_holder_name, card_number,
                      expiry_month, expiry_year

        Returns:
            Card ID

        Raises:
            ValueError: If card data is invalid
        """
        required_fields = ["card_holder_name", "card_number", "expiry_month", "expiry_year"]
        for field in required_fields:
            if field not in card_data:
                raise ValueError(f"Missing required field: {field}")

        # Defensive validation (defense-in-depth)
        card_number = card_data["card_number"]
        expiry_month = card_data["expiry_month"]

        # Validate card_number: only digits, length 13-19
        if not card_number.isdigit() or not (13 <= len(card_number) <= 19):
            raise ValueError("Card number must be 13-19 digits")

        # Validate expiry_month: must be 01-12
        try:
            month = int(expiry_month)
        except ValueError:
            raise ValueError("Invalid expiry month format")
        
        if not (1 <= month <= 12):
            raise ValueError("Expiry month must be between 01 and 12")

        # Encrypt sensitive data (card number only)
        card_number_encrypted = encrypt_password(card_data["card_number"])

        async with self.get_connection() as conn:
            # Check if a card already exists
            existing = await conn.fetchrow("SELECT id FROM payment_card LIMIT 1")

            if existing:
                # Update existing card
                await conn.execute(
                    """
                    UPDATE payment_card
                    SET card_holder_name = $1,
                        card_number_encrypted = $2,
                        expiry_month = $3,
                        expiry_year = $4,
                        updated_at = NOW()
                    WHERE id = $5
                    """,
                    card_data["card_holder_name"],
                    card_number_encrypted,
                    card_data["expiry_month"],
                    card_data["expiry_year"],
                    existing["id"],
                )
                logger.info("Payment card updated")
                return int(existing["id"])
            else:
                # Insert new card
                card_id = await conn.fetchval(
                    """
                    INSERT INTO payment_card
                    (card_holder_name, card_number_encrypted, expiry_month,
                     expiry_year)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                    """,
                    card_data["card_holder_name"],
                    card_number_encrypted,
                    card_data["expiry_month"],
                    card_data["expiry_year"],
                )
                if card_id is None:
                    raise RuntimeError("Failed to get inserted card ID")
                logger.info(f"Payment card created with ID: {card_id}")
                result_id: int = card_id
                return result_id

    @require_connection
    async def get_payment_card(self) -> Optional[Dict[str, Any]]:
        """
        Get the saved payment card with decrypted card number.

        Note: CVV is NOT stored per PCI-DSS Requirement 3.2.
        Card holder must enter CVV at payment time.

        Returns:
            Card dictionary with decrypted card number or None if no card exists
        """
        async with self.get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM payment_card LIMIT 1")

            if not row:
                return None

            card = dict(row)

            # Decrypt card number
            try:
                card["card_number"] = decrypt_password(card["card_number_encrypted"])
            except Exception as e:
                logger.error(f"Failed to decrypt card data: {e}")
                raise ValueError("Failed to decrypt card data")

            # Remove encrypted fields from response
            del card["card_number_encrypted"]

            return card

    @require_connection
    async def get_payment_card_masked(self) -> Optional[Dict[str, Any]]:
        """
        Get the saved payment card with masked card number (for frontend display).

        IMPORTANT: CVV is NOT returned in masked view.

        Returns:
            Card dictionary with masked card number or None if no card exists
        """
        async with self.get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM payment_card LIMIT 1")

            if not row:
                return None

            card = dict(row)

            # Decrypt card number to get last 4 digits, then mask
            try:
                card_number = decrypt_password(card["card_number_encrypted"])
                last_four = card_number[-4:]
                card["card_number_masked"] = f"**** **** **** {last_four}"
            except Exception as e:
                logger.error(f"Failed to decrypt card number: {e}")
                card["card_number_masked"] = "**** **** **** ****"

            # Remove encrypted fields (never expose in masked view)
            del card["card_number_encrypted"]

            return card

    @require_connection
    async def delete_payment_card(self) -> bool:
        """
        Delete the saved payment card.

        Returns:
            True if card was deleted, False if no card existed
        """
        async with self.get_connection() as conn:
            existing = await conn.fetchrow("SELECT id FROM payment_card LIMIT 1")

            if not existing:
                return False

            await conn.execute("DELETE FROM payment_card WHERE id = $1", existing["id"])
            logger.info("Payment card deleted")
            return True

    @require_connection
    async def create_appointment_request(
        self,
        country_code: str,
        visa_category: str,
        visa_subcategory: str,
        centres: List[str],
        preferred_dates: List[str],
        person_count: int,
        persons: List[Dict[str, Any]],
    ) -> int:
        """
        Create a new appointment request.

        Args:
            country_code: Target country code (e.g., 'nld', 'aut')
            visa_category: Visa category
            visa_subcategory: Visa subcategory
            centres: List of selected centres
            preferred_dates: List of preferred dates in DD/MM/YYYY format
            person_count: Number of persons (1-6)
            persons: List of person data dictionaries

        Returns:
            Request ID
        """
        import json

        async with self.get_connection() as conn:
            async with conn.transaction():
                # Insert appointment request
                request_id = await conn.fetchval(
                    """
                    INSERT INTO appointment_requests
                    (country_code, visa_category, visa_subcategory, centres,
                     preferred_dates, person_count)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    country_code,
                    visa_category,
                    visa_subcategory,
                    json.dumps(centres),
                    json.dumps(preferred_dates),
                    person_count,
                )
                if request_id is None:
                    raise RuntimeError("Failed to get inserted request ID")

                # Insert persons
                for person in persons:
                    # Validate email
                    email = person.get("email", "")
                    if not email:
                        raise ValidationError("Email is required for all persons", field="email")
                    if not validate_email(email):
                        raise ValidationError(f"Invalid email format: {email}", field="email")

                    await conn.execute(
                        """
                        INSERT INTO appointment_persons
                        (request_id, first_name, last_name, gender, nationality, birth_date,
                         passport_number, passport_issue_date, passport_expiry_date,
                         phone_code, phone_number, email, is_child_with_parent)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        """,
                        request_id,
                        person.get("first_name"),
                        person.get("last_name"),
                        person.get("gender", "male"),
                        person.get("nationality", "Turkey"),
                        person.get("birth_date"),
                        person.get("passport_number"),
                        person.get("passport_issue_date"),
                        person.get("passport_expiry_date"),
                        person.get("phone_code", "90"),
                        person.get("phone_number"),
                        person.get("email"),
                        person.get("is_child_with_parent", False),
                    )

                logger.info(f"Appointment request created: {request_id}")
                result_id: int = request_id
                return result_id

    @require_connection
    async def get_appointment_request(self, request_id: int) -> Optional[Dict[str, Any]]:
        """
        Get appointment request with person details.

        Args:
            request_id: Request ID

        Returns:
            Request dictionary with persons list or None
        """
        import json

        async with self.get_connection() as conn:
            # Get request
            request_row = await conn.fetchrow(
                "SELECT * FROM appointment_requests WHERE id = $1", request_id
            )

            if not request_row:
                return None

            request = dict(request_row)

            # Parse JSON fields
            request["centres"] = json.loads(request["centres"])
            request["preferred_dates"] = json.loads(request["preferred_dates"])

            # Ensure visa fields have defaults for old records
            if "visa_category" not in request or request["visa_category"] is None:
                request["visa_category"] = ""
            if "visa_subcategory" not in request or request["visa_subcategory"] is None:
                request["visa_subcategory"] = ""

            # Get persons
            person_rows = await conn.fetch(
                "SELECT * FROM appointment_persons WHERE request_id = $1", request_id
            )
            request["persons"] = [dict(row) for row in person_rows]

            return request

    @require_connection
    async def get_all_appointment_requests(
        self, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all appointment requests.

        Args:
            status: Optional status filter ('pending', 'processing', 'completed', 'failed')

        Returns:
            List of request dictionaries with persons
        """
        import json

        async with self.get_connection() as conn:
            if status:
                request_rows = await conn.fetch(
                    """SELECT * FROM appointment_requests
                    WHERE status = $1 ORDER BY created_at DESC""",
                    status,
                )
            else:
                request_rows = await conn.fetch(
                    "SELECT * FROM appointment_requests ORDER BY created_at DESC"
                )

            requests = []

            for request_row in request_rows:
                request = dict(request_row)
                request["centres"] = json.loads(request["centres"])
                request["preferred_dates"] = json.loads(request["preferred_dates"])

                # Ensure visa fields have defaults for old records
                if "visa_category" not in request or request["visa_category"] is None:
                    request["visa_category"] = ""
                if "visa_subcategory" not in request or request["visa_subcategory"] is None:
                    request["visa_subcategory"] = ""

                # Get persons for this request
                person_rows = await conn.fetch(
                    "SELECT * FROM appointment_persons WHERE request_id = $1", request["id"]
                )
                request["persons"] = [dict(row) for row in person_rows]

                requests.append(request)

            return requests

    @require_connection
    async def get_pending_appointment_request_for_user(
        self, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent pending appointment request associated with a user.

        Matches by checking if any person in the request has the same email as the user.

        Args:
            user_id: User ID

        Returns:
            Appointment request dict with persons list, or None
        """
        async with self.get_connection() as conn:
            # Get user email
            user_row = await conn.fetchrow("SELECT email FROM users WHERE id = $1", user_id)
            if not user_row:
                return None

            user_email = user_row["email"]

            # Find pending request where any person matches user email
            row = await conn.fetchrow(
                """
                SELECT DISTINCT ar.id FROM appointment_requests ar
                JOIN appointment_persons ap ON ar.id = ap.request_id
                WHERE ap.email = $1 AND ar.status = 'pending'
                ORDER BY ar.created_at DESC
                LIMIT 1
                """,
                user_email,
            )
            if not row:
                return None

            # Use existing method to get full request with persons
            return await self.get_appointment_request(row["id"])

    @require_connection
    async def update_appointment_request_status(
        self, request_id: int, status: str, completed_at: Optional[datetime] = None
    ) -> bool:
        """
        Update appointment request status.

        Args:
            request_id: Request ID
            status: New status ('pending', 'processing', 'completed', 'failed')
            completed_at: Optional completion timestamp

        Returns:
            True if updated, False if request not found
        """
        async with self.get_connection() as conn:
            if completed_at:
                result = await conn.execute(
                    """
                    UPDATE appointment_requests
                    SET status = $1, completed_at = $2, updated_at = NOW()
                    WHERE id = $3
                    """,
                    status, completed_at, request_id,
                )
            else:
                result = await conn.execute(
                    """
                    UPDATE appointment_requests
                    SET status = $1, updated_at = NOW()
                    WHERE id = $2
                    """,
                    status, request_id,
                )

            if result != "UPDATE 0":
                logger.info(f"Appointment request {request_id} status updated to {status}")
                return True
            return False

    @require_connection
    async def delete_appointment_request(self, request_id: int) -> bool:
        """
        Delete appointment request (cascades to persons).

        Args:
            request_id: Request ID

        Returns:
            True if deleted, False if not found
        """
        async with self.get_connection() as conn:
            result = await conn.execute("DELETE FROM appointment_requests WHERE id = $1", request_id)

            if result != "DELETE 0":
                logger.info(f"Appointment request {request_id} deleted")
                return True
            return False

    @require_connection
    async def cleanup_completed_requests(self, days: int = 30) -> int:
        """
        Delete completed requests older than specified days.

        Args:
            days: Age threshold in days (default 30)

        Returns:
            Number of requests deleted
        """
        from datetime import timedelta

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        async with self.get_connection() as conn:
            result = await conn.execute(
                """
                DELETE FROM appointment_requests
                WHERE status = 'completed' AND completed_at < $1
                """,
                cutoff_date,
            )
            deleted_count = self._parse_command_tag(result)

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old appointment requests")

            result_count: int = deleted_count
            return result_count

    @require_connection
    async def add_audit_log(
        self,
        action: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[str] = None,
        success: bool = True,
    ) -> int:
        """
        Add an audit log entry.

        Args:
            action: Action performed (e.g., 'login', 'user_created', 'payment_initiated')
            user_id: Optional user ID
            username: Optional username
            ip_address: Optional client IP address
            user_agent: Optional client user agent
            details: Optional JSON details
            success: Whether the action was successful

        Returns:
            Audit log entry ID
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        async with self.get_connection() as conn:
            audit_id = await conn.fetchval(
                """
                INSERT INTO audit_log
                (action, user_id, username, ip_address, user_agent, details, timestamp, success)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                action,
                user_id,
                username,
                ip_address,
                user_agent,
                details,
                timestamp,
                success,
            )
            if audit_id is None:
                raise RuntimeError("Failed to fetch ID after insert")
            logger.debug(f"Audit log entry added: {action}")
            return int(audit_id)

    @require_connection
    async def get_audit_logs(
        self,
        limit: int = 100,
        action: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get audit log entries.

        Args:
            limit: Maximum number of entries to retrieve
            action: Optional filter by action type
            user_id: Optional filter by user ID

        Returns:
            List of audit log dictionaries
        """
        async with self.get_connection() as conn:
            query = "SELECT * FROM audit_log WHERE 1=1"
            params: List[Any] = []
            param_num = 1

            if action:
                query += f" AND action = ${param_num}"
                params.append(action)
                param_num += 1
            if user_id is not None:
                query += f" AND user_id = ${param_num}"
                params.append(user_id)
                param_num += 1

            query += f" ORDER BY timestamp DESC LIMIT ${param_num}"
            params.append(limit)

            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    @require_connection
    async def add_appointment_history(
        self,
        user_id: int,
        centre: str,
        mission: str,
        status: str,
        category: Optional[str] = None,
        slot_date: Optional[str] = None,
        slot_time: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> int:
        """
        Add appointment history record.

        Args:
            user_id: User ID
            centre: VFS centre
            mission: Target country mission code
            status: Status ('found', 'booked', 'failed', 'cancelled')
            category: Visa category
            slot_date: Appointment date
            slot_time: Appointment time
            error_message: Error message if failed

        Returns:
            History record ID
        """
        async with self.get_connection() as conn:
            history_id = await conn.fetchval(
                """
                INSERT INTO appointment_history
                (user_id, centre, mission, category, slot_date, slot_time, status, error_message)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                user_id, centre, mission, category, slot_date, slot_time, status, error_message,
            )
            return history_id or 0

    @require_connection
    async def get_appointment_history(
        self, user_id: int, limit: int = 50, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get appointment history for user.

        Args:
            user_id: User ID
            limit: Maximum records to return
            status: Filter by status (optional)

        Returns:
            List of history records
        """
        query = "SELECT * FROM appointment_history WHERE user_id = $1"
        params: List[Any] = [user_id]
        param_num = 2

        if status:
            query += f" AND status = ${param_num}"
            params.append(status)
            param_num += 1

        query += f" ORDER BY created_at DESC LIMIT ${param_num}"
        params.append(limit)

        async with self.get_connection() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    @require_connection
    async def update_appointment_status(
        self, history_id: int, status: str, error_message: Optional[str] = None
    ) -> bool:
        """Update appointment history status."""
        async with self.get_connection() as conn:
            await conn.execute(
                """
                UPDATE appointment_history
                SET status = $1, error_message = $2, updated_at = $3, attempt_count = attempt_count + 1
                WHERE id = $4
                """,
                status, error_message, datetime.now(timezone.utc), history_id,
            )
            return True

    # =====================
    # User Webhook Methods
    # =====================

    @require_connection
    async def create_user_webhook(self, user_id: int) -> str:
        """
        Create a unique webhook token for a user.

        Args:
            user_id: User ID

        Returns:
            Generated webhook token

        Raises:
            ValueError: If user already has a webhook
        """
        # Check if user already has a webhook
        existing = await self.get_user_webhook(user_id)
        if existing:
            raise ValueError("User already has a webhook")

        # Generate unique token
        token = secrets.token_urlsafe(32)

        async with self.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO user_webhooks (user_id, webhook_token, is_active)
                VALUES ($1, $2, true)
                """,
                user_id, token,
            )

        logger.info(f"Webhook created for user {user_id}: {token[:8]}...")
        return token

    @require_connection
    async def get_user_webhook(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get webhook information for a user.

        Args:
            user_id: User ID

        Returns:
            Webhook data or None if not found
        """
        async with self.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM user_webhooks WHERE user_id = $1
                """,
                user_id,
            )
            return dict(row) if row else None

    @require_connection
    async def delete_user_webhook(self, user_id: int) -> bool:
        """
        Delete a user's webhook.

        Args:
            user_id: User ID

        Returns:
            True if deleted, False if not found
        """
        async with self.get_connection() as conn:
            result = await conn.execute(
                """
                DELETE FROM user_webhooks WHERE user_id = $1
                """,
                user_id,
            )
            deleted = result != "DELETE 0"

        if deleted:
            logger.info(f"Webhook deleted for user {user_id}")
        result_bool: bool = deleted
        return result_bool

    # ================================================================================
    # Proxy Management Methods
    # ================================================================================

    @require_connection
    async def add_proxy(self, server: str, port: int, username: str, password: str) -> int:
        """
        Add a new proxy endpoint with encrypted password.

        Args:
            server: Proxy server hostname
            port: Proxy port
            username: Proxy username
            password: Proxy password (will be encrypted)

        Returns:
            Proxy ID

        Raises:
            ValueError: If proxy already exists
        """
        # Encrypt password before storing
        encrypted_password = encrypt_password(password)

        async with self.get_connection() as conn:
            try:
                proxy_id = await conn.fetchval(
                    """
                    INSERT INTO proxy_endpoints
                    (server, port, username, password_encrypted, updated_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    RETURNING id
                    """,
                    server, port, username, encrypted_password,
                )

                logger.info(f"Proxy added: {server}:{port} (ID: {proxy_id})")
                return proxy_id or 0

            except Exception as e:
                if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
                    raise ValueError(
                        f"Proxy with server={server}, port={port}, "
                        f"username={username} already exists"
                    )
                raise

    @require_connection
    async def get_active_proxies(self) -> List[Dict[str, Any]]:
        """
        Get all active proxies with decrypted passwords.

        Returns:
            List of proxy dictionaries with decrypted passwords
        """
        async with self.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT id, server, port, username, password_encrypted, is_active,
                       last_used, failure_count, created_at, updated_at
                FROM proxy_endpoints
                WHERE is_active = true
                ORDER BY failure_count ASC, last_used ASC NULLS FIRST
                """
            )

            proxies = []
            for row in rows:
                proxy = dict(row)
                # Decrypt password
                try:
                    proxy["password"] = decrypt_password(proxy["password_encrypted"])
                    del proxy["password_encrypted"]  # Remove encrypted version from response
                    proxies.append(proxy)
                except Exception as e:
                    logger.error(f"Failed to decrypt password for proxy {proxy['id']}: {e}")
                    # Skip proxies with decryption errors
                    continue

            return proxies

    @require_connection
    async def get_proxy_by_id(self, proxy_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single proxy by ID with decrypted password.

        Args:
            proxy_id: Proxy ID

        Returns:
            Proxy dictionary with decrypted password or None if not found
        """
        async with self.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, server, port, username, password_encrypted, is_active,
                       last_used, failure_count, created_at, updated_at
                FROM proxy_endpoints
                WHERE id = $1
                """,
                proxy_id,
            )

            if not row:
                return None

            proxy = dict(row)
            # Decrypt password
            try:
                proxy["password"] = decrypt_password(proxy["password_encrypted"])
                del proxy["password_encrypted"]
                return proxy
            except Exception as e:
                logger.error(f"Failed to decrypt password for proxy {proxy_id}: {e}")
                return None

    @require_connection
    async def update_proxy(
        self,
        proxy_id: int,
        server: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> bool:
        """
        Update a proxy endpoint.

        Args:
            proxy_id: Proxy ID
            server: New server hostname (optional)
            port: New port (optional)
            username: New username (optional)
            password: New password (optional, will be encrypted)
            is_active: New active status (optional)

        Returns:
            True if updated, False if not found

        Raises:
            ValueError: If update violates uniqueness constraint
        """
        # Build dynamic update query
        updates: List[str] = []
        params: List[Any] = []
        param_num = 1

        if server is not None:
            updates.append(f"server = ${param_num}")
            params.append(server)
            param_num += 1

        if port is not None:
            updates.append(f"port = ${param_num}")
            params.append(port)
            param_num += 1

        if username is not None:
            updates.append(f"username = ${param_num}")
            params.append(username)
            param_num += 1

        if password is not None:
            updates.append(f"password_encrypted = ${param_num}")
            params.append(encrypt_password(password))
            param_num += 1

        if is_active is not None:
            updates.append(f"is_active = ${param_num}")
            params.append(is_active)
            param_num += 1

        if not updates:
            return False  # Nothing to update

        # Always update the updated_at timestamp
        updates.append("updated_at = NOW()")
        params.append(proxy_id)

        query = f"UPDATE proxy_endpoints SET {', '.join(updates)} WHERE id = ${param_num}"

        async with self.get_connection() as conn:
            try:
                result = await conn.execute(query, *params)
                updated = result != "UPDATE 0"

                if updated:
                    logger.info(f"Proxy {proxy_id} updated")
                result_bool: bool = updated
                return result_bool

            except Exception as e:
                if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
                    raise ValueError("Update violates uniqueness constraint")
                raise

    @require_connection
    async def delete_proxy(self, proxy_id: int) -> bool:
        """
        Delete a proxy endpoint.

        Args:
            proxy_id: Proxy ID

        Returns:
            True if deleted, False if not found
        """
        async with self.get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM proxy_endpoints WHERE id = $1",
                proxy_id,
            )
            deleted = result != "DELETE 0"

        if deleted:
            logger.info(f"Proxy {proxy_id} deleted")
        result_bool: bool = deleted
        return result_bool

    @require_connection
    async def mark_proxy_failed(self, proxy_id: int) -> bool:
        """
        Increment failure count for a proxy and update last_used.

        Args:
            proxy_id: Proxy ID

        Returns:
            True if updated, False if not found
        """
        async with self.get_connection() as conn:
            result = await conn.execute(
                """
                UPDATE proxy_endpoints
                SET failure_count = failure_count + 1,
                    last_used = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                """,
                proxy_id,
            )
            updated = result != "UPDATE 0"

        if updated:
            logger.debug(f"Proxy {proxy_id} marked as failed")
        result_bool: bool = updated
        return result_bool

    @require_connection
    async def reset_proxy_failures(self) -> int:
        """
        Reset failure count for all proxies.

        Returns:
            Number of proxies updated
        """
        async with self.get_connection() as conn:
            result = await conn.execute(
                """
                UPDATE proxy_endpoints
                SET failure_count = 0,
                    updated_at = NOW()
                WHERE failure_count > 0
                """
            )
            count = self._parse_command_tag(result)

        logger.info(f"Reset failure count for {count} proxies")
        result_count: int = count
        return result_count

    @require_connection
    async def get_proxy_stats(self) -> Dict[str, int]:
        """
        Get proxy statistics.

        Returns:
            Dictionary with total, active, inactive counts
        """
        async with self.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_active = true THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN is_active = false THEN 1 ELSE 0 END) as inactive
                FROM proxy_endpoints
                """
            )

            if row:
                return {
                    "total": row[0] or 0,
                    "active": row[1] or 0,
                    "inactive": row[2] or 0,
                }
            return {"total": 0, "active": 0, "inactive": 0}

    @require_connection
    async def clear_all_proxies(self) -> int:
        """
        Delete all proxy endpoints.

        Returns:
            Number of proxies deleted
        """
        async with self.get_connection() as conn:
            result = await conn.execute("DELETE FROM proxy_endpoints")
            count = self._parse_command_tag(result)

        logger.info(f"Cleared all {count} proxies")
        result_count: int = count
        return result_count

    @require_connection
    async def get_user_by_webhook_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get user information by webhook token.

        Args:
            token: Webhook token

        Returns:
            User data or None if not found
        """
        async with self.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT u.*
                FROM users u
                JOIN user_webhooks w ON u.id = w.user_id
                WHERE w.webhook_token = $1 AND w.is_active = true
                """,
                token,
            )
            return dict(row) if row else None
