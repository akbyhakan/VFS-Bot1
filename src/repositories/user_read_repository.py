"""User read repository implementation."""

from typing import Any, Dict, List, Optional

from loguru import logger

from src.models.database import Database
from src.repositories.base import BaseRepository
from src.repositories.user_entity import User
from src.utils.encryption import decrypt_password


class UserReadRepository(BaseRepository[User]):
    """Repository for user read operations."""

    def __init__(self, database: Database):
        """
        Initialize user read repository.

        Args:
            database: Database instance
        """
        super().__init__(database)

    def _row_to_user(self, row: Any) -> User:
        """
        Convert database row to User entity.

        Args:
            row: Database row

        Returns:
            User entity
        """
        return User(
            id=row["id"],
            email=row["email"],
            phone=row.get("phone", ""),
            first_name=row.get("first_name", ""),
            last_name=row.get("last_name", ""),
            center_name=row.get("center_name", ""),
            visa_category=row.get("visa_category", ""),
            visa_subcategory=row.get("visa_subcategory", ""),
            is_active=bool(row.get("is_active", True)),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )

    async def get_by_id(self, id: int) -> Optional[User]:
        """
        Get user by ID.

        Args:
            id: User ID

        Returns:
            User entity or None if not found
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, email, phone, first_name, last_name, center_name,
                       visa_category, visa_subcategory, is_active, created_at, updated_at
                FROM users
                WHERE id = $1
                """,
                id,
            )

            if row is None:
                return None

            return self._row_to_user(row)

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.

        Args:
            email: User email

        Returns:
            User entity or None if not found
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, email, phone, first_name, last_name, center_name,
                       visa_category, visa_subcategory, is_active, created_at, updated_at
                FROM users
                WHERE email = $1
                """,
                email,
            )

            if row is None:
                return None

            return self._row_to_user(row)

    async def get_all(self, limit: int = 100, active_only: bool = False) -> List[User]:
        """
        Get all users.

        Args:
            limit: Maximum number of users to return
            active_only: If True, only return active users

        Returns:
            List of user entities
        """
        query = """
            SELECT id, email, phone, first_name, last_name, center_name,
                   visa_category, visa_subcategory, is_active, created_at, updated_at
            FROM users
        """

        if active_only:
            query += " WHERE is_active = TRUE"

        query += " ORDER BY created_at DESC LIMIT $1"

        async with self.db.get_connection() as conn:
            rows = await conn.fetch(query, limit)

            return [self._row_to_user(row) for row in rows]

    async def get_all_active(self) -> List[Dict[str, Any]]:
        """
        Get all active users.

        Returns:
            List of user dictionaries
        """
        async with self.db.get_connection() as conn:
            rows = await conn.fetch("SELECT * FROM users WHERE active = true")
            return [dict(row) for row in rows]

    async def get_by_id_with_password(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user with decrypted password for VFS login.

        Args:
            user_id: User ID

        Returns:
            User dictionary with decrypted password or None

        Raises:
            ValueError: If user_id is invalid (negative or zero)
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}. Must be a positive integer.")

        async with self.db.get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
            if row:
                user = dict(row)
                try:
                    user["password"] = decrypt_password(user["password"])
                except Exception as e:
                    logger.error(f"Failed to decrypt password for user {user_id}: {e}")
                    raise
                return user
            return None

    async def get_all_active_with_passwords(self) -> List[Dict[str, Any]]:
        """
        Get all active users with decrypted passwords for VFS login.

        Returns:
            List of user dictionaries with decrypted passwords
        """
        async with self.db.get_connection() as conn:
            rows = await conn.fetch("SELECT * FROM users WHERE active = true")
            users = []
            failed_users = []
            for row in rows:
                user = dict(row)
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

            if failed_users:
                logger.warning(
                    f"⚠️  {len(failed_users)} user(s) have invalid "
                    f"encrypted passwords and will be skipped: "
                    f"{', '.join(failed_users)}. They need to re-register."
                )

            return users

    async def get_personal_details(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get personal details for a user.

        Args:
            user_id: User ID

        Returns:
            Personal details dictionary or None

        Raises:
            ValueError: If user_id is invalid
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}. Must be a positive integer.")

        async with self.db.get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM personal_details WHERE user_id = $1", user_id)
            if not row:
                return None

            details = dict(row)

            if details.get("passport_number_encrypted"):
                try:
                    details["passport_number"] = decrypt_password(
                        details["passport_number_encrypted"]
                    )
                except Exception as e:
                    logger.warning(f"Failed to decrypt passport number for user {user_id}: {e}")
                    if not details.get("passport_number"):
                        details["passport_number"] = None

            return details

    async def get_personal_details_batch(self, user_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """
        Get personal details for multiple users in a single query (N+1 query prevention).

        Args:
            user_ids: List of user IDs

        Returns:
            Dictionary mapping user_id to personal details dictionary

        Raises:
            ValueError: If user_ids is empty or contains invalid IDs
        """
        if not user_ids:
            return {}

        for user_id in user_ids:
            if not isinstance(user_id, int) or user_id <= 0:
                raise ValueError(f"Invalid user_id: {user_id}. Must be a positive integer.")

        async with self.db.get_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM personal_details WHERE user_id = ANY($1::bigint[])", user_ids
            )

            result = {}
            for row in rows:
                details = dict(row)

                if details.get("passport_number_encrypted"):
                    try:
                        details["passport_number"] = decrypt_password(
                            details["passport_number_encrypted"]
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to decrypt passport number for user {details['user_id']}: {e}"
                        )
                        if not details.get("passport_number"):
                            details["passport_number"] = None

                result[details["user_id"]] = details

            return result

    async def get_all_with_details(self) -> List[Dict[str, Any]]:
        """
        Get all users with their personal details joined.

        Returns:
            List of user dictionaries with personal details
        """
        async with self.db.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    u.id, u.email, u.centre as center_name,
                    u.category as visa_category, u.subcategory as visa_subcategory,
                    u.active as is_active, u.created_at, u.updated_at,
                    p.first_name, p.last_name, p.mobile_number as phone
                FROM users u
                LEFT JOIN personal_details p ON u.id = p.user_id
                ORDER BY u.created_at DESC
            """
            )
            return [dict(row) for row in rows]

    async def get_by_id_with_details(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single user with their personal details joined by user ID.

        Args:
            user_id: User ID to retrieve

        Returns:
            User dictionary with personal details or None if not found

        Raises:
            ValueError: If user_id is invalid
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}")

        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT u.id, u.email, u.centre as center_name,
                       u.category as visa_category, u.subcategory as visa_subcategory,
                       u.active as is_active, u.created_at, u.updated_at,
                       p.first_name, p.last_name, p.mobile_number as phone
                FROM users u
                LEFT JOIN personal_details p ON u.id = p.user_id
                WHERE u.id = $1
                """,
                user_id,
            )
            return dict(row) if row else None

    async def get_active_count(self) -> int:
        """
        Get count of active users.

        Returns:
            Number of active users
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
            count: int = row[0] if row else 0
            return count
