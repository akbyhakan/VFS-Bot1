"""Database operations for VFS-Bot using SQLite."""

import aiosqlite
import logging
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
import asyncio

from src.utils.encryption import encrypt_password, decrypt_password

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager for VFS-Bot with connection pooling."""

    def __init__(self, db_path: str = "vfs_bot.db", pool_size: int = 5):
        """
        Initialize database connection pool.

        Args:
            db_path: Path to SQLite database file
            pool_size: Maximum number of concurrent connections
        """
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None
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
    async def get_connection(self):
        """
        Get a connection from the pool.

        Yields:
            Database connection from pool
        """
        conn = await self._available_connections.get()
        try:
            yield conn
        finally:
            await self._available_connections.put(conn)

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

            await self.conn.commit()
            logger.info("Database tables created/verified")

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
        """
        if self.conn is None:
            raise RuntimeError("Database connection is not established.")

        # Encrypt password before storing (NOT hashing - we need plaintext for VFS login)
        encrypted_password = encrypt_password(password)

        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO users (email, password, centre, category, subcategory)
                VALUES (?, ?, ?, ?, ?)
            """,
                (email, encrypted_password, centre, category, subcategory),
            )
            await self.conn.commit()
            logger.info(f"User added: {email}")
            last_id = cursor.lastrowid
            if last_id is None:
                raise RuntimeError("Failed to fetch lastrowid after insert")
            return int(last_id)

    async def get_active_users(self) -> List[Dict[str, Any]]:
        """
        Get all active users.

        Returns:
            List of user dictionaries
        """
        if self.conn is None:
            raise RuntimeError("Database connection is not established.")
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT * FROM users WHERE active = 1")
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_user_with_decrypted_password(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user with decrypted password for VFS login.

        Args:
            user_id: User ID

        Returns:
            User dictionary with decrypted password or None
        """
        if self.conn is None:
            raise RuntimeError("Database connection is not established.")
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

    async def get_active_users_with_decrypted_passwords(self) -> List[Dict[str, Any]]:
        """
        Get all active users with decrypted passwords for VFS login.

        Returns:
            List of user dictionaries with decrypted passwords
        """
        if self.conn is None:
            raise RuntimeError("Database connection is not established.")
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

    async def add_personal_details(self, user_id: int, details: Dict[str, Any]) -> int:
        """
        Add personal details for a user.

        Args:
            user_id: User ID
            details: Personal details dictionary

        Returns:
            Personal details ID
        """
        if self.conn is None:
            raise RuntimeError("Database connection is not established.")
        async with self.conn.cursor() as cursor:
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
            await self.conn.commit()
            logger.info(f"Personal details added for user {user_id}")
            last_id = cursor.lastrowid
            if last_id is None:
                raise RuntimeError("Failed to fetch lastrowid after insert")
            return int(last_id)

    async def get_personal_details(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get personal details for a user.

        Args:
            user_id: User ID

        Returns:
            Personal details dictionary or None
        """
        if self.conn is None:
            raise RuntimeError("Database connection is not established.")
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM personal_details WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

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
        if self.conn is None:
            raise RuntimeError("Database connection is not established.")
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO appointments
                (user_id, centre, category, subcategory, appointment_date,
                 appointment_time, reference_number)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (user_id, centre, category, subcategory, date, time, reference),
            )
            await self.conn.commit()
            logger.info(f"Appointment added for user {user_id}")
            last_id = cursor.lastrowid
            if last_id is None:
                raise RuntimeError("Failed to fetch lastrowid after insert")
            return int(last_id)

    async def get_appointments(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get appointments, optionally filtered by user.

        Args:
            user_id: Optional user ID filter

        Returns:
            List of appointment dictionaries
        """
        if self.conn is None:
            raise RuntimeError("Database connection is not established.")
        async with self.conn.cursor() as cursor:
            if user_id:
                await cursor.execute("SELECT * FROM appointments WHERE user_id = ?", (user_id,))
            else:
                await cursor.execute("SELECT * FROM appointments")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def add_log(self, level: str, message: str, user_id: Optional[int] = None) -> None:
        """
        Add a log entry.

        Args:
            level: Log level (INFO, WARNING, ERROR)
            message: Log message
            user_id: Optional user ID
        """
        if self.conn is None:
            raise RuntimeError("Database connection is not established.")
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO logs (level, message, user_id)
                VALUES (?, ?, ?)
            """,
                (level, message, user_id),
            )
            await self.conn.commit()

    async def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent log entries.

        Args:
            limit: Maximum number of logs to retrieve

        Returns:
            List of log dictionaries
        """
        if self.conn is None:
            raise RuntimeError("Database connection is not established.")
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM logs ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
