"""Database operations for VFS-Bot using SQLite."""

import aiosqlite
import logging
import os
import secrets
import time
from typing import Dict, List, Optional, Any, AsyncIterator, Callable, TypeVar, Awaitable
from contextlib import asynccontextmanager
from functools import wraps
import asyncio
from datetime import datetime, timezone

from src.utils.encryption import encrypt_password, decrypt_password
from src.utils.validators import validate_email, validate_phone
from src.core.exceptions import (
    ValidationError,
    DatabaseNotConnectedError,
    DatabasePoolTimeoutError,
    BatchOperationError,
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
        if self.conn is None:
            raise DatabaseNotConnectedError()
        return await func(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


class Database:
    """SQLite database manager for VFS-Bot with connection pooling."""

    def __init__(self, db_path: str = "vfs_bot.db", pool_size: Optional[int] = None):
        """
        Initialize database connection pool.

        Args:
            db_path: Path to SQLite database file
            pool_size: Maximum number of concurrent connections (defaults to
                DB_POOL_SIZE env var or calculated optimal size)
        """
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None
        # Get pool size from parameter, env var, or calculate optimal size
        if pool_size is None:
            env_pool_size = os.getenv("DB_POOL_SIZE")
            if env_pool_size:
                pool_size = int(env_pool_size)
            else:
                pool_size = self._calculate_optimal_pool_size()
        self.pool_size = pool_size
        self._pool: List[aiosqlite.Connection] = []
        self._pool_lock = asyncio.Lock()
        self._available_connections: asyncio.Queue = asyncio.Queue(maxsize=pool_size)

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

    async def connect(self) -> None:
        """Establish database connection pool and create tables."""
        async with self._pool_lock:
            try:
                # Create main connection for schema management
                self.conn = await aiosqlite.connect(self.db_path)
                self.conn.row_factory = aiosqlite.Row

                # Enable WAL mode for better concurrency (database-wide setting)
                await self.conn.execute("PRAGMA journal_mode=WAL")
                # Add busy timeout for concurrent access
                await self.conn.execute("PRAGMA busy_timeout=30000")
                # Enable foreign keys
                await self.conn.execute("PRAGMA foreign_keys=ON")
                await self.conn.commit()

                await self._create_tables()

                # Initialize connection pool
                # Note: WAL mode is a database-wide setting that persists across connections
                for _ in range(self.pool_size):
                    conn = await aiosqlite.connect(self.db_path)
                    conn.row_factory = aiosqlite.Row

                    # Verify WAL mode is enabled for this connection
                    cursor = await conn.execute("PRAGMA journal_mode")
                    mode = await cursor.fetchone()
                    if mode and mode[0].lower() != "wal":
                        logger.warning(f"Connection not in WAL mode, enabling: {mode}")
                        await conn.execute("PRAGMA journal_mode=WAL")

                    # Add busy timeout for this connection
                    await conn.execute("PRAGMA busy_timeout=30000")

                    self._pool.append(conn)
                    await self._available_connections.put(conn)

                logger.info(
                    f"Database connected with pool size {self.pool_size} "
                    f"(WAL mode enabled): {self.db_path}"
                )
            except Exception:
                # Clean up partial connections on error
                if self.conn:
                    await self.conn.close()
                    self.conn = None
                for conn in self._pool:
                    await conn.close()
                self._pool.clear()
                # Clear the queue
                while not self._available_connections.empty():
                    try:
                        self._available_connections.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                raise

    async def close(self) -> None:
        """Close database connection pool."""
        async with self._pool_lock:
            # Close pooled connections
            for conn in self._pool:
                await conn.close()
            self._pool.clear()

            # Clear the queue
            while not self._available_connections.empty():
                try:
                    self._available_connections.get_nowait()
                except asyncio.QueueEmpty:
                    break

            # Close main connection
            if self.conn:
                await self.conn.close()
            logger.info("Database connection pool closed")

    async def cleanup_idle_connections(self, idle_timeout_seconds: int = 300) -> int:
        """Clean up idle connections from the pool."""
        async with self._pool_lock:
            now = time.time()
            cleaned = 0
            active_pool = []

            while not self._available_connections.empty():
                try:
                    conn = self._available_connections.get_nowait()
                    last_used = getattr(conn, "_last_used", now)

                    if now - last_used > idle_timeout_seconds:
                        await conn.close()
                        cleaned += 1
                    else:
                        active_pool.append(conn)
                except asyncio.QueueEmpty:
                    break

            for conn in active_pool:
                await self._available_connections.put(conn)

            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} idle database connections")

            return cleaned

    async def __aenter__(self) -> "Database":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    @asynccontextmanager
    async def get_connection(self, timeout: float = 30.0) -> AsyncIterator[aiosqlite.Connection]:
        """
        Get a connection from the pool with timeout.

        Args:
            timeout: Maximum time to wait for a connection

        Yields:
            Database connection from pool

        Raises:
            DatabasePoolTimeoutError: If connection cannot be acquired within timeout
        """
        conn = None
        try:
            conn = await asyncio.wait_for(self._available_connections.get(), timeout=timeout)
            yield conn
        except asyncio.TimeoutError:
            logger.error(
                f"Database connection pool exhausted "
                f"(timeout: {timeout}s, pool_size: {self.pool_size})"
            )
            raise DatabasePoolTimeoutError(timeout=timeout, pool_size=self.pool_size)
        finally:
            if conn is not None:
                try:
                    # Track when connection was last used for idle cleanup
                    conn._last_used = time.time()  # type: ignore
                    await self._available_connections.put(conn)
                except Exception as e:
                    logger.error(f"Failed to return connection to pool: {e}")

    @asynccontextmanager
    async def get_connection_with_retry(
        self, timeout: float = 30.0, max_retries: int = 3
    ) -> AsyncIterator[aiosqlite.Connection]:
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
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    result = await cursor.fetchone()
                    return result is not None
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        if self.conn is None:
            raise RuntimeError("Database connection is not established.")
        async with self.conn.cursor() as cursor:
            # Users table
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    centre TEXT NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT NOT NULL,
                    active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Personal details table
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS personal_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
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
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """
            )

            # Appointments table
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    centre TEXT NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT NOT NULL,
                    appointment_date TEXT,
                    appointment_time TEXT,
                    status TEXT DEFAULT 'pending',
                    reference_number TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """
            )

            # Logs table
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    user_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
                )
            """
            )

            # Payment card table (single card for all payments)
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_card (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_holder_name TEXT NOT NULL,
                    card_number_encrypted TEXT NOT NULL,
                    expiry_month TEXT NOT NULL,
                    expiry_year TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Appointment requests table
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS appointment_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    country_code TEXT NOT NULL,
                    visa_category TEXT NOT NULL,
                    visa_subcategory TEXT NOT NULL,
                    centres TEXT NOT NULL,
                    preferred_dates TEXT NOT NULL,
                    person_count INTEGER NOT NULL CHECK(person_count >= 1 AND person_count <= 6),
                    status TEXT DEFAULT 'pending',
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Appointment persons table
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS appointment_persons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
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
                    is_child_with_parent BOOLEAN NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES appointment_requests (id) ON DELETE CASCADE
                )
            """
            )

            # Audit log table
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    user_id INTEGER,
                    username TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    details TEXT,
                    timestamp TEXT NOT NULL,
                    success BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
                )
            """
            )

            # Audit log indexes
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)
            """
            )
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id)
            """
            )
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)
            """
            )

            # Appointment history table
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS appointment_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    centre TEXT NOT NULL,
                    mission TEXT NOT NULL,
                    category TEXT,
                    slot_date TEXT,
                    slot_time TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempt_count INTEGER DEFAULT 1,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """
            )

            # Index for faster queries
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_appointment_history_user_status
                ON appointment_history(user_id, status)
            """
            )

            # User webhooks table - per-user OTP webhook tokens
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_webhooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    webhook_token VARCHAR(64) UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """
            )

            # Index for faster webhook token lookups
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_user_webhooks_token
                ON user_webhooks(webhook_token)
            """
            )

            # Proxy endpoints table
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS proxy_endpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    password_encrypted TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    last_used TIMESTAMP,
                    failure_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(server, port, username)
                )
            """
            )

            # Index for active proxies lookup
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_proxy_endpoints_active
                ON proxy_endpoints(is_active)
            """
            )

            # Token blacklist table
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS token_blacklist (
                    jti VARCHAR(64) PRIMARY KEY,
                    exp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Index for cleanup
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_token_blacklist_exp
                ON token_blacklist(exp)
            """
            )

            await self.conn.commit()

            # Migration: Add new columns if they don't exist
            await self._migrate_schema()

            logger.info("Database tables created/verified")

    async def _migrate_schema(self) -> None:
        """Migrate database schema for new columns."""
        if self.conn is None:
            raise RuntimeError("Database connection is not established.")

        async with self.conn.cursor() as cursor:
            # Check if appointment_requests table has visa_category column
            await cursor.execute("PRAGMA table_info(appointment_requests)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            # Add visa_category if missing
            if "visa_category" not in column_names:
                logger.info("Adding visa_category column to appointment_requests")
                await cursor.execute(
                    "ALTER TABLE appointment_requests ADD COLUMN visa_category TEXT"
                )
                # Update existing records with a default value
                await cursor.execute(
                    "UPDATE appointment_requests SET visa_category = '' WHERE visa_category IS NULL"
                )

            # Add visa_subcategory if missing
            if "visa_subcategory" not in column_names:
                logger.info("Adding visa_subcategory column to appointment_requests")
                await cursor.execute(
                    "ALTER TABLE appointment_requests ADD COLUMN visa_subcategory TEXT"
                )
                # Update existing records with a default value
                await cursor.execute(
                    """UPDATE appointment_requests
                    SET visa_subcategory = ''
                    WHERE visa_subcategory IS NULL"""
                )

            # Check appointment_persons table
            await cursor.execute("PRAGMA table_info(appointment_persons)")
            person_columns = await cursor.fetchall()
            person_column_names = [col[1] for col in person_columns]

            # Add gender if missing
            if "gender" not in person_column_names:
                logger.info("Adding gender column to appointment_persons")
                await cursor.execute("ALTER TABLE appointment_persons ADD COLUMN gender TEXT")
                # Update existing records with default value
                await cursor.execute(
                    "UPDATE appointment_persons SET gender = 'male' WHERE gender IS NULL"
                )

            # Add is_child_with_parent if missing
            if "is_child_with_parent" not in person_column_names:
                logger.info("Adding is_child_with_parent column to appointment_persons")
                await cursor.execute(
                    "ALTER TABLE appointment_persons ADD COLUMN is_child_with_parent BOOLEAN"
                )
                # Update existing records with default value
                await cursor.execute(
                    """UPDATE appointment_persons
                    SET is_child_with_parent = 0
                    WHERE is_child_with_parent IS NULL"""
                )

            await self.conn.commit()
            logger.info("Schema migration completed")

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
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO users (email, password, centre, category, subcategory)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (email, encrypted_password, centre, category, subcategory),
                )
                await conn.commit()
                logger.info(f"User added: {email}")
                last_id = cursor.lastrowid
                if last_id is None:
                    raise RuntimeError("Failed to fetch lastrowid after insert")
                return int(last_id)

    @require_connection
    async def get_active_users(self) -> List[Dict[str, Any]]:
        """
        Get all active users.

        Returns:
            List of user dictionaries
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT * FROM users WHERE active = 1")
                rows = await cursor.fetchall()
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
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                row = await cursor.fetchone()
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
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT * FROM users WHERE active = 1")
                rows = await cursor.fetchall()
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

        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO personal_details
                    (user_id, first_name, last_name, passport_number, passport_expiry,
                     gender, mobile_code, mobile_number, email, nationality, date_of_birth,
                     address_line1, address_line2, state, city, postcode)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        user_id,
                        details.get("first_name"),
                        details.get("last_name"),
                        details.get("passport_number"),
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
                    ),
                )
                await conn.commit()
                logger.info(f"Personal details added for user {user_id}")
                last_id = cursor.lastrowid
                if last_id is None:
                    raise RuntimeError("Failed to fetch lastrowid after insert")
                return int(last_id)

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
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT * FROM personal_details WHERE user_id = ?", (user_id,))
                row = await cursor.fetchone()
                return dict(row) if row else None

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

        # Build SQL query with parameterized placeholders
        # SQL Injection Safety: This is safe because:
        # 1. user_ids are validated as positive integers above (no SQL can be injected)
        # 2. placeholders contains only "?" characters (no dynamic SQL)
        # 3. SQLite uses parameter binding - values never enter the SQL string
        # 4. Alternative would be to use: "... WHERE user_id IN (SELECT value FROM json_each(?))"
        #    but that's less readable and not significantly safer
        num_placeholders = len(user_ids)
        placeholders = ",".join(["?"] * num_placeholders)
        query = f"SELECT * FROM personal_details WHERE user_id IN ({placeholders})"

        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, user_ids)
                rows = await cursor.fetchall()

                # Map results by user_id
                result = {}
                for row in rows:
                    details = dict(row)
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
            async with conn.cursor() as cursor:
                await cursor.execute(
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
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

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
        Update user information.

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
        updates = []
        params = []

        if email is not None:
            updates.append("email = ?")
            params.append(email)
        if password is not None:
            # Encrypt password before storage
            encrypted_password = encrypt_password(password)
            updates.append("password = ?")
            params.append(encrypted_password)
        if centre is not None:
            updates.append("centre = ?")
            params.append(centre)
        if category is not None:
            updates.append("category = ?")
            params.append(category)
        if subcategory is not None:
            updates.append("subcategory = ?")
            params.append(subcategory)
        if active is not None:
            updates.append("active = ?")
            params.append(1 if active else 0)

        if not updates:
            return True  # Nothing to update

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(user_id)

        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
                await cursor.execute(query, params)
                await conn.commit()

                if cursor.rowcount == 0:
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
        updates = []
        params = []

        if first_name is not None:
            updates.append("first_name = ?")
            params.append(first_name)
        if last_name is not None:
            updates.append("last_name = ?")
            params.append(last_name)
        if mobile_number is not None:
            updates.append("mobile_number = ?")
            params.append(mobile_number)

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
            updates.append(f"{field} = ?")
            params.append(value)

        if not updates:
            return True  # Nothing to update (success case)

        # Add updated_at timestamp and user_id
        updates.append("updated_at = ?")
        params.append(datetime.now(timezone.utc))
        params.append(user_id)

        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                query = f"UPDATE personal_details SET {', '.join(updates)} WHERE user_id = ?"
                await cursor.execute(query, params)
                await conn.commit()

                if cursor.rowcount == 0:
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
            async with conn.cursor() as cursor:
                await cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                await conn.commit()

                if cursor.rowcount == 0:
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
                async with conn.cursor() as cursor:
                    # Use executemany for efficiency
                    user_data = []
                    for user in users:
                        # Encrypt password before storing
                        encrypted_password = encrypt_password(user["password"])
                        user_data.append(
                            (
                                user["email"],
                                encrypted_password,
                                user["centre"],
                                user["category"],
                                user["subcategory"],
                            )
                        )

                    # Insert all users in a single transaction
                    await cursor.executemany(
                        """
                        INSERT INTO users (email, password, centre, category, subcategory)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        user_data,
                    )

                    await conn.commit()

                    # Get all inserted IDs
                    # Note: SQLite doesn't support RETURNING, so we query by email
                    for user in users:
                        await cursor.execute(
                            "SELECT id FROM users WHERE email = ? ORDER BY id DESC LIMIT 1",
                            (user["email"],),
                        )
                        row = await cursor.fetchone()
                        if row:
                            user_ids.append(row[0])

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

        Args:
            updates: List of update dictionaries with 'id' and optional fields:
                    email, password, centre, category, subcategory, active

        Returns:
            Number of users successfully updated

        Raises:
            ValidationError: If any email format is invalid
            BatchOperationError: If batch operation fails
        """
        if not updates:
            return 0

        # Validate all emails first (fail fast)
        for update in updates:
            email = update.get("email")
            if email and not validate_email(email):
                raise ValidationError(f"Invalid email format: {email}", field="email")

        updated_count = 0

        async with self.get_connection() as conn:
            try:
                async with conn.cursor() as cursor:
                    # Process each update individually but within a single transaction
                    for update in updates:
                        user_id = update.get("id")
                        if not user_id:
                            logger.warning("Skipping update without user_id")
                            continue

                        # Build dynamic update query
                        fields = []
                        params = []

                        if "email" in update:
                            fields.append("email = ?")
                            params.append(update["email"])
                        if "password" in update:
                            # Encrypt password before storage
                            encrypted_password = encrypt_password(update["password"])
                            fields.append("password = ?")
                            params.append(encrypted_password)
                        if "centre" in update:
                            fields.append("centre = ?")
                            params.append(update["centre"])
                        if "category" in update:
                            fields.append("category = ?")
                            params.append(update["category"])
                        if "subcategory" in update:
                            fields.append("subcategory = ?")
                            params.append(update["subcategory"])
                        if "active" in update:
                            fields.append("active = ?")
                            params.append(1 if update["active"] else 0)

                        if not fields:
                            continue

                        fields.append("updated_at = CURRENT_TIMESTAMP")
                        params.append(user_id)

                        query = f"UPDATE users SET {', '.join(fields)} WHERE id = ?"
                        await cursor.execute(query, params)

                        if cursor.rowcount > 0:
                            updated_count += 1

                    await conn.commit()
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
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO appointments
                    (user_id, centre, category, subcategory, appointment_date,
                     appointment_time, reference_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (user_id, centre, category, subcategory, date, time, reference),
                )
                await conn.commit()
                logger.info(f"Appointment added for user {user_id}")
                last_id = cursor.lastrowid
                if last_id is None:
                    raise RuntimeError("Failed to fetch lastrowid after insert")
                return int(last_id)

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
            async with conn.cursor() as cursor:
                if user_id:
                    await cursor.execute("SELECT * FROM appointments WHERE user_id = ?", (user_id,))
                else:
                    await cursor.execute("SELECT * FROM appointments")
                rows = await cursor.fetchall()
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
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO logs (level, message, user_id)
                    VALUES (?, ?, ?)
                """,
                    (level, message, user_id),
                )
                await conn.commit()

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
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT * FROM logs ORDER BY created_at DESC LIMIT ?", (limit,)
                )
                rows = await cursor.fetchall()
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
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT OR REPLACE INTO token_blacklist (jti, exp)
                    VALUES (?, ?)
                    """,
                    (jti, exp.isoformat()),
                )
                await conn.commit()

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
            async with conn.cursor() as cursor:
                now = datetime.now(timezone.utc).isoformat()
                await cursor.execute(
                    """
                    SELECT 1 FROM token_blacklist
                    WHERE jti = ? AND exp > ?
                    """,
                    (jti, now),
                )
                result = await cursor.fetchone()
                return result is not None

    @require_connection
    async def get_active_blacklisted_tokens(self) -> List[tuple[str, datetime]]:
        """
        Get all active (non-expired) blacklisted tokens.

        Returns:
            List of (jti, exp) tuples
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                now = datetime.now(timezone.utc).isoformat()
                await cursor.execute(
                    """
                    SELECT jti, exp FROM token_blacklist
                    WHERE exp > ?
                    """,
                    (now,),
                )
                rows = await cursor.fetchall()
                return [(row[0], datetime.fromisoformat(row[1])) for row in rows]

    @require_connection
    async def cleanup_expired_tokens(self) -> int:
        """
        Remove expired tokens from blacklist.

        Returns:
            Number of tokens removed
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                now = datetime.now(timezone.utc).isoformat()
                await cursor.execute(
                    """
                    DELETE FROM token_blacklist
                    WHERE exp <= ?
                    """,
                    (now,),
                )
                await conn.commit()
                return cursor.rowcount

    @require_connection
    async def save_payment_card(self, card_data: Dict[str, str]) -> int:
        """
        Save or update payment card - PCI-DSS compliant (CVV NOT stored).

        IMPORTANT: CVV is NOT stored per PCI-DSS requirements.
        CVV must be re-entered for each payment transaction.

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

        # Encrypt sensitive data (card number only - CVV is NEVER stored)
        card_number_encrypted = encrypt_password(card_data["card_number"])

        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                # Check if a card already exists
                await cursor.execute("SELECT id FROM payment_card LIMIT 1")
                existing = await cursor.fetchone()

                if existing:
                    # Update existing card
                    await cursor.execute(
                        """
                        UPDATE payment_card
                        SET card_holder_name = ?,
                            card_number_encrypted = ?,
                            expiry_month = ?,
                            expiry_year = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (
                            card_data["card_holder_name"],
                            card_number_encrypted,
                            card_data["expiry_month"],
                            card_data["expiry_year"],
                            existing["id"],
                        ),
                    )
                    await conn.commit()
                    logger.info("Payment card updated")
                    return int(existing["id"])
                else:
                    # Insert new card
                    await cursor.execute(
                        """
                        INSERT INTO payment_card
                        (card_holder_name, card_number_encrypted, expiry_month,
                         expiry_year)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            card_data["card_holder_name"],
                            card_number_encrypted,
                            card_data["expiry_month"],
                            card_data["expiry_year"],
                        ),
                    )
                    await conn.commit()
                    card_id = cursor.lastrowid
                    if card_id is None:
                        raise RuntimeError("Failed to get inserted card ID")
                    logger.info(f"Payment card created with ID: {card_id}")
                    return card_id

    @require_connection
    async def get_payment_card(self) -> Optional[Dict[str, Any]]:
        """
        Get the saved payment card with decrypted card number.

        IMPORTANT: CVV is NOT returned (PCI-DSS compliant).
        CVV must be requested separately for each transaction.

        Returns:
            Card dictionary with decrypted card number or None if no card exists
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT * FROM payment_card LIMIT 1")
                row = await cursor.fetchone()

                if not row:
                    return None

                card = dict(row)

                # Decrypt card number
                try:
                    card["card_number"] = decrypt_password(card["card_number_encrypted"])
                except Exception as e:
                    logger.error(f"Failed to decrypt card data: {e}")
                    raise ValueError("Failed to decrypt card data")

                # Remove encrypted field from response
                del card["card_number_encrypted"]

                return card

    @require_connection
    async def get_payment_card_masked(self) -> Optional[Dict[str, Any]]:
        """
        Get the saved payment card with masked card number (for frontend display).

        IMPORTANT: CVV is NOT returned (PCI-DSS compliant).

        Returns:
            Card dictionary with masked card number or None if no card exists
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT * FROM payment_card LIMIT 1")
                row = await cursor.fetchone()

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

                # Remove encrypted field
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
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT id FROM payment_card LIMIT 1")
                existing = await cursor.fetchone()

                if not existing:
                    return False

                await cursor.execute("DELETE FROM payment_card WHERE id = ?", (existing["id"],))
                await conn.commit()
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
            async with conn.cursor() as cursor:
                # Insert appointment request
                await cursor.execute(
                    """
                    INSERT INTO appointment_requests
                    (country_code, visa_category, visa_subcategory, centres,
                     preferred_dates, person_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        country_code,
                        visa_category,
                        visa_subcategory,
                        json.dumps(centres),
                        json.dumps(preferred_dates),
                        person_count,
                    ),
                )
                request_id = cursor.lastrowid
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

                    await cursor.execute(
                        """
                        INSERT INTO appointment_persons
                        (request_id, first_name, last_name, gender, nationality, birth_date,
                         passport_number, passport_issue_date, passport_expiry_date,
                         phone_code, phone_number, email, is_child_with_parent)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
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
                        ),
                    )

                await conn.commit()
                logger.info(f"Appointment request created: {request_id}")
                return request_id

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
            async with conn.cursor() as cursor:
                # Get request
                await cursor.execute(
                    "SELECT * FROM appointment_requests WHERE id = ?", (request_id,)
                )
                request_row = await cursor.fetchone()

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
                await cursor.execute(
                    "SELECT * FROM appointment_persons WHERE request_id = ?", (request_id,)
                )
                person_rows = await cursor.fetchall()
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
            async with conn.cursor() as cursor:
                if status:
                    await cursor.execute(
                        """SELECT * FROM appointment_requests
                        WHERE status = ? ORDER BY created_at DESC""",
                        (status,),
                    )
                else:
                    await cursor.execute(
                        "SELECT * FROM appointment_requests ORDER BY created_at DESC"
                    )

                request_rows = await cursor.fetchall()
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
                    await cursor.execute(
                        "SELECT * FROM appointment_persons WHERE request_id = ?", (request["id"],)
                    )
                    person_rows = await cursor.fetchall()
                    request["persons"] = [dict(row) for row in person_rows]

                    requests.append(request)

                return requests

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
            async with conn.cursor() as cursor:
                if completed_at:
                    await cursor.execute(
                        """
                        UPDATE appointment_requests
                        SET status = ?, completed_at = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (status, completed_at, request_id),
                    )
                else:
                    await cursor.execute(
                        """
                        UPDATE appointment_requests
                        SET status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (status, request_id),
                    )

                await conn.commit()

                if cursor.rowcount > 0:
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
            async with conn.cursor() as cursor:
                await cursor.execute("DELETE FROM appointment_requests WHERE id = ?", (request_id,))
                await conn.commit()

                if cursor.rowcount > 0:
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
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    DELETE FROM appointment_requests
                    WHERE status = 'completed' AND completed_at < ?
                    """,
                    (cutoff_date,),
                )
                await conn.commit()
                deleted_count = cursor.rowcount

                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} old appointment requests")

                return deleted_count

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
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO audit_log
                    (action, user_id, username, ip_address, user_agent, details, timestamp, success)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        action,
                        user_id,
                        username,
                        ip_address,
                        user_agent,
                        details,
                        timestamp,
                        1 if success else 0,
                    ),
                )
                await conn.commit()
                last_id = cursor.lastrowid
                if last_id is None:
                    raise RuntimeError("Failed to fetch lastrowid after insert")
                logger.debug(f"Audit log entry added: {action}")
                return int(last_id)

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
            async with conn.cursor() as cursor:
                query = "SELECT * FROM audit_log WHERE 1=1"
                params: List[Any] = []

                if action:
                    query += " AND action = ?"
                    params.append(action)
                if user_id is not None:
                    query += " AND user_id = ?"
                    params.append(user_id)

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                await cursor.execute(query, params)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    @require_connection
    async def add_appointment_history(
        self,
        user_id: int,
        centre: str,
        mission: str,
        status: str,
        category: str = None,
        slot_date: str = None,
        slot_time: str = None,
        error_message: str = None,
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
            cursor = await conn.execute(
                """
                INSERT INTO appointment_history
                (user_id, centre, mission, category, slot_date, slot_time, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, centre, mission, category, slot_date, slot_time, status, error_message),
            )
            await conn.commit()
            return cursor.lastrowid

    @require_connection
    async def get_appointment_history(
        self, user_id: int, limit: int = 50, status: str = None
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
        query = "SELECT * FROM appointment_history WHERE user_id = ?"
        params = [user_id]

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with self.get_connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    @require_connection
    async def update_appointment_status(
        self, history_id: int, status: str, error_message: str = None
    ) -> bool:
        """Update appointment history status."""
        async with self.get_connection() as conn:
            await conn.execute(
                """
                UPDATE appointment_history
                SET status = ?, error_message = ?, updated_at = ?, attempt_count = attempt_count + 1
                WHERE id = ?
                """,
                (status, error_message, datetime.now(timezone.utc), history_id),
            )
            await conn.commit()
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
                VALUES (?, ?, 1)
                """,
                (user_id, token),
            )
            await conn.commit()

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
            cursor = await conn.execute(
                """
                SELECT * FROM user_webhooks WHERE user_id = ?
                """,
                (user_id,),
            )
            row = await cursor.fetchone()
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
            cursor = await conn.execute(
                """
                DELETE FROM user_webhooks WHERE user_id = ?
                """,
                (user_id,),
            )
            await conn.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Webhook deleted for user {user_id}")
        return deleted

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
                cursor = await conn.execute(
                    """
                    INSERT INTO proxy_endpoints
                    (server, port, username, password_encrypted, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (server, port, username, encrypted_password),
                )
                await conn.commit()
                proxy_id = cursor.lastrowid

                logger.info(f"Proxy added: {server}:{port} (ID: {proxy_id})")
                return proxy_id

            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    raise ValueError(
                        f"Proxy with server={server}, port={port}, username={username} already exists"
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
            cursor = await conn.execute(
                """
                SELECT id, server, port, username, password_encrypted, is_active,
                       last_used, failure_count, created_at, updated_at
                FROM proxy_endpoints
                WHERE is_active = 1
                ORDER BY failure_count ASC, last_used ASC NULLS FIRST
                """
            )
            rows = await cursor.fetchall()

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
            cursor = await conn.execute(
                """
                SELECT id, server, port, username, password_encrypted, is_active,
                       last_used, failure_count, created_at, updated_at
                FROM proxy_endpoints
                WHERE id = ?
                """,
                (proxy_id,),
            )
            row = await cursor.fetchone()

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
        updates = []
        params = []

        if server is not None:
            updates.append("server = ?")
            params.append(server)

        if port is not None:
            updates.append("port = ?")
            params.append(port)

        if username is not None:
            updates.append("username = ?")
            params.append(username)

        if password is not None:
            updates.append("password_encrypted = ?")
            params.append(encrypt_password(password))

        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)

        if not updates:
            return False  # Nothing to update

        # Always update the updated_at timestamp
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(proxy_id)

        query = f"UPDATE proxy_endpoints SET {', '.join(updates)} WHERE id = ?"

        async with self.get_connection() as conn:
            try:
                cursor = await conn.execute(query, params)
                await conn.commit()
                updated = cursor.rowcount > 0

                if updated:
                    logger.info(f"Proxy {proxy_id} updated")
                return updated

            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
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
            cursor = await conn.execute(
                "DELETE FROM proxy_endpoints WHERE id = ?",
                (proxy_id,),
            )
            await conn.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Proxy {proxy_id} deleted")
        return deleted

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
            cursor = await conn.execute(
                """
                UPDATE proxy_endpoints
                SET failure_count = failure_count + 1,
                    last_used = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (proxy_id,),
            )
            await conn.commit()
            updated = cursor.rowcount > 0

        if updated:
            logger.debug(f"Proxy {proxy_id} marked as failed")
        return updated

    @require_connection
    async def reset_proxy_failures(self) -> int:
        """
        Reset failure count for all proxies.

        Returns:
            Number of proxies updated
        """
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                """
                UPDATE proxy_endpoints
                SET failure_count = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE failure_count > 0
                """
            )
            await conn.commit()
            count = cursor.rowcount

        logger.info(f"Reset failure count for {count} proxies")
        return count

    @require_connection
    async def get_proxy_stats(self) -> Dict[str, int]:
        """
        Get proxy statistics.

        Returns:
            Dictionary with total, active, inactive counts
        """
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) as inactive
                FROM proxy_endpoints
                """
            )
            row = await cursor.fetchone()

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
            cursor = await conn.execute("DELETE FROM proxy_endpoints")
            await conn.commit()
            count = cursor.rowcount

        logger.info(f"Cleared all {count} proxies")
        return count

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
            cursor = await conn.execute(
                """
                SELECT u.*
                FROM users u
                JOIN user_webhooks w ON u.id = w.user_id
                WHERE w.webhook_token = ? AND w.is_active = 1
                """,
                (token,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
