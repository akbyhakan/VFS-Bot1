"""User repository implementation."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from src.repositories.base import BaseRepository
from src.models.database import Database
from src.core.exceptions import ValidationError, RecordNotFoundError
from src.utils.validators import validate_email, validate_phone

logger = logging.getLogger(__name__)


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
            center_name=row["center_name"],
            visa_category=row["visa_category"],
            visa_subcategory=row["visa_subcategory"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
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
            cursor = await conn.execute(
                """
                SELECT id, email, phone, first_name, last_name, center_name,
                       visa_category, visa_subcategory, is_active, created_at, updated_at
                FROM users
                WHERE id = ?
                """,
                (id,),
            )
            row = await cursor.fetchone()
            
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
            cursor = await conn.execute(
                """
                SELECT id, email, phone, first_name, last_name, center_name,
                       visa_category, visa_subcategory, is_active, created_at, updated_at
                FROM users
                WHERE email = ?
                """,
                (email,),
            )
            row = await cursor.fetchone()
            
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
            query += " WHERE is_active = 1"
        
        query += " ORDER BY created_at DESC LIMIT ?"
        
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(query, (limit,))
            rows = await cursor.fetchall()
            
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
        
        # Use database's create_user method for consistency
        user_id = await self.db.create_user(
            email=data["email"],
            password=data.get("password", ""),
            phone=data.get("phone", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            center_name=data["center_name"],
            visa_category=data.get("visa_category", ""),
            visa_subcategory=data.get("visa_subcategory", ""),
            is_active=data.get("is_active", True),
        )
        
        logger.info(f"Created user {user_id} with email {data['email']}")
        return user_id
    
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
        
        # Validate phone if provided
        if "phone" in data and data["phone"] and not validate_phone(data["phone"]):
            raise ValidationError("Invalid phone format", field="phone")
        
        # Use database's update_user method for consistency
        success = await self.db.update_user(id, data)
        
        if success:
            logger.info(f"Updated user {id}")
        
        return success
    
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
            cursor = await conn.execute("DELETE FROM users WHERE id = ?", (id,))
            await conn.commit()
            
            deleted = cursor.rowcount > 0
            
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
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM users WHERE is_active = 1"
            )
            row = await cursor.fetchone()
            return row[0] if row else 0
