"""Database factory with singleton pattern for connection management."""

import logging
from threading import RLock
from typing import Optional

from src.models.database import Database

logger = logging.getLogger(__name__)


class DatabaseFactory:
    """
    Singleton factory for database connections.

    Ensures only one database instance exists throughout the application lifecycle.
    Thread-safe singleton implementation.

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
    _lock = RLock()

    @classmethod
    def get_instance(
        cls,
        db_path: Optional[str] = None,
        pool_size: Optional[int] = None,
    ) -> Database:
        """
        Get database singleton instance.

        Args:
            db_path: Path to database file (only used on first call)
            pool_size: Connection pool size (only used on first call)

        Returns:
            Database singleton instance
        """
        with cls._lock:
            if cls._instance is None:
                # Ensure db_path is not None when creating Database instance
                path = db_path if db_path is not None else "vfs_bot.db"
                cls._instance = Database(db_path=path, pool_size=pool_size)
                logger.info("Created new database singleton instance")
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset singleton instance (useful for testing).

        Warning: This will NOT close the existing connection.
        Call close() on the instance before resetting.
        """
        with cls._lock:
            cls._instance = None
            logger.info("Reset database singleton instance")

    @classmethod
    async def ensure_connected(cls) -> Database:
        """
        Get database instance and ensure it's connected.

        Returns:
            Connected database instance
        """
        db = cls.get_instance()
        if db.conn is None:
            await db.connect()
            logger.info("Database connection established")
        return db

    @classmethod
    async def close_instance(cls) -> None:
        """
        Close database singleton instance.

        This should be called during application shutdown.
        """
        with cls._lock:
            if cls._instance is not None:
                await cls._instance.close()
                cls._instance = None
                logger.info("Closed and reset database singleton instance")
