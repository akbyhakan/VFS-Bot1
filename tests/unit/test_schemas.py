"""Tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from src.core.config.config_models import (
    BotConfig,
    NotificationConfig,
    TelegramConfig,
)
from web.models.appointments import (
    AppointmentPersonRequest,
    AppointmentRequestCreate,
    AppointmentRequestResponse,
)
from web.models.vfs_accounts import VFSAccountCreateRequest, VFSAccountModel


def _make_person(**kwargs):
    defaults = dict(
        first_name="Jane",
        last_name="Doe",
        gender="female",
        nationality="Turkey",
        birth_date="01/01/1990",
        passport_number="A1234567",
        passport_issue_date="01/01/2020",
        passport_expiry_date="01/01/2030",
        phone_code="90",
        phone_number="5001234567",
        email="jane@example.com",
    )
    defaults.update(kwargs)
    return AppointmentPersonRequest(**defaults)


def test_vfs_account_create_valid():
    """Test valid VFSAccountCreateRequest schema."""
    account = VFSAccountCreateRequest(
        email="test@example.com",
        password="securepass123",
        phone="5001234567",
    )

    assert account.email == "test@example.com"
    assert account.password == "securepass123"
    assert account.is_active is True


def test_vfs_account_create_invalid_email():
    """Test VFSAccountCreateRequest with invalid email."""
    with pytest.raises(ValidationError):
        VFSAccountCreateRequest(
            email="not-an-email",
            password="securepass123",
            phone="5001234567",
        )


def test_vfs_account_model_valid():
    """Test valid VFSAccountModel schema."""
    account = VFSAccountModel(
        id=1,
        email="test@example.com",
        phone="5001234567",
        is_active=True,
        created_at="2024-01-15T10:00:00",
        updated_at="2024-01-15T10:00:00",
    )

    assert account.id == 1
    assert account.email == "test@example.com"
    assert account.is_active is True


def test_vfs_account_create_model_dump():
    """Test VFSAccountCreateRequest model_dump method."""
    account = VFSAccountCreateRequest(
        email="test@example.com",
        password="securepass123",
        phone="5001234567",
    )

    data = account.model_dump()

    assert isinstance(data, dict)
    assert data["email"] == "test@example.com"
    assert data["password"] == "securepass123"


def test_appointment_request_create_valid():
    """Test valid AppointmentRequestCreate schema."""
    appt = AppointmentRequestCreate(
        country_code="TR",
        visa_category="Tourism",
        visa_subcategory="Short Stay",
        centres=["Istanbul"],
        preferred_dates=["15/01/2024"],
        person_count=1,
        persons=[_make_person()],
    )

    assert appt.country_code == "TR"
    assert appt.centres == ["Istanbul"]
    assert appt.preferred_dates == ["15/01/2024"]


def test_appointment_request_create_optional_fields():
    """Test AppointmentRequestCreate with multiple centres and dates."""
    appt = AppointmentRequestCreate(
        country_code="TR",
        visa_category="Tourism",
        visa_subcategory="Short Stay",
        centres=["Istanbul", "Ankara"],
        preferred_dates=[],
        person_count=1,
        persons=[_make_person()],
    )

    assert appt.preferred_dates == []
    assert len(appt.centres) == 2


def test_appointment_request_response_valid():
    """Test valid AppointmentRequestResponse schema."""
    appt = AppointmentRequestResponse(
        id=1,
        country_code="TR",
        visa_category="Tourism",
        visa_subcategory="Short Stay",
        centres=["Istanbul"],
        preferred_dates=["15/01/2024"],
        person_count=1,
        status="pending",
        created_at="2024-01-15T10:00:00",
        persons=[],
    )

    assert appt.id == 1
    assert appt.status == "pending"
    assert appt.completed_at is None


def test_appointment_request_response_completed_at():
    """Test AppointmentRequestResponse with completed_at set."""
    appt = AppointmentRequestResponse(
        id=2,
        country_code="TR",
        visa_category="Tourism",
        visa_subcategory="Short Stay",
        centres=["Istanbul"],
        preferred_dates=["15/01/2024"],
        person_count=1,
        status="confirmed",
        created_at="2024-01-15T10:00:00",
        completed_at="2024-01-16T10:00:00",
        persons=[],
    )

    assert appt.completed_at == "2024-01-16T10:00:00"


def test_bot_config_defaults():
    """Test BotConfig with default values."""
    config = BotConfig()

    assert config.check_interval == 30  # Updated default from config_models
    assert config.max_retries == 3
    assert config.headless is False  # Updated default from config_models
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

    assert config.telegram.enabled is False
    assert config.webhook_enabled is False
    assert config.webhook_url is None


def test_notification_config_custom_values():
    """Test NotificationConfig with custom values."""
    config = NotificationConfig(
        telegram=TelegramConfig(enabled=True, bot_token="test_token", chat_id="12345"),
        webhook_enabled=True,
        webhook_url="https://example.com/webhook",
    )

    assert config.telegram.enabled is True
    assert config.webhook_enabled is True
    assert config.webhook_url == "https://example.com/webhook"

