"""User model with role-based API mode support."""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserRole(str, Enum):
    """User roles."""
    ADMIN = "admin"
    USER = "user"
    TESTER = "tester"  # Test user - uses direct API


class UserSettings(BaseModel):
    """User-specific settings."""
    use_direct_api: bool = False  # Enable direct API usage
    preferred_language: str = "tr"
    notification_enabled: bool = True


class User(BaseModel):
    """User model."""
    id: str
    email: EmailStr
    password_hash: str
    role: UserRole = UserRole.USER
    settings: UserSettings = UserSettings()
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    is_active: bool = True
    
    @property
    def is_tester(self) -> bool:
        """Check if user is a tester (uses direct API)."""
        return self.role == UserRole.TESTER
    
    @property
    def uses_direct_api(self) -> bool:
        """Check if user should use direct API."""
        return self.role == UserRole.TESTER or self.settings.use_direct_api


class UserCreate(BaseModel):
    """User creation model."""
    email: EmailStr
    password: str
    role: UserRole = UserRole.USER


class UserResponse(BaseModel):
    """User response model (without sensitive data)."""
    id: str
    email: EmailStr
    role: UserRole
    is_tester: bool
    uses_direct_api: bool
    created_at: datetime
    
    class Config:
        from_attributes = True
