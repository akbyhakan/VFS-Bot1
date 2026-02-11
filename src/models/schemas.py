"""Pydantic models for API data validation."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """User creation schema."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    centre: str
    category: str
    subcategory: str


class UserResponse(BaseModel):
    """User response schema."""

    id: int
    email: EmailStr
    centre: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AppointmentCreate(BaseModel):
    """Appointment creation schema."""

    user_id: int
    centre: str
    category: str
    appointment_date: str | None = None
    appointment_time: str | None = None


class AppointmentResponse(BaseModel):
    """Appointment response schema."""

    id: int
    user_id: int
    centre: str
    category: str
    appointment_date: str | None
    appointment_time: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
