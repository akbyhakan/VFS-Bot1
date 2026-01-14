"""Tests for Pydantic schemas."""

import pytest
from pathlib import Path
import sys
from datetime import datetime
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.schemas import (
    UserCreate,
    UserResponse,
    AppointmentCreate,
    AppointmentResponse,
    BotConfig,
    NotificationConfig,
)


def test_user_create_valid():
    """Test valid UserCreate schema."""
    user = UserCreate(
        email="test@example.com",
        password="securepass123",
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay",
    )

    assert user.email == "test@example.com"
    assert user.password == "securepass123"
    assert user.centre == "Istanbul"


def test_user_create_short_password():
    """Test UserCreate with password too short."""
    with pytest.raises(ValidationError):
        UserCreate(
            email="test@example.com",
            password="short",  # Less than 8 characters
            centre="Istanbul",
            category="Tourism",
            subcategory="Short Stay",
        )


def test_user_response_valid():
    """Test valid UserResponse schema."""
    now = datetime.now()
    user = UserResponse(
        id=1, email="test@example.com", centre="Istanbul", active=True, created_at=now
    )

    assert user.id == 1
    assert user.email == "test@example.com"
    assert user.active is True


def test_appointment_create_valid():
    """Test valid AppointmentCreate schema."""
    appt = AppointmentCreate(
        user_id=1,
        centre="Istanbul",
        category="Tourism",
        appointment_date="2024-01-15",
        appointment_time="10:00",
    )

    assert appt.user_id == 1
    assert appt.centre == "Istanbul"
    assert appt.appointment_date == "2024-01-15"


def test_appointment_create_optional_fields():
    """Test AppointmentCreate with optional fields as None."""
    appt = AppointmentCreate(user_id=1, centre="Istanbul", category="Tourism")

    assert appt.appointment_date is None
    assert appt.appointment_time is None


def test_appointment_response_valid():
    """Test valid AppointmentResponse schema."""
    now = datetime.now()
    appt = AppointmentResponse(
        id=1,
        user_id=1,
        centre="Istanbul",
        category="Tourism",
        appointment_date="2024-01-15",
        appointment_time="10:00",
        status="confirmed",
        created_at=now,
    )

    assert appt.id == 1
    assert appt.status == "confirmed"


def test_bot_config_defaults():
    """Test BotConfig with default values."""
    config = BotConfig()

    assert config.check_interval == 60
    assert config.max_retries == 3
    assert config.headless is True
    assert config.auto_book is False


def test_bot_config_custom_values():
    """Test BotConfig with custom values."""
    config = BotConfig(check_interval=120, max_retries=5, headless=False, auto_book=True)

    assert config.check_interval == 120
    assert config.max_retries == 5
    assert config.headless is False
    assert config.auto_book is True


def test_bot_config_validation_min():
    """Test BotConfig validation for minimum values."""
    with pytest.raises(ValidationError):
        BotConfig(check_interval=5)  # Less than 10

    with pytest.raises(ValidationError):
        BotConfig(max_retries=0)  # Less than 1


def test_bot_config_validation_max():
    """Test BotConfig validation for maximum values."""
    with pytest.raises(ValidationError):
        BotConfig(check_interval=5000)  # Greater than 3600

    with pytest.raises(ValidationError):
        BotConfig(max_retries=15)  # Greater than 10


def test_notification_config_defaults():
    """Test NotificationConfig with default values."""
    config = NotificationConfig()

    assert config.telegram_enabled is False
    assert config.email_enabled is False
    assert config.webhook_enabled is False
    assert config.webhook_url is None


def test_notification_config_custom_values():
    """Test NotificationConfig with custom values."""
    config = NotificationConfig(
        telegram_enabled=True,
        email_enabled=True,
        webhook_enabled=True,
        webhook_url="https://example.com/webhook",
    )

    assert config.telegram_enabled is True
    assert config.email_enabled is True
    assert config.webhook_enabled is True
    assert config.webhook_url == "https://example.com/webhook"


def test_user_create_model_dump():
    """Test UserCreate model_dump method."""
    user = UserCreate(
        email="test@example.com",
        password="securepass123",
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay",
    )

    data = user.model_dump()

    assert isinstance(data, dict)
    assert data["email"] == "test@example.com"
    assert data["password"] == "securepass123"


def test_user_response_config():
    """Test UserResponse Config settings."""
    now = datetime.now()
    user = UserResponse(
        id=1, email="test@example.com", centre="Istanbul", active=True, created_at=now
    )

    # Config should allow from_attributes
    assert user.model_config.get("from_attributes") is True


def test_appointment_response_config():
    """Test AppointmentResponse Config settings."""
    now = datetime.now()
    appt = AppointmentResponse(
        id=1,
        user_id=1,
        centre="Istanbul",
        category="Tourism",
        appointment_date="2024-01-15",
        appointment_time="10:00",
        status="confirmed",
        created_at=now,
    )

    # Config should allow from_attributes
    assert appt.model_config.get("from_attributes") is True
