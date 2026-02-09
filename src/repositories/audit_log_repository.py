"""Audit log repository implementation."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.models.database import Database
from src.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class AuditLogEntry:
    """Audit log entry entity model."""

    def __init__(
        self,
        id: int,
        action: str,
        user_id: Optional[int],
        username: Optional[str],
        ip_address: Optional[str],
        user_agent: Optional[str],
        details: Optional[str],
        timestamp: str,
        success: bool,
    ):
        """Initialize audit log entry entity."""
        self.id = id
        self.action = action
        self.user_id = user_id
        self.username = username
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.details = details
        self.timestamp = timestamp
        self.success = success

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit log entry to dictionary."""
        return {
            "id": self.id,
            "action": self.action,
            "user_id": self.user_id,
            "username": self.username,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "details": self.details,
            "timestamp": self.timestamp,
            "success": self.success,
        }


class AuditLogRepository(BaseRepository[AuditLogEntry]):
    """Repository for audit log CRUD operations."""

    def __init__(self, database: Database):
        """
        Initialize audit log repository.

        Args:
            database: Database instance
        """
        super().__init__(database)

    def _row_to_entry(self, row: Any) -> AuditLogEntry:
        """
        Convert database row to AuditLogEntry entity.

        Args:
            row: Database row

        Returns:
            AuditLogEntry entity
        """
        return AuditLogEntry(
            id=row["id"],
            action=row["action"],
            user_id=row.get("user_id"),
            username=row.get("username"),
            ip_address=row.get("ip_address"),
            user_agent=row.get("user_agent"),
            details=row.get("details"),
            timestamp=row["timestamp"],
            success=bool(row.get("success", True)),
        )

    async def get_by_id(self, id: int) -> Optional[AuditLogEntry]:
        """
        Get audit log entry by ID.

        Args:
            id: Entry ID

        Returns:
            AuditLogEntry entity or None if not found
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM audit_log WHERE id = $1",
                id,
            )

            if row is None:
                return None

            return self._row_to_entry(row)

    async def get_all(
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
        async with self.db.get_connection() as conn:
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

    async def create(self, data: Dict[str, Any]) -> int:
        """
        Create new audit log entry.

        Args:
            data: Audit log data (action, user_id, username, ip_address, etc.)

        Returns:
            Created entry ID
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        async with self.db.get_connection() as conn:
            audit_id = await conn.fetchval(
                """
                INSERT INTO audit_log
                (action, user_id, username, ip_address, user_agent, details, timestamp, success)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                data.get("action"),
                data.get("user_id"),
                data.get("username"),
                data.get("ip_address"),
                data.get("user_agent"),
                data.get("details"),
                timestamp,
                data.get("success", True),
            )
            if audit_id is None:
                raise RuntimeError("Failed to fetch ID after insert")
            logger.debug(f"Audit log entry added: {data.get('action')}")
            return int(audit_id)

    async def update(self, id: int, data: Dict[str, Any]) -> bool:
        """
        Update audit log entry (not typically supported for audit logs).

        Args:
            id: Entry ID
            data: Update data

        Returns:
            False (audit logs are immutable)
        """
        logger.warning("Audit logs are immutable and cannot be updated")
        return False

    async def delete(self, id: int) -> bool:
        """
        Delete audit log entry (soft delete or hard delete based on requirements).

        Args:
            id: Entry ID

        Returns:
            True if deleted, False otherwise
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM audit_log WHERE id = $1",
                id,
            )
            deleted = result != "DELETE 0"

            if deleted:
                logger.warning(f"Audit log entry {id} deleted")

            return deleted
