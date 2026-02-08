"""Appointment repository implementation."""

import logging
from typing import Any, Dict, List, Optional

from src.models.database import Database
from src.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class Appointment:
    """Appointment entity model."""

    def __init__(
        self,
        id: int,
        user_id: int,
        centre: str,
        category: str,
        subcategory: str,
        appointment_date: Optional[str] = None,
        appointment_time: Optional[str] = None,
        reference_number: Optional[str] = None,
        status: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        """Initialize appointment entity."""
        self.id = id
        self.user_id = user_id
        self.centre = centre
        self.category = category
        self.subcategory = subcategory
        self.appointment_date = appointment_date
        self.appointment_time = appointment_time
        self.reference_number = reference_number
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert appointment to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "centre": self.centre,
            "category": self.category,
            "subcategory": self.subcategory,
            "appointment_date": self.appointment_date,
            "appointment_time": self.appointment_time,
            "reference_number": self.reference_number,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class AppointmentRepository(BaseRepository[Appointment]):
    """Repository for appointment CRUD operations."""

    def __init__(self, database: Database):
        """
        Initialize appointment repository.

        Args:
            database: Database instance
        """
        super().__init__(database)

    def _row_to_appointment(self, row: Any) -> Appointment:
        """
        Convert database row to Appointment entity.

        Args:
            row: Database row

        Returns:
            Appointment entity
        """
        return Appointment(
            id=row["id"],
            user_id=row["user_id"],
            centre=row.get("centre", ""),
            category=row.get("category", ""),
            subcategory=row.get("subcategory", ""),
            appointment_date=row.get("appointment_date"),
            appointment_time=row.get("appointment_time"),
            reference_number=row.get("reference_number"),
            status=row.get("status"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    async def get_by_id(self, id: int) -> Optional[Appointment]:
        """
        Get appointment by ID.

        Args:
            id: Appointment ID

        Returns:
            Appointment entity or None if not found
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM appointments WHERE id = $1",
                id,
            )

            if row is None:
                return None

            return self._row_to_appointment(row)

    async def get_all(self, limit: int = 100) -> List[Appointment]:
        """
        Get all appointments.

        Args:
            limit: Maximum number of appointments to return

        Returns:
            List of appointment entities
        """
        async with self.db.get_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM appointments ORDER BY created_at DESC LIMIT $1",
                limit,
            )

            return [self._row_to_appointment(row) for row in rows]

    async def get_by_user(self, user_id: int, limit: int = 100) -> List[Appointment]:
        """
        Get appointments for a specific user.

        Args:
            user_id: User ID
            limit: Maximum number of appointments to return

        Returns:
            List of appointment entities
        """
        async with self.db.get_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM appointments WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
                user_id,
                limit,
            )

            return [self._row_to_appointment(row) for row in rows]

    async def create(self, data: Dict[str, Any]) -> int:
        """
        Create new appointment (delegates to Database.add_appointment).

        Args:
            data: Appointment data

        Returns:
            Created appointment ID
        """
        return await self.db.add_appointment(
            user_id=data["user_id"],
            centre=data["centre"],
            category=data["category"],
            subcategory=data["subcategory"],
            date=data.get("appointment_date"),
            time=data.get("appointment_time"),
            reference=data.get("reference_number"),
        )

    async def update(self, id: int, data: Dict[str, Any]) -> bool:
        """
        Update appointment.

        Args:
            id: Appointment ID
            data: Update data

        Returns:
            True if updated, False otherwise
        """
        # Build dynamic update query
        update_fields = []
        values = []
        param_num = 1

        for key, value in data.items():
            if key in [
                "centre",
                "category",
                "subcategory",
                "appointment_date",
                "appointment_time",
                "reference_number",
                "status",
            ]:
                update_fields.append(f"{key} = ${param_num}")
                values.append(value)
                param_num += 1

        if not update_fields:
            return False

        update_fields.append("updated_at = NOW()")
        values.append(id)

        query = "UPDATE appointments SET {} WHERE id = ${}".format(
            ", ".join(update_fields), param_num
        )

        async with self.db.get_connection() as conn:
            result = await conn.execute(query, *values)
            return result != "UPDATE 0"

    async def delete(self, id: int) -> bool:
        """
        Delete appointment.

        Args:
            id: Appointment ID

        Returns:
            True if deleted, False otherwise
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM appointments WHERE id = $1",
                id,
            )

            deleted = result != "DELETE 0"

            if deleted:
                logger.info(f"Deleted appointment {id}")

            return deleted
