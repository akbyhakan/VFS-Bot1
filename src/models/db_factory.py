"""Database factory with singleton pattern for connection management."""

import asyncio
import threading
from typing import Optional

from loguru import logger

from src.models.database import Database


class DatabaseFactory:
    """
    Singleton factory for database connections.

    Ensures only one database instance exists throughout the application lifecycle.
    Thread-safe singleton implementation with async lock for async operations.

    Example:
        ```python
        # Get database instance
        db = DatabaseFactory.get_instance()
        await db.connect()

        # Use in different modules
        db = DatabaseFactory.get_instance()  # Same instance
        ```
    """

    _instance: Optional[Database] = None
    _async_lock: Optional[asyncio.Lock] = None
    _class_lock = threading.Lock()  # Thread-safe guard for async lock creation

    @classmethod
    def _get_async_lock(cls) -> asyncio.Lock:
        """Get or create the async lock (lazy initialization for event loop safety)."""
        with cls._class_lock:
            if cls._async_lock is None:
                cls._async_lock = asyncio.Lock()
        return cls._async_lock

    @classmethod
    def get_instance(
        cls,
        database_url: Optional[str] = None,
        pool_size: Optional[int] = None,
    ) -> Database:
        """
        Get database singleton instance.

        Args:
            database_url: PostgreSQL connection URL (only used on first call)
            pool_size: Connection pool size (only used on first call)

        Returns:
            Database singleton instance
        """
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = Database(database_url=database_url, pool_size=pool_size)
                logger.info("Created new database singleton instance")
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset singleton instance (useful for testing).

        Warning: This will NOT close the existing connection.
        Call close() on the instance before resetting.
        """
        cls._instance = None
        with cls._class_lock:
            cls._async_lock = None  # Reset lock too
        logger.info("Reset database singleton instance")

    @classmethod
    async def ensure_connected(cls) -> Database:
        """
        Get database instance and ensure it's connected.

        Returns:
            Connected database instance
        """
        async with cls._get_async_lock():
            db = cls.get_instance()
            if db.pool is None:
                await db.connect()
                logger.info("Database connection established")
            return db

    @classmethod
    async def close_instance(cls) -> None:
        """
        Close database singleton instance.

        This should be called during application shutdown.
        """
        async with cls._get_async_lock():
            if cls._instance is not None:
                instance_to_close = cls._instance
                cls._instance = None
                await instance_to_close.close()
                logger.info("Closed and reset database singleton instance")
