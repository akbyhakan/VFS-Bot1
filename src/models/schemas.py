"""Pydantic models for data validation."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    """User creation schema."""

    email: str
    password: str = Field(..., min_length=8)
    centre: str
    category: str
    subcategory: str


class UserResponse(BaseModel):
    """User response schema."""

    id: int
    email: str
    centre: str
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AppointmentCreate(BaseModel):
    """Appointment creation schema."""

    user_id: int
    centre: str
    category: str
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None


class AppointmentResponse(BaseModel):
    """Appointment response schema."""

    id: int
    user_id: int
    centre: str
    category: str
    appointment_date: Optional[str]
    appointment_time: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class BotConfig(BaseModel):
    """Bot configuration schema."""

    check_interval: int = Field(default=60, ge=10, le=3600)
    max_retries: int = Field(default=3, ge=1, le=10)
    headless: bool = Field(default=True)
    auto_book: bool = Field(default=False)


class NotificationConfig(BaseModel):
    """Notification configuration schema."""

    telegram_enabled: bool = Field(default=False)
    email_enabled: bool = Field(default=False)
    webhook_enabled: bool = Field(default=False)
    webhook_url: Optional[str] = None
