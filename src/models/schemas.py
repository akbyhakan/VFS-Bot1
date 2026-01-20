"""Pydantic models for data validation."""

from pydantic import BaseModel, Field
from typing import Optional, List, TypedDict
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


# TypedDict definitions for type-safe configuration


class TelegramConfig(TypedDict, total=False):
    """Telegram notification configuration."""

    enabled: bool
    bot_token: str
    chat_id: str


class EmailConfig(TypedDict, total=False):
    """Email notification configuration."""

    enabled: bool
    smtp_server: str
    smtp_port: int
    sender: str
    password: str
    receiver: str


class NotificationConfigTyped(TypedDict, total=False):
    """Complete notification configuration with type safety."""

    telegram: TelegramConfig
    email: EmailConfig


class VFSConfigTyped(TypedDict, total=False):
    """VFS bot configuration with type safety."""

    base_url: str
    country: str
    language: str
    mission: str
    centres: List[str]
    category: str
    subcategory: str


class BotConfigTyped(TypedDict, total=False):
    """Bot runtime configuration with type safety."""

    check_interval: int
    max_retries: int
    headless: bool
    auto_book: bool
    timeout: int


class DatabaseConfigTyped(TypedDict, total=False):
    """Database configuration with type safety."""

    path: str
    pool_size: int
    connection_timeout: float


class SecurityConfigTyped(TypedDict, total=False):
    """Security configuration with type safety."""

    api_secret_key: str
    api_key_salt: str
    encryption_key: str
    jwt_algorithm: str
    jwt_expiration_minutes: int


class ProxyConfigTyped(TypedDict, total=False):
    """Proxy configuration with type safety."""

    enabled: bool
    server: str
    username: str
    password: str
