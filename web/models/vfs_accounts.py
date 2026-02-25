"""VFS Account models for VFS-Bot web application."""

from typing import Optional

from pydantic import BaseModel, EmailStr


class VFSAccountCreateRequest(BaseModel):
    """VFS Account creation request."""

    email: EmailStr
    password: str  # VFS password for login
    phone: str
    is_active: bool = True


class VFSAccountUpdateRequest(BaseModel):
    """VFS Account update request."""

    email: Optional[EmailStr] = None
    password: Optional[str] = None  # VFS password
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class VFSAccountModel(BaseModel):
    """VFS Account response model."""

    id: int
    email: EmailStr
    phone: str = ""
    is_active: bool
    created_at: str
    updated_at: str
