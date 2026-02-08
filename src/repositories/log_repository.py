"""Log repository implementation."""

import logging
from typing import Any, Dict, List, Optional

from src.core.enums import LogLevel
from src.models.database import Database
from src.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class LogEntry:
    """Log entry entity model."""

    def __init__(
        self,
        id: int,
        level: str,
        message: str,
        user_id: Optional[int] = None,
        created_at: Optional[str] = None,
    ):
        """Initialize log entry entity."""
        self.id = id
        self.level = level
        self.message = message
        self.user_id = user_id
        self.created_at = created_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to dictionary."""
        return {
            "id": self.id,
            "level": self.level,
            "message": self.message,
            "user_id": self.user_id,
            "created_at": self.created_at,
        }


class LogRepository(BaseRepository[LogEntry]):
    """Repository for log CRUD operations."""

    def __init__(self, database: Database):
        """
        Initialize log repository.

        Args:
            database: Database instance
        """
        super().__init__(database)

    def _row_to_log_entry(self, row: Any) -> LogEntry:
        """
        Convert database row to LogEntry entity.

        Args:
            row: Database row

        Returns:
            LogEntry entity
        """
        return LogEntry(
            id=row["id"],
            level=row["level"],
            message=row["message"],
            user_id=row.get("user_id"),
            created_at=row.get("created_at"),
        )

    async def get_by_id(self, id: int) -> Optional[LogEntry]:
        """
        Get log entry by ID.

        Args:
            id: Log entry ID

        Returns:
            LogEntry entity or None if not found
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM logs WHERE id = $1",
                id,
            )

            if row is None:
                return None

            return self._row_to_log_entry(row)

    async def get_all(self, limit: int = 100) -> List[LogEntry]:
        """
        Get all log entries (delegates to Database.get_logs).

        Args:
            limit: Maximum number of logs to return

        Returns:
            List of log entry entities
        """
        log_dicts = await self.db.get_logs(limit=limit)
        return [
            LogEntry(
                id=log["id"],
                level=log["level"],
                message=log["message"],
                user_id=log.get("user_id"),
                created_at=log.get("created_at"),
            )
            for log in log_dicts
        ]

    async def create(self, data: Dict[str, Any]) -> int:
        """
        Create new log entry (delegates to Database.add_log).

        Args:
            data: Log entry data (level, message, user_id)

        Returns:
            Created log entry ID (returns 0 as Database.add_log returns None)
        """
        await self.db.add_log(
            level=data.get("level", LogLevel.INFO.value),
            message=data["message"],
            user_id=data.get("user_id"),
        )
        # Database.add_log doesn't return an ID, so we return 0
        return 0

    async def update(self, id: int, data: Dict[str, Any]) -> bool:
        """
        Update log entry.

        Note: Log entries are typically immutable, but this method is implemented
        for BaseRepository compliance.

        Args:
            id: Log entry ID
            data: Update data

        Returns:
            True if updated, False otherwise
        """
        # Build dynamic update query
        update_fields = []
        values = []
        param_num = 1

        for key, value in data.items():
            if key in ["level", "message"]:
                update_fields.append(f"{key} = ${param_num}")
                values.append(value)
                param_num += 1

        if not update_fields:
            return False

        values.append(id)
        query = f"UPDATE logs SET {', '.join(update_fields)} WHERE id = ${param_num}"

        async with self.db.get_connection() as conn:
            result = await conn.execute(query, *values)
            return result != "UPDATE 0"

    async def delete(self, id: int) -> bool:
        """
        Delete log entry.

        Args:
            id: Log entry ID

        Returns:
            True if deleted, False otherwise
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM logs WHERE id = $1",
                id,
            )

            deleted = result != "DELETE 0"

            if deleted:
                logger.info(f"Deleted log entry {id}")

            return deleted
