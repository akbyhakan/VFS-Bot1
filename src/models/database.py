"""Database operations for VFS-Bot using SQLite."""

import aiosqlite
import logging
import os
from typing import Dict, List, Optional, Any, AsyncIterator, Callable, TypeVar, Awaitable
from contextlib import asynccontextmanager
from functools import wraps
import asyncio
from datetime import datetime, timezone

from src.utils.encryption import encrypt_password, decrypt_password
from src.utils.validators import validate_email, validate_phone
from src.core.exceptions import ValidationError
from src.constants import Defaults

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def require_connection(func: F) -> F:
    """
    Decorator to ensure database connection exists before method execution.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function that checks for connection

    Raises:
        RuntimeError: If database connection is not established
    """

    @wraps(func)
    async def wrapper(self: "Database", *args: Any, **kwargs: Any) -> Any:
        if self.conn is None:
            raise RuntimeError("Database connection is not established. " "Call connect() first.")
        return await func(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


class Database:
    """SQLite database manager for VFS-Bot with connection pooling."""

    def __init__(self, db_path: str = "vfs_bot.db", pool_size: Optional[int] = None):
        """
        Initialize database connection pool.

        Args:
            db_path: Path to SQLite database file
            pool_size: Maximum number of concurrent connections (defaults to DB_POOL_SIZE env var or Defaults.DB_POOL_SIZE)
        """
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None
        # Get pool size from parameter, env var, or default
        if pool_size is None:
            pool_size = int(os.getenv("DB_POOL_SIZE", str(Defaults.DB_POOL_SIZE)))
        self.pool_size = pool_size
        self._pool: List[aiosqlite.Connection] = []
        self._pool_lock = asyncio.Lock()
        self._available_connections: asyncio.Queue = asyncio.Queue(maxsize=pool_size)

    async def connect(self) -> None:
        """Establish database connection pool and create tables."""
        # Create main connection for schema management
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self._create_tables()

        # Initialize connection pool
        for _ in range(self.pool_size):
            conn = await aiosqlite.connect(self.db_path)
            conn.row_factory = aiosqlite.Row
            self._pool.append(conn)
            await self._available_connections.put(conn)

        logger.info(f"Database connected with pool size {self.pool_size}: {self.db_path}")

    async def close(self) -> None:
        """Close database connection pool."""
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

    @asynccontextmanager
    async def get_connection(self, timeout: float = 30.0) -> AsyncIterator[aiosqlite.Connection]:
        """
        Get a connection from the pool with timeout.

        Args:
            timeout: Maximum time to wait for a connection

        Yields:
            Database connection from pool

        Raises:
            RuntimeError: If connection cannot be acquired within timeout
        """
        try:
            conn = await asyncio.wait_for(self._available_connections.get(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"Database connection pool exhausted (timeout: {timeout}s)")
            raise RuntimeError(f"Database connection pool exhausted after {timeout}s")
        try:
            yield conn
        finally:
            await self._available_connections.put(conn)

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
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                async with self.get_connection(timeout=timeout) as conn:
                    yield conn
                    return
            except RuntimeError as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = (2**attempt) * 0.5  # Exponential backoff
                    logger.warning(
                        f"Connection pool exhausted, retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)

        raise last_error or RuntimeError("Failed to acquire database connection")

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
                    cvv_encrypted TEXT NOT NULL,
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
                    "UPDATE appointment_requests SET visa_subcategory = '' WHERE visa_subcategory IS NULL"
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
                    "UPDATE appointment_persons SET is_child_with_parent = 0 WHERE is_child_with_parent IS NULL"
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
        """
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
        """
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
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT * FROM personal_details WHERE user_id = ?", (user_id,))
                row = await cursor.fetchone()
                return dict(row) if row else None

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
    async def save_payment_card(self, card_data: Dict[str, str]) -> int:
        """
        Save or update payment card (only one card allowed).

        Args:
            card_data: Dictionary containing card_holder_name, card_number,
                      expiry_month, expiry_year, cvv

        Returns:
            Card ID

        Raises:
            ValueError: If card data is invalid
        """
        required_fields = ["card_holder_name", "card_number", "expiry_month", "expiry_year", "cvv"]
        for field in required_fields:
            if field not in card_data:
                raise ValueError(f"Missing required field: {field}")

        # Encrypt sensitive data
        card_number_encrypted = encrypt_password(card_data["card_number"])
        cvv_encrypted = encrypt_password(card_data["cvv"])

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
                            cvv_encrypted = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (
                            card_data["card_holder_name"],
                            card_number_encrypted,
                            card_data["expiry_month"],
                            card_data["expiry_year"],
                            cvv_encrypted,
                            existing["id"],
                        ),
                    )
                    await conn.commit()
                    logger.info("Payment card updated")
                    return existing["id"]
                else:
                    # Insert new card
                    await cursor.execute(
                        """
                        INSERT INTO payment_card 
                        (card_holder_name, card_number_encrypted, expiry_month, expiry_year, cvv_encrypted)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            card_data["card_holder_name"],
                            card_number_encrypted,
                            card_data["expiry_month"],
                            card_data["expiry_year"],
                            cvv_encrypted,
                        ),
                    )
                    await conn.commit()
                    card_id = cursor.lastrowid
                    logger.info(f"Payment card created with ID: {card_id}")
                    return card_id

    @require_connection
    async def get_payment_card(self) -> Optional[Dict[str, Any]]:
        """
        Get the saved payment card with decrypted data.

        Returns:
            Card dictionary with decrypted data or None if no card exists
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT * FROM payment_card LIMIT 1")
                row = await cursor.fetchone()

                if not row:
                    return None

                card = dict(row)

                # Decrypt sensitive data
                try:
                    card["card_number"] = decrypt_password(card["card_number_encrypted"])
                    card["cvv"] = decrypt_password(card["cvv_encrypted"])
                except Exception as e:
                    logger.error(f"Failed to decrypt card data: {e}")
                    raise ValueError("Failed to decrypt card data")

                # Remove encrypted fields from response
                del card["card_number_encrypted"]
                del card["cvv_encrypted"]

                return card

    @require_connection
    async def get_payment_card_masked(self) -> Optional[Dict[str, Any]]:
        """
        Get the saved payment card with masked card number (for frontend display).

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

                # Remove encrypted and sensitive fields
                del card["card_number_encrypted"]
                del card["cvv_encrypted"]

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
                    (country_code, visa_category, visa_subcategory, centres, preferred_dates, person_count)
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
                        "SELECT * FROM appointment_requests WHERE status = ? ORDER BY created_at DESC",
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
