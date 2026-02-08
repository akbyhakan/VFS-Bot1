"""Appointment request repository implementation."""

import logging
from typing import Any, Dict, List, Optional

from src.models.database import Database
from src.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class AppointmentRequest:
    """Appointment request entity model."""

    def __init__(
        self,
        id: int,
        country_code: str,
        visa_category: str,
        visa_subcategory: str,
        centres: List[str],
        preferred_dates: List[str],
        person_count: int,
        status: str,
        created_at: str,
        updated_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        persons: Optional[List[Dict[str, Any]]] = None,
    ):
        """Initialize appointment request entity."""
        self.id = id
        self.country_code = country_code
        self.visa_category = visa_category
        self.visa_subcategory = visa_subcategory
        self.centres = centres
        self.preferred_dates = preferred_dates
        self.person_count = person_count
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at
        self.completed_at = completed_at
        self.persons = persons or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert appointment request to dictionary."""
        return {
            "id": self.id,
            "country_code": self.country_code,
            "visa_category": self.visa_category,
            "visa_subcategory": self.visa_subcategory,
            "centres": self.centres,
            "preferred_dates": self.preferred_dates,
            "person_count": self.person_count,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "persons": self.persons,
        }


class AppointmentRequestRepository(BaseRepository[AppointmentRequest]):
    """Repository for appointment request CRUD operations."""

    def __init__(self, database: Database):
        """
        Initialize appointment request repository.

        Args:
            database: Database instance
        """
        super().__init__(database)

    def _dict_to_appointment_request(self, data: Dict[str, Any]) -> AppointmentRequest:
        """
        Convert dictionary to AppointmentRequest entity.

        Args:
            data: Dictionary data

        Returns:
            AppointmentRequest entity
        """
        return AppointmentRequest(
            id=data["id"],
            country_code=data["country_code"],
            visa_category=data.get("visa_category", ""),
            visa_subcategory=data.get("visa_subcategory", ""),
            centres=data["centres"],
            preferred_dates=data["preferred_dates"],
            person_count=data["person_count"],
            status=data["status"],
            created_at=data["created_at"],
            updated_at=data.get("updated_at"),
            completed_at=data.get("completed_at"),
            persons=data.get("persons", []),
        )

    async def get_by_id(self, id: int) -> Optional[AppointmentRequest]:
        """
        Get appointment request by ID (delegates to Database.get_appointment_request).

        Args:
            id: Request ID

        Returns:
            AppointmentRequest entity or None if not found
        """
        request_dict = await self.db.get_appointment_request(request_id=id)
        if request_dict is None:
            return None

        return self._dict_to_appointment_request(request_dict)

    async def get_all(self, limit: int = 100, status: Optional[str] = None) -> List[AppointmentRequest]:
        """
        Get all appointment requests (delegates to Database.get_all_appointment_requests).

        Args:
            limit: Maximum number of requests to return (not used by underlying method)
            status: Optional status filter

        Returns:
            List of appointment request entities
        """
        request_dicts = await self.db.get_all_appointment_requests(status=status)
        return [self._dict_to_appointment_request(req) for req in request_dicts]

    async def get_pending_for_user(self, user_id: int) -> Optional[AppointmentRequest]:
        """
        Get pending appointment request for user.

        Args:
            user_id: User ID

        Returns:
            AppointmentRequest entity or None if not found
        """
        request_dict = await self.db.get_pending_appointment_request_for_user(user_id=user_id)
        if request_dict is None:
            return None

        return self._dict_to_appointment_request(request_dict)

    async def create(self, data: Dict[str, Any]) -> int:
        """
        Create new appointment request (delegates to Database.create_appointment_request).

        Args:
            data: Appointment request data

        Returns:
            Created request ID
        """
        return await self.db.create_appointment_request(
            country_code=data["country_code"],
            visa_category=data.get("visa_category", ""),
            visa_subcategory=data.get("visa_subcategory", ""),
            centres=data["centres"],
            preferred_dates=data["preferred_dates"],
            person_count=data["person_count"],
            persons=data["persons"],
        )

    async def update(self, id: int, data: Dict[str, Any]) -> bool:
        """
        Update appointment request.

        Args:
            id: Request ID
            data: Update data

        Returns:
            True if updated, False otherwise
        """
        # For status updates, use update_status method
        if "status" in data:
            return await self.update_status(
                id,
                data["status"],
                data.get("completed_at")
            )

        # For other updates, build dynamic query
        import json
        update_fields = []
        values = []
        param_num = 1

        for key, value in data.items():
            if key in ["country_code", "visa_category", "visa_subcategory", "person_count"]:
                update_fields.append(f"{key} = ${param_num}")
                values.append(value)
                param_num += 1
            elif key in ["centres", "preferred_dates"]:
                update_fields.append(f"{key} = ${param_num}")
                values.append(json.dumps(value))
                param_num += 1

        if not update_fields:
            return False

        update_fields.append(f"updated_at = NOW()")
        values.append(id)

        query = f"UPDATE appointment_requests SET {', '.join(update_fields)} WHERE id = ${param_num}"

        async with self.db.get_connection() as conn:
            result = await conn.execute(query, *values)
            return result != "UPDATE 0"

    async def update_status(self, id: int, status: str, completed_at: Any = None) -> bool:
        """
        Update appointment request status (delegates to Database.update_appointment_request_status).

        Args:
            id: Request ID
            status: New status
            completed_at: Optional completion timestamp

        Returns:
            True if updated, False otherwise
        """
        return await self.db.update_appointment_request_status(
            request_id=id,
            status=status,
            completed_at=completed_at,
        )

    async def delete(self, id: int) -> bool:
        """
        Delete appointment request (delegates to Database.delete_appointment_request).

        Args:
            id: Request ID

        Returns:
            True if deleted, False otherwise
        """
        return await self.db.delete_appointment_request(request_id=id)

    async def cleanup_completed(self, days: int = 30) -> int:
        """
        Cleanup completed requests older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of requests deleted
        """
        return await self.db.cleanup_completed_requests(days=days)
