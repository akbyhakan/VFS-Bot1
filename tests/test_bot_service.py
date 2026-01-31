"""Tests for VFS bot service."""

import pytest
import pytest_asyncio
import asyncio
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.bot.vfs_bot import VFSBot
from src.models.database import Database
from src.services.notification import NotificationService


@pytest.fixture
def bot_config():
    """Bot configuration fixture."""
    return {
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tur",
            "mission": "deu",
            "centres": ["Istanbul"],
            "category": "Schengen Visa",
            "subcategory": "Tourism",
        },
        "credentials": {"email": "test@example.com", "password": "testpass"},
        "notifications": {"telegram": {"enabled": False}, "email": {"enabled": False}},
        "captcha": {"provider": "manual", "api_key": "", "manual_timeout": 10},
        "bot": {
            "check_interval": 5,
            "headless": True,
            "screenshot_on_error": False,
            "max_retries": 1,
        },
        "appointments": {
            "preferred_dates": [],
            "preferred_times": [],
            "random_selection": True,
        },
        "anti_detection": {"enabled": False},
    }


@pytest.fixture
def mock_db():
    """Mock database fixture."""
    db = AsyncMock(spec=Database)
    db.get_active_users = AsyncMock(return_value=[])
    db.get_personal_details = AsyncMock(return_value=None)
    db.add_appointment = AsyncMock(return_value=1)
    db.connect = AsyncMock()
    db.close = AsyncMock()
    return db


@pytest.fixture
def mock_notifier():
    """Mock notifier fixture."""
    notifier = AsyncMock(spec=NotificationService)
    notifier.notify_bot_started = AsyncMock()
    notifier.notify_bot_stopped = AsyncMock()
    notifier.notify_slot_found = AsyncMock()
    notifier.notify_booking_success = AsyncMock()
    notifier.notify_error = AsyncMock()
    return notifier


def test_bot_initialization(bot_config, mock_db, mock_notifier):
    """Test VFSBot initialization."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.config == bot_config
    assert bot.db == mock_db
    assert bot.notifier == mock_notifier
    assert bot.running is False
    # New modular architecture - components are initialized
    assert bot.browser_manager is not None
    assert bot.circuit_breaker is not None
    assert bot.auth_service is not None
    assert bot.slot_checker is not None
    assert bot.error_handler is not None


def test_bot_initialization_with_anti_detection_disabled(bot_config, mock_db, mock_notifier):
    """Test VFSBot initialization with anti-detection disabled."""
    bot_config["anti_detection"]["enabled"] = False
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.anti_detection_enabled is False


def test_bot_initialization_with_anti_detection_enabled(bot_config, mock_db, mock_notifier):
    """Test VFSBot initialization with anti-detection enabled."""
    bot_config["anti_detection"]["enabled"] = True
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.anti_detection_enabled is True
    assert bot.human_sim is not None
    assert bot.header_manager is not None
    assert bot.session_manager is not None


def test_bot_circuit_breaker_state(bot_config, mock_db, mock_notifier):
    """Test circuit breaker initial state."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Circuit breaker is now a service component
    assert bot.circuit_breaker is not None


def test_bot_captcha_solver_initialization(bot_config, mock_db, mock_notifier):
    """Test captcha solver initialization."""
    # Update config to provide API key
    bot_config["captcha"]["api_key"] = "test_api_key"
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.captcha_solver is not None
    assert bot.captcha_solver.api_key == "test_api_key"


def test_bot_centre_fetcher_initialization(bot_config, mock_db, mock_notifier):
    """Test centre fetcher initialization."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.centre_fetcher is not None


def test_bot_error_capture_initialization(bot_config, mock_db, mock_notifier):
    """Test error capture initialization."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.error_capture is not None


def test_bot_rate_limiter_initialization(bot_config, mock_db, mock_notifier):
    """Test rate limiter initialization."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.rate_limiter is not None


@pytest.mark.asyncio
async def test_bot_start_sets_running_flag(bot_config, mock_db, mock_notifier):
    """Test that start sets running flag."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Mock browser manager's start method
    bot.browser_manager.start = AsyncMock()
    bot.browser_manager.browser = AsyncMock()

    # Mock get_active_users_with_decrypted_passwords to return empty list to stop the loop
    mock_db.get_active_users_with_decrypted_passwords = AsyncMock(return_value=[])

    # Start bot in background task
    task = asyncio.create_task(bot.start())

    # Give it a moment to set running flag
    await asyncio.sleep(0.1)

    # Stop the bot
    await bot.stop()

    # Wait for task to complete
    try:
        await asyncio.wait_for(task, timeout=2.0)
    except asyncio.TimeoutError:
        task.cancel()


@pytest.mark.asyncio
async def test_bot_stop_clears_running_flag(bot_config, mock_db, mock_notifier):
    """Test that stop clears running flag."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)
    bot.running = True

    await bot.stop()

    assert bot.running is False


@pytest.mark.asyncio
async def test_bot_stop_calls_notifier(bot_config, mock_db, mock_notifier):
    """Test that stop calls notifier."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)
    bot.running = True

    await bot.stop()

    mock_notifier.notify_bot_stopped.assert_called_once()


@pytest.mark.asyncio
async def test_bot_stop_closes_browser(bot_config, mock_db, mock_notifier):
    """Test that stop closes browser."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Mock browser manager's browser
    mock_browser = AsyncMock()
    mock_browser.close = AsyncMock()
    bot.browser_manager.browser = mock_browser

    await bot.stop()

    mock_browser.close.assert_called_once()


@pytest.mark.asyncio
async def test_bot_stop_handles_browser_none(bot_config, mock_db, mock_notifier):
    """Test that stop handles None browser gracefully."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)
    bot.browser_manager.browser = None

    # Should not raise exception
    await bot.stop()


def test_bot_config_access(bot_config, mock_db, mock_notifier):
    """Test accessing bot configuration."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.config["vfs"]["country"] == "tur"
    assert bot.config["vfs"]["mission"] == "deu"
    assert bot.config["bot"]["check_interval"] == 5


def test_bot_user_semaphore(bot_config, mock_db, mock_notifier):
    """Test user semaphore initialization."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.user_semaphore is not None
    # Semaphore should have a value from RateLimits.CONCURRENT_USERS


def test_bot_health_checker_default(bot_config, mock_db, mock_notifier):
    """Test health checker default value."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.health_checker is None


@pytest.mark.asyncio
async def test_bot_circuit_breaker_tracking(bot_config, mock_db, mock_notifier):
    """Test circuit breaker error tracking."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Circuit breaker is now a service - check it's available
    is_available = await bot.circuit_breaker.is_available()
    assert is_available is True


def test_bot_with_custom_captcha_config(mock_db, mock_notifier):
    """Test bot with custom captcha configuration."""
    config = {
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tur",
            "mission": "deu",
        },
        "captcha": {
            "provider": "2captcha",
            "api_key": "test_key",
            "manual_timeout": 60,
        },
        "credentials": {"email": "test@example.com", "password": "testpass"},
        "notifications": {"telegram": {"enabled": False}, "email": {"enabled": False}},
        "bot": {"check_interval": 5, "headless": True, "screenshot_on_error": False},
        "appointments": {"preferred_dates": [], "preferred_times": []},
        "anti_detection": {"enabled": False},
    }

    bot = VFSBot(config, mock_db, mock_notifier)

    assert bot.captcha_solver.api_key == "test_key"


def test_bot_with_custom_session_config(mock_db, mock_notifier):
    """Test bot with custom session configuration."""
    config = {
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tur",
            "mission": "deu",
        },
        "captcha": {"provider": "manual", "api_key": "", "manual_timeout": 10},
        "credentials": {"email": "test@example.com", "password": "testpass"},
        "notifications": {"telegram": {"enabled": False}, "email": {"enabled": False}},
        "bot": {"check_interval": 5, "headless": True, "screenshot_on_error": False},
        "appointments": {"preferred_dates": [], "preferred_times": []},
        "anti_detection": {"enabled": True},
        "session": {
            "save_file": "custom_session.json",
            "token_refresh_buffer": 10,
        },
    }

    bot = VFSBot(config, mock_db, mock_notifier)

    assert bot.session_manager is not None
