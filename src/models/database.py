from typing import Optional, AsyncIterator
import aiosqlite
import os
from datetime import datetime

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/vfs_bot.db")


async def init_database():
    """Initialize the database and create tables if they don't exist."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                appointment_date DATE NOT NULL,
                appointment_time TIME,
                location TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                notify_enabled BOOLEAN DEFAULT 1,
                language TEXT DEFAULT 'en',
                timezone TEXT DEFAULT 'UTC',
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        await db.commit()


async def get_connection() -> AsyncIterator[aiosqlite.Connection]:
    """Get a database connection as an async context manager."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        yield db


async def get_user_by_telegram_id(telegram_id: int) -> Optional[dict]:
    """Get a user by their Telegram ID."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_user(telegram_id: int, username: str = None, 
                      first_name: str = None, last_name: str = None) -> int:
    """Create a new user and return their ID."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO users (telegram_id, username, first_name, last_name)
               VALUES (?, ?, ?, ?)""",
            (telegram_id, username, first_name, last_name)
        )
        await db.commit()
        return cursor.lastrowid


async def update_user(telegram_id: int, **kwargs) -> bool:
    """Update user information."""
    if not kwargs:
        return False
    
    set_clause = ", ".join(f"{key} = ?" for key in kwargs.keys())
    values = list(kwargs.values()) + [telegram_id]
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE users SET {set_clause} WHERE telegram_id = ?",
            values
        )
        await db.commit()
        return True


async def create_appointment(user_id: int, appointment_date: str,
                            appointment_time: str = None, 
                            location: str = None) -> int:
    """Create a new appointment."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO appointments (user_id, appointment_date, appointment_time, location)
               VALUES (?, ?, ?, ?)""",
            (user_id, appointment_date, appointment_time, location)
        )
        await db.commit()
        return cursor.lastrowid


async def get_user_appointments(user_id: int) -> list:
    """Get all appointments for a user."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM appointments WHERE user_id = ? ORDER BY appointment_date",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_appointment_status(appointment_id: int, status: str) -> bool:
    """Update the status of an appointment."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE appointments SET status = ? WHERE id = ?",
            (status, appointment_id)
        )
        await db.commit()
        return True


async def get_user_settings(user_id: int) -> Optional[dict]:
    """Get settings for a user."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM settings WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_or_update_settings(user_id: int, **kwargs) -> bool:
    """Create or update user settings."""
    existing = await get_user_settings(user_id)
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if existing:
            if kwargs:
                set_clause = ", ".join(f"{key} = ?" for key in kwargs.keys())
                values = list(kwargs.values()) + [user_id]
                await db.execute(
                    f"UPDATE settings SET {set_clause} WHERE user_id = ?",
                    values
                )
        else:
            columns = ["user_id"] + list(kwargs.keys())
            placeholders = ", ".join("?" * len(columns))
            values = [user_id] + list(kwargs.values())
            await db.execute(
                f"INSERT INTO settings ({', '.join(columns)}) VALUES ({placeholders})",
                values
            )
        await db.commit()
        return True
