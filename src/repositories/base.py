"""Base repository class."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic
from src.models.database import Database

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """Base repository with common CRUD operations."""

    def __init__(self, database: Database):
        """
        Initialize repository with database connection.

        Args:
            database: Database instance
        """
        self.db = database

    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[T]:
        """
        Get entity by ID.

        Args:
            id: Entity ID

        Returns:
            Entity or None if not found
        """
        pass

    @abstractmethod
    async def get_all(self, limit: int = 100) -> List[T]:
        """
        Get all entities.

        Args:
            limit: Maximum number of entities to return

        Returns:
            List of entities
        """
        pass

    @abstractmethod
    async def create(self, data: Dict[str, Any]) -> int:
        """
        Create new entity.

        Args:
            data: Entity data

        Returns:
            Created entity ID
        """
        pass

    @abstractmethod
    async def update(self, id: int, data: Dict[str, Any]) -> bool:
        """
        Update entity.

        Args:
            id: Entity ID
            data: Update data

        Returns:
            True if updated, False otherwise
        """
        pass

    @abstractmethod
    async def delete(self, id: int) -> bool:
        """
        Delete entity.

        Args:
            id: Entity ID

        Returns:
            True if deleted, False otherwise
        """
        pass
