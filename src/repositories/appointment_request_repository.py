"""Appointment request repository implementation."""

import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.models.database import Database

from loguru import logger

from src.core.exceptions import ValidationError
from src.repositories.base import BaseRepository
from src.utils.validators import validate_email


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

    def __init__(self, database: "Database"):
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
        Get appointment request by ID.

        Args:
            id: Request ID

        Returns:
            AppointmentRequest entity or None if not found
        """
        async with self.db.get_connection() as conn:
            # Get request
            request_row = await conn.fetchrow(
                "SELECT * FROM appointment_requests WHERE id = $1", id
            )

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
            person_rows = await conn.fetch(
                "SELECT * FROM appointment_persons WHERE request_id = $1", id
            )
            request["persons"] = [dict(row) for row in person_rows]

            return self._dict_to_appointment_request(request)

    async def get_all(
        self, limit: int = 100, status: Optional[str] = None
    ) -> List[AppointmentRequest]:
        """
        Get all appointment requests.

        Args:
            limit: Maximum number of requests to return (not used by underlying method)
            status: Optional status filter

        Returns:
            List of appointment request entities
        """
        async with self.db.get_connection() as conn:
            if status:
                request_rows = await conn.fetch(
                    """SELECT * FROM appointment_requests
                    WHERE status = $1 ORDER BY created_at DESC""",
                    status,
                )
            else:
                request_rows = await conn.fetch(
                    "SELECT * FROM appointment_requests ORDER BY created_at DESC"
                )

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
                person_rows = await conn.fetch(
                    "SELECT * FROM appointment_persons WHERE request_id = $1", request["id"]
                )
                request["persons"] = [dict(row) for row in person_rows]

                requests.append(self._dict_to_appointment_request(request))

            return requests

    async def get_pending_for_user(self, user_id: int) -> Optional[AppointmentRequest]:
        """
        Get pending appointment request for user.

        Args:
            user_id: User ID

        Returns:
            AppointmentRequest entity or None if not found
        """
        async with self.db.get_connection() as conn:
            # Get user email
            user_row = await conn.fetchrow("SELECT email FROM users WHERE id = $1", user_id)
            if not user_row:
                return None

            user_email = user_row["email"]

            # Find pending request where any person matches user email
            row = await conn.fetchrow(
                """
                SELECT DISTINCT ar.id, ar.created_at FROM appointment_requests ar
                JOIN appointment_persons ap ON ar.id = ap.request_id
                WHERE ap.email = $1 AND ar.status = 'pending'
                ORDER BY ar.created_at DESC
                LIMIT 1
                """,
                user_email,
            )
            if not row:
                return None

            # Get full request with persons
            return await self.get_by_id(row["id"])

    async def get_all_pending_for_user(self, user_id: int) -> List[AppointmentRequest]:
        """
        Get ALL pending appointment requests for a user.

        Args:
            user_id: User ID

        Returns:
            List of AppointmentRequest entities (empty list if none found)
        """
        async with self.db.get_connection() as conn:
            # Get user email
            user_row = await conn.fetchrow("SELECT email FROM users WHERE id = $1", user_id)
            if not user_row:
                return []

            user_email = user_row["email"]

            # Find all pending requests where any person matches user email
            rows = await conn.fetch(
                """
                SELECT DISTINCT ar.id, ar.created_at FROM appointment_requests ar
                JOIN appointment_persons ap ON ar.id = ap.request_id
                WHERE ap.email = $1 AND ar.status = 'pending'
                ORDER BY ar.created_at DESC
                """,
                user_email,
            )
            if not rows:
                return []

            # Get full requests with persons
            requests = []
            for row in rows:
                request = await self.get_by_id(row["id"])
                if request:
                    requests.append(request)
            return requests

    async def get_user_ids_with_pending_requests(self) -> set[int]:
        """
        Get set of user IDs that have at least one pending appointment request.

        This is a bulk query alternative to calling get_pending_for_user()
        for each user individually, avoiding N+1 query problem.

        Returns:
            Set of user IDs with pending appointment requests
        """
        async with self.db.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT u.id
                FROM users u
                JOIN appointment_persons ap ON ap.email = u.email
                JOIN appointment_requests ar ON ar.id = ap.request_id
                WHERE ar.status = 'pending' AND u.active = true
                """
            )
            return {row["id"] for row in rows}

    async def create(self, data: Dict[str, Any]) -> int:
        """
        Create new appointment request.

        Args:
            data: Appointment request data

        Returns:
            Created request ID
        """
        async with self.db.get_connection() as conn:
            async with conn.transaction():
                # Insert appointment request
                request_id = await conn.fetchval(
                    """
                    INSERT INTO appointment_requests
                    (country_code, visa_category, visa_subcategory, centres,
                     preferred_dates, person_count)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    data["country_code"],
                    data.get("visa_category", ""),
                    data.get("visa_subcategory", ""),
                    json.dumps(data["centres"]),
                    json.dumps(data["preferred_dates"]),
                    data["person_count"],
                )
                if request_id is None:
                    raise RuntimeError("Failed to get inserted request ID")

                # Insert persons
                for person in data["persons"]:
                    # Validate email
                    email = person.get("email", "")
                    if not email:
                        raise ValidationError("Email is required for all persons", field="email")
                    if not validate_email(email):
                        raise ValidationError(f"Invalid email format: {email}", field="email")

                    await conn.execute(
                        """
                        INSERT INTO appointment_persons
                        (request_id, first_name, last_name, gender, nationality, birth_date,
                         passport_number, passport_issue_date, passport_expiry_date,
                         phone_code, phone_number, email, is_child_with_parent)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        """,
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
                    )

                logger.info(f"Appointment request created: {request_id}")
                return int(request_id)

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
            return await self.update_status(id, data["status"], data.get("completed_at"))

        # For other updates, build dynamic query
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

        update_fields.append("updated_at = NOW()")
        values.append(id)

        query = "UPDATE appointment_requests SET {} WHERE id = ${}".format(
            ", ".join(update_fields), param_num
        )

        async with self.db.get_connection() as conn:
            result = await conn.execute(query, *values)
            return bool(result != "UPDATE 0")

    async def update_status(self, id: int, status: str, completed_at: Any = None) -> bool:
        """
        Update appointment request status.

        Args:
            id: Request ID
            status: New status
            completed_at: Optional completion timestamp

        Returns:
            True if updated, False otherwise
        """
        async with self.db.get_connection() as conn:
            if completed_at:
                result = await conn.execute(
                    """
                    UPDATE appointment_requests
                    SET status = $1, completed_at = $2, updated_at = NOW()
                    WHERE id = $3
                    """,
                    status,
                    completed_at,
                    id,
                )
            else:
                result = await conn.execute(
                    """
                    UPDATE appointment_requests
                    SET status = $1, updated_at = NOW()
                    WHERE id = $2
                    """,
                    status,
                    id,
                )

            if result != "UPDATE 0":
                logger.info(f"Appointment request {id} status updated to {status}")
                return True
            return False

    async def delete(self, id: int) -> bool:
        """
        Delete appointment request (cascades to persons).

        Args:
            id: Request ID

        Returns:
            True if deleted, False otherwise
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute("DELETE FROM appointment_requests WHERE id = $1", id)

            if result != "DELETE 0":
                logger.info(f"Appointment request {id} deleted")
                return True
            return False

    async def cleanup_completed(self, days: int = 30) -> int:
        """
        Cleanup completed requests older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of requests deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        async with self.db.get_connection() as conn:
            result = await conn.execute(
                """
                DELETE FROM appointment_requests
                WHERE status = 'completed' AND completed_at < $1
                """,
                cutoff_date,
            )
            # Parse the command tag like "DELETE 5" to get the count
            deleted_count = int(result.split()[-1]) if result and result.startswith("DELETE") else 0

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old appointment requests")

            return deleted_count
