"""Integration tests for bot functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import LoginError, SelectorNotFoundError
from src.services.bot.vfs_bot import VFSBot


@pytest.mark.asyncio
async def test_bot_initialization(config, mock_db, mock_notifier):
    """Test bot initialization."""
    bot = VFSBot(config, mock_db, mock_notifier)

    assert bot.config == config
    assert bot.running is False
    assert bot.db == mock_db
    assert bot.notifier == mock_notifier


@pytest.mark.asyncio
async def test_login_success(mock_page, config, mock_db, mock_notifier):
    """Test successful login flow."""
    bot = VFSBot(config, mock_db, mock_notifier)

    # Mock successful login redirect
    mock_page.url = "https://visa.vfsglobal.com/tur/deu/en/dashboard"
    mock_page.locator.return_value.count = AsyncMock(return_value=0)  # No captcha

    result = await bot.services.workflow.auth_service.login(
        mock_page, "test@example.com", "password"
    )

    assert result is True
    mock_page.goto.assert_called_once()
    mock_page.fill.assert_called()


@pytest.mark.asyncio
async def test_login_failure_wrong_credentials(mock_page, config, mock_db, mock_notifier):
    """Test login failure with wrong credentials."""
    bot = VFSBot(config, mock_db, mock_notifier)

    # Mock failed login - stays on login page
    mock_page.url = "https://visa.vfsglobal.com/tur/deu/en/login"
    mock_page.locator.return_value.count = AsyncMock(return_value=0)

    result = await bot.services.workflow.auth_service.login(
        mock_page, "wrong@example.com", "wrongpass"
    )

    assert result is False


@pytest.mark.asyncio
async def test_check_slots_available(mock_page, config, mock_db, mock_notifier):
    """Test slot checking when slots are available."""
    bot = VFSBot(config, mock_db, mock_notifier)

    # Mock available slots
    mock_locator = MagicMock()
    mock_locator.count = AsyncMock(return_value=1)

    mock_first = MagicMock()
    mock_first.text_content = AsyncMock(side_effect=["2024-02-15", "10:00"])

    mock_page.locator.return_value = mock_locator
    mock_page.locator.return_value.first = mock_first

    slot = await bot.services.workflow.slot_checker.check_slots(
        mock_page, "Istanbul", "Schengen Visa", "Tourism"
    )

    assert slot is not None
    assert slot["date"] == "2024-02-15"
    assert slot["time"] == "10:00"


@pytest.mark.asyncio
async def test_check_slots_not_available(mock_page, config, mock_db, mock_notifier):
    """Test slot checking when no slots available."""
    bot = VFSBot(config, mock_db, mock_notifier)

    # Mock no available slots
    mock_locator = MagicMock()
    mock_locator.count = AsyncMock(return_value=0)
    mock_page.locator.return_value = mock_locator

    slot = await bot.services.workflow.slot_checker.check_slots(
        mock_page, "Istanbul", "Schengen Visa", "Tourism"
    )

    assert slot is None


@pytest.mark.asyncio
async def test_build_reservation(config, mock_db, mock_notifier):
    """Test building reservation data structure from user, slot, and details."""
    bot = VFSBot(config, mock_db, mock_notifier)

    user = {
        "id": 1,
        "email": "test@example.com",
        "centre": "Istanbul",
        "category": "Schengen Visa",
    }

    slot = {"date": "15/02/2024", "time": "10:00"}

    details = {
        "first_name": "John",
        "last_name": "Doe",
        "gender": "male",
        "date_of_birth": "01/01/1990",
        "passport_number": "AB123456",
        "passport_expiry": "01/01/2030",
        "mobile_code": "90",
        "mobile_number": "5551234567",
        "email": "test@example.com",
    }

    # Build reservation
    reservation = bot.booking_workflow._build_reservation(user, slot, details)

    # Verify reservation structure
    assert reservation["person_count"] == 1
    assert reservation["preferred_dates"] == ["15/02/2024"]
    assert len(reservation["persons"]) == 1

    person = reservation["persons"][0]
    assert person["first_name"] == "John"
    assert person["last_name"] == "Doe"
    assert person["gender"] == "male"
    assert person["birth_date"] == "01/01/1990"
    assert person["passport_number"] == "AB123456"
    assert person["passport_expiry_date"] == "01/01/2030"
    assert person["phone_code"] == "90"
    assert person["phone_number"] == "5551234567"
    assert person["email"] == "test@example.com"
    assert person["is_child_with_parent"] is False


@pytest.mark.asyncio
async def test_process_user_with_slot_found(config, mock_db, mock_notifier):
    """Test processing user when slot is found and booking succeeds."""
    bot = VFSBot(config, mock_db, mock_notifier)

    user = {
        "id": 1,
        "email": "test@example.com",
        "password": "testpass",
        "centre": "Istanbul",
        "category": "Schengen Visa",
        "subcategory": "Tourism",
    }

    # Mock browser manager
    mock_page = AsyncMock()
    bot.browser_manager.new_page = AsyncMock(return_value=mock_page)

    # Mock successful flow
    with (
        patch.object(bot.services.workflow.auth_service, "login", return_value=True),
        patch.object(
            bot.services.workflow.slot_checker,
            "check_slots",
            return_value={"date": "15/02/2024", "time": "10:00"},
        ),
        patch.object(bot.services.workflow.booking_service, "run_booking_flow", return_value=True),
        patch.object(
            bot.services.workflow.booking_service,
            "verify_booking_confirmation",
            return_value={"success": True, "reference": "REF-123456"},
        ),
        patch.object(
            bot.services.workflow.waitlist_handler, "detect_waitlist_mode", return_value=False
        ),
    ):
        mock_db.get_personal_details.return_value = {
            "first_name": "John",
            "last_name": "Doe",
            "passport_number": "AB123456",
            "passport_expiry": "01/01/2030",
            "gender": "male",
            "date_of_birth": "01/01/1990",
            "mobile_code": "90",
            "mobile_number": "5551234567",
            "email": "test@example.com",
        }

        await bot.booking_workflow.process_user(mock_page, user)

        # Verify notifications were sent
        mock_notifier.notify_slot_found.assert_called_once()
        mock_notifier.notify_booking_success.assert_called_once()
        mock_db.add_appointment.assert_called_once()


@pytest.mark.asyncio
async def test_process_user_login_failure(config, mock_db, mock_notifier):
    """Test processing user when login fails."""
    bot = VFSBot(config, mock_db, mock_notifier)

    user = {
        "id": 1,
        "email": "test@example.com",
        "password": "wrongpass",
        "centre": "Istanbul",
        "category": "Schengen Visa",
        "subcategory": "Tourism",
    }

    # Mock browser manager
    mock_page = AsyncMock()
    bot.browser_manager.new_page = AsyncMock(return_value=mock_page)

    # Mock failed login
    with patch.object(bot.services.workflow.auth_service, "login", return_value=False):
        await bot.booking_workflow.process_user(mock_page, user)

        # Verify check_slots was not called
        mock_notifier.notify_slot_found.assert_not_called()


@pytest.mark.asyncio
async def test_take_screenshot(mock_page, config, mock_db, mock_notifier, tmp_path):
    """Test taking screenshot on error."""
    bot = VFSBot(config, mock_db, mock_notifier)

    with patch("pathlib.Path.mkdir"):
        await bot.services.workflow.error_handler.take_screenshot(mock_page, "test_error")

        mock_page.screenshot.assert_called_once()
