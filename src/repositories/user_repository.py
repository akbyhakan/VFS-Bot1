"""User repository implementation with backward compatibility."""

from typing import Any, Dict, List, Optional

from src.models.database import Database
from src.repositories.base import BaseRepository
from src.repositories.user_entity import User
from src.repositories.user_read_repository import UserReadRepository
from src.repositories.user_write_repository import UserWriteRepository


class UserRepository(BaseRepository[User]):
    """Repository for user CRUD operations with backward compatibility."""

    def __init__(self, database: Database):
        """
        Initialize user repository.

        Args:
            database: Database instance
        """
        super().__init__(database)
        self._read_repo = UserReadRepository(database)
        self._write_repo = UserWriteRepository(database)

    # Read operations - delegate to UserReadRepository
    def _row_to_user(self, row: Any):
        """Convert database row to User entity."""
        return self._read_repo._row_to_user(row)

    async def get_by_id(self, id: int) -> Optional[User]:
        """Get user by ID."""
        return await self._read_repo.get_by_id(id)

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return await self._read_repo.get_by_email(email)

    async def get_all(self, limit: int = 100, active_only: bool = False) -> List[User]:
        """Get all users."""
        return await self._read_repo.get_all(limit, active_only)

    async def get_all_active(self) -> List[Dict[str, Any]]:
        """Get all active users."""
        return await self._read_repo.get_all_active()

    async def get_by_id_with_password(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user with decrypted password for VFS login."""
        return await self._read_repo.get_by_id_with_password(user_id)

    async def get_all_active_with_passwords(self) -> List[Dict[str, Any]]:
        """Get all active users with decrypted passwords for VFS login."""
        return await self._read_repo.get_all_active_with_passwords()

    async def get_personal_details(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get personal details for a user."""
        return await self._read_repo.get_personal_details(user_id)

    async def get_personal_details_batch(self, user_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Get personal details for multiple users in a single query."""
        return await self._read_repo.get_personal_details_batch(user_ids)

    async def get_all_with_details(self) -> List[Dict[str, Any]]:
        """Get all users with their personal details joined."""
        return await self._read_repo.get_all_with_details()

    async def get_by_id_with_details(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get a single user with their personal details joined by user ID."""
        return await self._read_repo.get_by_id_with_details(user_id)

    async def get_active_count(self) -> int:
        """Get count of active users."""
        return await self._read_repo.get_active_count()

    # Write operations - delegate to UserWriteRepository
    async def create(self, data: Dict[str, Any]) -> int:
        """Create new user."""
        return await self._write_repo.create(data)

    async def update(self, id: int, data: Dict[str, Any]) -> bool:
        """Update user."""
        return await self._write_repo.update(id, data)

    async def add_personal_details(self, user_id: int, details: Dict[str, Any]) -> int:
        """Add personal details for a user."""
        return await self._write_repo.add_personal_details(user_id, details)

    async def update_personal_details(
        self,
        user_id: int,
        first_name: str | None = None,
        last_name: str | None = None,
        mobile_number: str | None = None,
        **other_fields: Any,
    ) -> bool:
        """Update personal details for a user with SQL injection protection."""
        return await self._write_repo.update_personal_details(
            user_id, first_name, last_name, mobile_number, **other_fields
        )

    async def create_batch(self, users: List[Dict[str, Any]]) -> List[int]:
        """Add multiple users in a single transaction for improved performance."""
        return await self._write_repo.create_batch(users)

    async def update_batch(self, updates: List[Dict[str, Any]]) -> int:
        """Update multiple users in a single transaction for improved performance."""
        return await self._write_repo.update_batch(updates)

    async def delete(self, id: int) -> bool:
        """Delete user (soft delete by setting is_active=False)."""
        return await self._write_repo.delete(id)

    async def hard_delete(self, id: int) -> bool:
        """Permanently delete user from database."""
        return await self._write_repo.hard_delete(id)
