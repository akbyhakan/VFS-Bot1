"""User models for VFS-Bot web application."""

from typing import Optional

from pydantic import BaseModel


class UserCreateRequest(BaseModel):
    """User creation request."""

    email: str
    password: str  # VFS password for login
    phone: str
    first_name: str
    last_name: str
    center_name: str
    visa_category: str
    visa_subcategory: str
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    """User update request."""

    email: Optional[str] = None
    password: Optional[str] = None  # VFS password
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    center_name: Optional[str] = None
    visa_category: Optional[str] = None
    visa_subcategory: Optional[str] = None
    is_active: Optional[bool] = None


class UserModel(BaseModel):
    """User response model."""

    id: int
    email: str
    phone: str = ""  # Default to empty string for backward compatibility
    first_name: str = ""  # Default to empty string for backward compatibility
    last_name: str = ""  # Default to empty string for backward compatibility
    center_name: str
    visa_category: str
    visa_subcategory: str
    is_active: bool
    created_at: str
    updated_at: str
