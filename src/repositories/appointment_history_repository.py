"""Appointment history repository implementation."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.models.database import Database

from loguru import logger

from src.repositories.base import BaseRepository


class AppointmentHistory:
    """Appointment history entity model."""

    def __init__(
        self,
        id: int,
        user_id: int,
        centre: str,
        mission: str,
        status: str,
        category: Optional[str] = None,
        slot_date: Optional[str] = None,
        slot_time: Optional[str] = None,
        error_message: Optional[str] = None,
        attempt_count: Optional[int] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        """Initialize appointment history entity."""
        self.id = id
        self.user_id = user_id
        self.centre = centre
        self.mission = mission
        self.status = status
        self.category = category
        self.slot_date = slot_date
        self.slot_time = slot_time
        self.error_message = error_message
        self.attempt_count = attempt_count
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert appointment history to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "centre": self.centre,
            "mission": self.mission,
            "status": self.status,
            "category": self.category,
            "slot_date": self.slot_date,
            "slot_time": self.slot_time,
            "error_message": self.error_message,
            "attempt_count": self.attempt_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class AppointmentHistoryRepository(BaseRepository[AppointmentHistory]):
    """Repository for appointment history CRUD operations."""

    def __init__(self, database: "Database"):
        """
        Initialize appointment history repository.

        Args:
            database: Database instance
        """
        super().__init__(database)

    def _dict_to_appointment_history(self, data: Dict[str, Any]) -> AppointmentHistory:
        """
        Convert dictionary to AppointmentHistory entity.

        Args:
            data: Dictionary data

        Returns:
            AppointmentHistory entity
        """
        return AppointmentHistory(
            id=data["id"],
            user_id=data["user_id"],
            centre=data["centre"],
            mission=data["mission"],
            status=data["status"],
            category=data.get("category"),
            slot_date=data.get("slot_date"),
            slot_time=data.get("slot_time"),
            error_message=data.get("error_message"),
            attempt_count=data.get("attempt_count"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    async def get_by_id(self, id: int) -> Optional[AppointmentHistory]:
        """
        Get appointment history by ID.

        Args:
            id: History record ID

        Returns:
            AppointmentHistory entity or None if not found
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM appointment_history WHERE id = $1",
                id,
            )

            if row is None:
                return None

            return self._dict_to_appointment_history(dict(row))

    async def get_all(self, limit: int = 100) -> List[AppointmentHistory]:
        """
        Get all appointment history records.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of appointment history entities
        """
        async with self.db.get_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM appointment_history ORDER BY created_at DESC LIMIT $1",
                limit,
            )

            return [self._dict_to_appointment_history(dict(row)) for row in rows]

    async def get_by_user(
        self, user_id: int, limit: int = 50, status: Optional[str] = None
    ) -> List[AppointmentHistory]:
        """
        Get appointment history for a user.

        Args:
            user_id: User ID
            limit: Maximum number of records to return
            status: Optional status filter

        Returns:
            List of appointment history entities
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

        async with self.db.get_connection() as conn:
            rows = await conn.fetch(query, *params)
            return [self._dict_to_appointment_history(dict(row)) for row in rows]

    async def create(self, data: Dict[str, Any]) -> int:
        """
        Create new appointment history record.

        Args:
            data: Appointment history data

        Returns:
            Created history record ID
        """
        async with self.db.get_connection() as conn:
            history_id = await conn.fetchval(
                """
                INSERT INTO appointment_history
                (user_id, centre, mission, category, slot_date, slot_time, status, error_message)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                data["user_id"],
                data["centre"],
                data["mission"],
                data.get("category"),
                data.get("slot_date"),
                data.get("slot_time"),
                data["status"],
                data.get("error_message"),
            )
            return int(history_id) if history_id is not None else 0

    async def update(self, id: int, data: Dict[str, Any]) -> bool:
        """
        Update appointment history record.

        Args:
            id: History record ID
            data: Update data

        Returns:
            True if updated, False otherwise
        """
        # For status updates, use update_status method
        if "status" in data and "error_message" in data:
            return await self.update_status(id, data["status"], data.get("error_message"))

        # For other updates, build dynamic query
        update_fields = []
        values = []
        param_num = 1

        for key, value in data.items():
            if key in [
                "centre",
                "mission",
                "status",
                "category",
                "slot_date",
                "slot_time",
                "error_message",
            ]:
                update_fields.append(f"{key} = ${param_num}")
                values.append(value)
                param_num += 1

        if not update_fields:
            return False

        update_fields.append("updated_at = NOW()")
        values.append(id)

        query = "UPDATE appointment_history SET {} WHERE id = ${}".format(
            ", ".join(update_fields), param_num
        )

        async with self.db.get_connection() as conn:
            result = await conn.execute(query, *values)
            return bool(result != "UPDATE 0")

    async def update_status(
        self, id: int, status: str, error_message: Optional[str] = None
    ) -> bool:
        """
        Update appointment history status.

        Args:
            id: History record ID
            status: New status
            error_message: Optional error message

        Returns:
            True if updated, False otherwise
        """
        async with self.db.get_connection() as conn:
            await conn.execute(
                """
                UPDATE appointment_history
                SET status = $1, error_message = $2, updated_at = $3, attempt_count = attempt_count + 1
                WHERE id = $4
                """,
                status,
                error_message,
                datetime.now(timezone.utc),
                id,
            )
            return True

    async def delete(self, id: int) -> bool:
        """
        Delete appointment history record.

        Args:
            id: History record ID

        Returns:
            True if deleted, False otherwise
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM appointment_history WHERE id = $1",
                id,
            )

            deleted: bool = result != "DELETE 0"

            if deleted:
                logger.info(f"Deleted appointment history {id}")

            return deleted
