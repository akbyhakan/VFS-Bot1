"""Repository pattern implementation."""

from .base import BaseRepository
from .user_repository import UserRepository, User

__all__ = ["BaseRepository", "UserRepository", "User"]
