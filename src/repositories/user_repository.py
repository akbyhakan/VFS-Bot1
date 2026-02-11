"""User repository implementation."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from src.core.constants import ALLOWED_PERSONAL_DETAILS_FIELDS, ALLOWED_USER_UPDATE_FIELDS
from src.core.exceptions import BatchOperationError, RecordNotFoundError, ValidationError
from src.models.database import Database
from src.repositories.base import BaseRepository
from src.utils.db_helpers import _parse_command_tag
from src.utils.encryption import decrypt_password, encrypt_password
from src.utils.validators import validate_email, validate_phone


class User:
    """User entity model."""

    def __init__(
        self,
        id: int,
        email: str,
        phone: str,
        first_name: str,
        last_name: str,
        center_name: str,
        visa_category: str,
        visa_subcategory: str,
        is_active: bool,
        created_at: str,
        updated_at: str,
    ):
        """Initialize user entity."""
        self.id = id
        self.email = email
        self.phone = phone
        self.first_name = first_name
        self.last_name = last_name
        self.center_name = center_name
        self.visa_category = visa_category
        self.visa_subcategory = visa_subcategory
        self.is_active = is_active
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary."""
        return {
            "id": self.id,
            "email": self.email,
            "phone": self.phone,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "center_name": self.center_name,
            "visa_category": self.visa_category,
            "visa_subcategory": self.visa_subcategory,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class UserRepository(BaseRepository[User]):
    """Repository for user CRUD operations."""

    def __init__(self, database: Database):
        """
        Initialize user repository.

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

    async def create(self, data: Dict[str, Any]) -> int:
        """
        Create new user.

        Args:
            data: User data (email, password, phone, etc.)

        Returns:
            Created user ID

        Raises:
            ValidationError: If data validation fails
        """
        # Validate required fields
        if "email" not in data:
            raise ValidationError("Email is required", field="email")
        if "center_name" not in data:
            raise ValidationError("Center name is required", field="center_name")

        # Validate email format
        if not validate_email(data["email"]):
            raise ValidationError("Invalid email format", field="email")

        # Validate phone if provided
        if data.get("phone") and not validate_phone(data["phone"]):
            raise ValidationError("Invalid phone format", field="phone")

        # Encrypt password before storing
        encrypted_password = encrypt_password(data.get("password", ""))

        async with self.db.get_connection() as conn:
            user_id = await conn.fetchval(
                """
                INSERT INTO users (email, password, centre, category, subcategory)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """,
                data["email"],
                encrypted_password,
                data["center_name"],
                data.get("visa_category", ""),
                data.get("visa_subcategory", ""),
            )
            if user_id is None:
                raise RuntimeError("Failed to create user: INSERT did not return an ID")

        # Add personal details if provided
        personal_details = {}
        for key in ["first_name", "last_name", "phone", "mobile_number"]:
            if key in data and data[key]:
                personal_details[key] = data[key]

        if personal_details:
            await self.add_personal_details(user_id, personal_details)

        logger.info(f"Created user {user_id} with email {data['email']}")
        return int(user_id)

    async def update(self, id: int, data: Dict[str, Any]) -> bool:
        """
        Update user.

        Args:
            id: User ID
            data: Update data

        Returns:
            True if updated, False otherwise

        Raises:
            ValidationError: If data validation fails
            RecordNotFoundError: If user not found
        """
        # Check if user exists
        user = await self.get_by_id(id)
        if user is None:
            raise RecordNotFoundError("User", id)

        # Validate email if provided
        if "email" in data and not validate_email(data["email"]):
            raise ValidationError("Invalid email format", field="email")

        # Build dynamic update query
        updates: List[str] = []
        params: List[Any] = []
        param_num = 1

        if "email" in data:
            updates.append(f"email = ${param_num}")
            params.append(data["email"])
            param_num += 1
        if "password" in data:
            encrypted_password = encrypt_password(data["password"])
            updates.append(f"password = ${param_num}")
            params.append(encrypted_password)
            param_num += 1
        if "center_name" in data or "centre" in data:
            centre = data.get("center_name") or data.get("centre")
            updates.append(f"centre = ${param_num}")
            params.append(centre)
            param_num += 1
        if "visa_category" in data or "category" in data:
            category = data.get("visa_category") or data.get("category")
            updates.append(f"category = ${param_num}")
            params.append(category)
            param_num += 1
        if "visa_subcategory" in data or "subcategory" in data:
            subcategory = data.get("visa_subcategory") or data.get("subcategory")
            updates.append(f"subcategory = ${param_num}")
            params.append(subcategory)
            param_num += 1
        if "is_active" in data:
            updates.append(f"active = ${param_num}")
            params.append(data["is_active"])
            param_num += 1

        if not updates:
            return True  # Nothing to update

        updates.append("updated_at = NOW()")
        params.append(id)

        async with self.db.get_connection() as conn:
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ${param_num}"
            result = await conn.execute(query, *params)

            success = result != "UPDATE 0"
            if success:
                logger.info(f"Updated user {id}")

            return success

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

    async def add_personal_details(self, user_id: int, details: Dict[str, Any]) -> int:
        """
        Add personal details for a user.

        Args:
            user_id: User ID
            details: Personal details dictionary

        Returns:
            Personal details ID

        Raises:
            ValidationError: If email or phone format is invalid
            ValueError: If user_id is invalid
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}. Must be a positive integer.")

        email = details.get("email")
        if email and not validate_email(email):
            raise ValidationError(f"Invalid email format: {email}", field="email")

        mobile_number = details.get("mobile_number")
        if mobile_number and not validate_phone(mobile_number):
            raise ValidationError(
                f"Invalid phone number format: {mobile_number}", field="mobile_number"
            )

        passport_number = details.get("passport_number")
        passport_number_encrypted = None
        if passport_number:
            passport_number_encrypted = encrypt_password(passport_number)

        async with self.db.get_connection() as conn:
            personal_id = await conn.fetchval(
                """
                INSERT INTO personal_details
                (user_id, first_name, last_name, passport_number, passport_number_encrypted, passport_expiry,
                 gender, mobile_code, mobile_number, email, nationality, date_of_birth,
                 address_line1, address_line2, state, city, postcode)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                RETURNING id
            """,
                user_id,
                details.get("first_name"),
                details.get("last_name"),
                "",
                passport_number_encrypted,
                details.get("passport_expiry"),
                details.get("gender"),
                details.get("mobile_code"),
                details.get("mobile_number"),
                details.get("email"),
                details.get("nationality"),
                details.get("date_of_birth"),
                details.get("address_line1"),
                details.get("address_line2"),
                details.get("state"),
                details.get("city"),
                details.get("postcode"),
            )
            logger.info(f"Personal details added for user {user_id}")
            if personal_id is None:
                raise RuntimeError("Failed to insert personal details: no ID returned")
            return int(personal_id)

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

    async def update_personal_details(
        self,
        user_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        mobile_number: Optional[str] = None,
        **other_fields: Any,
    ) -> bool:
        """
        Update personal details for a user with SQL injection protection.

        Args:
            user_id: User ID
            first_name: New first name (optional)
            last_name: New last name (optional)
            mobile_number: New mobile number (optional)
            **other_fields: Other personal detail fields

        Returns:
            True if updated, False if not found

        Raises:
            ValidationError: If phone format is invalid
            ValueError: If user_id is invalid
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("Invalid user_id")

        if mobile_number and not validate_phone(mobile_number):
            raise ValidationError(
                f"Invalid phone number format: {mobile_number}", field="mobile_number"
            )

        updates: List[str] = []
        params: List[Any] = []
        param_num = 1

        if first_name is not None:
            updates.append(f"first_name = ${param_num}")
            params.append(first_name)
            param_num += 1
        if last_name is not None:
            updates.append(f"last_name = ${param_num}")
            params.append(last_name)
            param_num += 1
        if mobile_number is not None:
            updates.append(f"mobile_number = ${param_num}")
            params.append(mobile_number)
            param_num += 1

        valid_fields = {}
        rejected = set()

        for field, value in other_fields.items():
            if value is not None:
                if field in ALLOWED_PERSONAL_DETAILS_FIELDS:
                    valid_fields[field] = value
                else:
                    rejected.add(field)

        if rejected:
            logger.warning(f"Rejected disallowed fields for user {user_id}: {rejected}")

        for field, value in valid_fields.items():
            if field == "passport_number" and value is not None:
                encrypted_value = encrypt_password(value)
                updates.append(f"passport_number_encrypted = ${param_num}")
                params.append(encrypted_value)
                param_num += 1
                updates.append(f"passport_number = ${param_num}")
                params.append("")
                param_num += 1
            else:
                updates.append(f"{field} = ${param_num}")
                params.append(value)
                param_num += 1

        if not updates:
            return True

        updates.append("updated_at = NOW()")
        params.append(user_id)

        async with self.db.get_connection() as conn:
            query = f"UPDATE personal_details SET {', '.join(updates)} WHERE user_id = ${param_num}"
            result = await conn.execute(query, *params)

            success = result != "UPDATE 0"
            if success:
                logger.info(f"Personal details updated for user {user_id}")

            return success

    async def create_batch(self, users: List[Dict[str, Any]]) -> List[int]:
        """
        Add multiple users in a single transaction for improved performance.

        Args:
            users: List of user dictionaries with keys:
                email, password, centre, category, subcategory

        Returns:
            List of user IDs for successfully added users

        Raises:
            ValidationError: If any email format is invalid
            BatchOperationError: If batch operation fails
        """
        if not users:
            return []

        for user in users:
            email = user.get("email")
            if not email or not validate_email(email):
                raise ValidationError(f"Invalid email format: {email}", field="email")

        user_ids: List[int] = []
        failed_count = 0

        async with self.db.get_connection() as conn:
            try:
                async with conn.transaction():
                    for user in users:
                        encrypted_password = encrypt_password(user["password"])

                        user_id = await conn.fetchval(
                            """
                            INSERT INTO users (email, password, centre, category, subcategory)
                            VALUES ($1, $2, $3, $4, $5)
                            RETURNING id
                            """,
                            user["email"],
                            encrypted_password,
                            user["centre"],
                            user["category"],
                            user["subcategory"],
                        )
                        if user_id:
                            user_ids.append(user_id)

                    logger.info(f"Batch added {len(user_ids)} users")
                    return user_ids

            except Exception as e:
                failed_count = len(users) - len(user_ids)
                logger.error(f"Batch user insert failed: {e}")
                raise BatchOperationError(
                    f"Failed to add users in batch: {e}",
                    operation="add_users_batch",
                    failed_count=failed_count,
                    total_count=len(users),
                ) from e

    async def update_batch(self, updates: List[Dict[str, Any]]) -> int:
        """
        Update multiple users in a single transaction for improved performance.

        Args:
            updates: List of update dictionaries with 'id' and optional fields:
                    email, password, centre, category, subcategory, active

        Returns:
            Number of users successfully updated

        Raises:
            ValidationError: If any email format is invalid or invalid field name
            BatchOperationError: If batch operation fails
        """
        if not updates:
            return 0

        for update in updates:
            email = update.get("email")
            if email and not validate_email(email):
                raise ValidationError(f"Invalid email format: {email}", field="email")

            for field_name in update.keys():
                if field_name != "id" and field_name not in ALLOWED_USER_UPDATE_FIELDS:
                    raise ValidationError(
                        f"Invalid field name for user update: {field_name}", field=field_name
                    )

        updated_count = 0

        async with self.db.get_connection() as conn:
            try:
                async with conn.transaction():
                    for update in updates:
                        user_id = update.get("id")
                        if not user_id:
                            logger.warning("Skipping update without user_id")
                            continue

                        fields: List[str] = []
                        params: List[Any] = []
                        param_num = 1

                        if "email" in update:
                            fields.append(f"email = ${param_num}")
                            params.append(update["email"])
                            param_num += 1
                        if "password" in update:
                            encrypted_password = encrypt_password(update["password"])
                            fields.append(f"password = ${param_num}")
                            params.append(encrypted_password)
                            param_num += 1
                        if "centre" in update:
                            fields.append(f"centre = ${param_num}")
                            params.append(update["centre"])
                            param_num += 1
                        if "category" in update:
                            fields.append(f"category = ${param_num}")
                            params.append(update["category"])
                            param_num += 1
                        if "subcategory" in update:
                            fields.append(f"subcategory = ${param_num}")
                            params.append(update["subcategory"])
                            param_num += 1
                        if "active" in update:
                            fields.append(f"active = ${param_num}")
                            params.append(update["active"])
                            param_num += 1

                        if not fields:
                            continue

                        fields.append("updated_at = NOW()")
                        params.append(user_id)

                        query = f"UPDATE users SET {', '.join(fields)} WHERE id = ${param_num}"
                        result = await conn.execute(query, *params)

                        if result != "UPDATE 0":
                            updated_count += 1

                    logger.info(f"Batch updated {updated_count} users")
                    return updated_count

            except Exception as e:
                logger.error(f"Batch user update failed: {e}")
                raise BatchOperationError(
                    f"Failed to update users in batch: {e}",
                    operation="update_users_batch",
                    failed_count=len(updates) - updated_count,
                    total_count=len(updates),
                ) from e

    async def delete(self, id: int) -> bool:
        """
        Delete user (soft delete by setting is_active=False).

        Args:
            id: User ID

        Returns:
            True if deleted, False otherwise
        """
        return await self.update(id, {"is_active": False})

    async def hard_delete(self, id: int) -> bool:
        """
        Permanently delete user from database.

        Args:
            id: User ID

        Returns:
            True if deleted, False otherwise
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute("DELETE FROM users WHERE id = $1", id)

            deleted = _parse_command_tag(result) > 0

            if deleted:
                logger.warning(f"Hard deleted user {id}")

            return deleted

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
