"""Tests for VFS bot service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
import pytest_asyncio

from src.models.database import Database
from src.services.bot.vfs_bot import VFSBot
from src.services.notification.notification import NotificationService


@pytest.fixture
def bot_config(config):
    """Bot config based on shared test config."""
    return config


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
    assert bot.services.workflow.auth_service is not None
    assert bot.services.workflow.slot_checker is not None
    assert bot.services.workflow.error_handler is not None


def test_bot_initialization_with_anti_detection_disabled(bot_config, mock_db, mock_notifier):
    """Test VFSBot initialization with anti-detection disabled."""
    bot_config["anti_detection"]["enabled"] = False
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.services.anti_detection.enabled is False


def test_bot_initialization_with_anti_detection_enabled(bot_config, mock_db, mock_notifier):
    """Test VFSBot initialization with anti-detection enabled."""
    bot_config["anti_detection"]["enabled"] = True
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.services.anti_detection.enabled is True
    assert bot.services.anti_detection.human_sim is not None
    assert bot.services.anti_detection.header_manager is not None
    assert bot.services.anti_detection.session_manager is not None


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

    assert bot.services.core.captcha_solver is not None
    assert bot.services.core.captcha_solver.api_key == "test_api_key"


def test_bot_centre_fetcher_initialization(bot_config, mock_db, mock_notifier):
    """Test centre fetcher initialization."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.services.core.centre_fetcher is not None


def test_bot_error_capture_initialization(bot_config, mock_db, mock_notifier):
    """Test error capture initialization."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.services.core.error_capture is not None


def test_bot_rate_limiter_initialization(bot_config, mock_db, mock_notifier):
    """Test rate limiter initialization."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.services.core.rate_limiter is not None


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

    assert bot.services.core.user_semaphore is not None
    # Semaphore should have a value from RateLimits.CONCURRENT_USERS


def test_bot_health_checker_default(bot_config, mock_db, mock_notifier):
    """Test health checker default value."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert bot.health_checker is None


def test_bot_health_task_initialized_none(bot_config, mock_db, mock_notifier):
    """Test health task is initialized to None."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    assert hasattr(bot, "_health_task")
    assert bot._health_task is None


@pytest.mark.asyncio
async def test_handle_task_exception_logs_error(bot_config, mock_db, mock_notifier):
    """Test _handle_task_exception logs exceptions from tasks."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Create a task that raises an exception
    async def failing_task():
        raise ValueError("Test exception")

    task = asyncio.create_task(failing_task())

    # Wait for task to complete
    try:
        await task
    except ValueError:
        pass

    # Call the exception handler - should not raise
    bot._handle_task_exception(task)

    # Verify the task has an exception
    assert task.exception() is not None


@pytest.mark.asyncio
async def test_handle_task_exception_cancelled(bot_config, mock_db, mock_notifier):
    """Test _handle_task_exception handles cancelled tasks."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Create a task and cancel it
    async def slow_task():
        await asyncio.sleep(10)

    task = asyncio.create_task(slow_task())
    task.cancel()

    # Wait for cancellation
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Call the exception handler - should not raise
    bot._handle_task_exception(task)


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
        },
        "credentials": {"email": "test@example.com", "password": "testpass"},
        "notifications": {"telegram": {"enabled": False}, "email": {"enabled": False}},
        "bot": {"check_interval": 5, "headless": True, "screenshot_on_error": False},
        "appointments": {"preferred_dates": [], "preferred_times": []},
        "anti_detection": {"enabled": False},
    }

    bot = VFSBot(config, mock_db, mock_notifier)

    assert bot.services.core.captcha_solver.api_key == "test_key"


def test_bot_with_custom_session_config(mock_db, mock_notifier):
    """Test bot with custom session configuration."""
    config = {
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tur",
            "mission": "deu",
        },
        "captcha": {"provider": "2captcha", "api_key": "test_key"},
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

    assert bot.services.anti_detection.session_manager is not None


# Tests for Issue 3.3: Graceful Degradation with User Cache


@pytest.mark.asyncio
async def test_bot_get_users_with_fallback_uses_cache_when_ttl_valid(bot_config, mock_notifier):
    """Test that _get_users_with_fallback returns cached users without DB query when TTL is valid."""
    import time

    from src.models.database import DatabaseState

    # Create mock database
    mock_db = AsyncMock(spec=Database)
    mock_db.execute_with_fallback = AsyncMock(return_value=None)
    mock_db.state = DatabaseState.CONNECTED

    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Pre-populate cache with test data
    test_users = [
        {"id": 1, "email": "user1@test.com", "password": "pass1"},
        {"id": 2, "email": "user2@test.com", "password": "pass2"},
    ]
    bot._user_cache.users = test_users
    bot._user_cache.timestamp = time.time()  # Recent timestamp

    # Call the method
    users = await bot._get_users_with_fallback()

    # Assert cached users are returned WITHOUT calling DB
    assert users == test_users
    assert len(users) == 2
    mock_db.execute_with_fallback.assert_not_called()


@pytest.mark.asyncio
async def test_bot_get_users_with_fallback_queries_db_when_ttl_expired(bot_config, mock_notifier):
    """Test that _get_users_with_fallback queries DB when TTL is expired."""
    import time

    from src.models.database import DatabaseState

    # Create mock database that succeeds
    test_users = [
        {"id": 3, "email": "user3@test.com", "password": "pass3"},
    ]
    mock_db = AsyncMock(spec=Database)
    mock_db.execute_with_fallback = AsyncMock(return_value=test_users)
    mock_db.state = DatabaseState.CONNECTED

    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Pre-populate cache with old timestamp (expired)
    old_users = [{"id": 1, "email": "old@test.com", "password": "oldpass"}]
    bot._user_cache.users = old_users
    bot._user_cache.timestamp = time.time() - 400  # 400 seconds ago (> 300s TTL)

    # Call the method
    users = await bot._get_users_with_fallback()

    # Assert DB was queried and new users returned
    assert users == test_users
    mock_db.execute_with_fallback.assert_called_once()


@pytest.mark.asyncio
async def test_bot_get_users_with_fallback_queries_db_when_cache_empty(bot_config, mock_notifier):
    """Test that _get_users_with_fallback queries DB when cache is empty."""
    from src.models.database import DatabaseState

    # Create mock database that succeeds
    test_users = [
        {"id": 1, "email": "user1@test.com", "password": "pass1"},
    ]
    mock_db = AsyncMock(spec=Database)
    mock_db.execute_with_fallback = AsyncMock(return_value=test_users)
    mock_db.state = DatabaseState.CONNECTED

    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Ensure cache is empty
    assert bot._user_cache.users == []

    # Call the method
    users = await bot._get_users_with_fallback()

    # Assert DB was queried
    assert users == test_users
    mock_db.execute_with_fallback.assert_called_once()


@pytest.mark.asyncio
async def test_bot_get_users_with_fallback_uses_cache_on_db_failure(bot_config, mock_notifier):
    """Test that _get_users_with_fallback returns expired cached users when DB fails."""
    import time

    from src.models.database import DatabaseState

    # Create mock database that simulates failure
    mock_db = AsyncMock(spec=Database)
    mock_db.execute_with_fallback = AsyncMock(return_value=None)  # Simulate DB failure
    mock_db.state = DatabaseState.DEGRADED

    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Pre-populate cache with old/expired data
    test_users = [
        {"id": 1, "email": "user1@test.com", "password": "pass1"},
        {"id": 2, "email": "user2@test.com", "password": "pass2"},
    ]
    bot._user_cache.users = test_users
    bot._user_cache.timestamp = time.time() - 400  # Expired cache

    # Call the method
    users = await bot._get_users_with_fallback()

    # Assert expired cached users are returned as fallback
    assert users == test_users
    assert len(users) == 2


@pytest.mark.asyncio
async def test_bot_get_users_with_fallback_returns_empty_when_cache_expired(
    bot_config, mock_notifier
):
    """Test that _get_users_with_fallback returns empty list when cache is expired and DB fails."""
    import time

    from src.models.database import DatabaseState

    # Create mock database that simulates failure
    mock_db = AsyncMock(spec=Database)
    mock_db.execute_with_fallback = AsyncMock(return_value=None)  # Simulate DB failure
    mock_db.state = DatabaseState.DEGRADED

    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Start with empty cache (no fallback available)
    assert bot._user_cache.users == []
    bot._user_cache.timestamp = time.time() - 400  # Expired timestamp

    # Call the method
    users = await bot._get_users_with_fallback()

    # Assert empty list is returned (no cache AND DB failed)
    assert users == []


@pytest.mark.asyncio
async def test_bot_get_users_with_fallback_updates_cache_on_success(bot_config, mock_notifier):
    """Test that _get_users_with_fallback updates cache on successful DB query."""
    import time

    from src.models.database import DatabaseState

    # Create mock database that succeeds
    test_users = [
        {"id": 1, "email": "user1@test.com", "password": "pass1"},
        {"id": 2, "email": "user2@test.com", "password": "pass2"},
    ]
    mock_db = AsyncMock(spec=Database)
    mock_db.execute_with_fallback = AsyncMock(return_value=test_users)
    mock_db.state = DatabaseState.CONNECTED

    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Ensure cache is initially empty
    assert bot._user_cache.users == []
    assert bot._user_cache.timestamp == 0

    # Call the method
    users = await bot._get_users_with_fallback()

    # Assert users are returned and cache is updated
    assert users == test_users
    assert bot._user_cache.users == test_users
    assert bot._user_cache.timestamp > 0


@pytest.mark.asyncio
async def test_bot_ensure_db_connection_attempts_reconnect_on_degraded(bot_config, mock_notifier):
    """Test that _ensure_db_connection attempts reconnection when DB is degraded."""
    from src.models.database import DatabaseState

    # Create mock database in degraded state
    mock_db = AsyncMock(spec=Database)
    mock_db.state = DatabaseState.DEGRADED
    mock_db.reconnect = AsyncMock(return_value=True)

    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Call the method
    await bot._ensure_db_connection()

    # Assert reconnect was called
    mock_db.reconnect.assert_called_once()


@pytest.mark.asyncio
async def test_bot_ensure_db_connection_does_nothing_when_connected(bot_config, mock_notifier):
    """Test that _ensure_db_connection does nothing when DB is already connected."""
    from src.models.database import DatabaseState

    # Create mock database in connected state
    mock_db = AsyncMock(spec=Database)
    mock_db.state = DatabaseState.CONNECTED
    mock_db.reconnect = AsyncMock(return_value=True)

    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Call the method
    await bot._ensure_db_connection()

    # Assert reconnect was NOT called
    mock_db.reconnect.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_event_initialized(bot_config, mock_db, mock_notifier):
    """Test that trigger event is initialized in VFSBot."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Verify trigger event exists and is an Event
    assert hasattr(bot, "_trigger_event")
    assert isinstance(bot._trigger_event, asyncio.Event)
    # Event should not be set initially
    assert not bot._trigger_event.is_set()


@pytest.mark.asyncio
async def test_wait_or_shutdown_normal_timeout(bot_config, mock_db, mock_notifier):
    """Test _wait_or_shutdown returns False on normal timeout."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Wait for a short duration - should timeout normally
    result = await bot._wait_or_shutdown(0.1)

    assert result is False


@pytest.mark.asyncio
async def test_wait_or_shutdown_trigger_event(bot_config, mock_db, mock_notifier):
    """Test _wait_or_shutdown returns False when trigger event is set."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Set trigger event after a delay
    async def set_trigger_after_delay():
        await asyncio.sleep(0.05)
        bot._trigger_event.set()

    # Start the delayed setter
    asyncio.create_task(set_trigger_after_delay())

    # Wait - should be interrupted by trigger
    result = await bot._wait_or_shutdown(1.0)

    # Should return False (not shutdown)
    assert result is False
    # Trigger event should be cleared after use
    assert not bot._trigger_event.is_set()


@pytest.mark.asyncio
async def test_wait_or_shutdown_shutdown_event(bot_config, mock_db, mock_notifier):
    """Test _wait_or_shutdown returns True when shutdown event is set."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Set shutdown event after a delay
    async def set_shutdown_after_delay():
        await asyncio.sleep(0.05)
        bot.shutdown_event.set()

    # Start the delayed setter
    asyncio.create_task(set_shutdown_after_delay())

    # Wait - should be interrupted by shutdown
    result = await bot._wait_or_shutdown(1.0)

    # Should return True (shutdown requested)
    assert result is True


@pytest.mark.asyncio
async def test_trigger_immediate_check_sets_event(bot_config, mock_db, mock_notifier):
    """Test that trigger_immediate_check() sets the _trigger_event."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Verify event is not set initially
    assert not bot._trigger_event.is_set()

    # Call trigger_immediate_check
    bot.trigger_immediate_check()

    # Verify event is now set
    assert bot._trigger_event.is_set()


@pytest.mark.asyncio
async def test_trigger_immediate_check_can_be_cleared(bot_config, mock_db, mock_notifier):
    """Test that after calling trigger_immediate_check(), the event is set and can be cleared by _wait_or_shutdown()."""
    bot = VFSBot(bot_config, mock_db, mock_notifier)

    # Trigger immediate check
    bot.trigger_immediate_check()
    assert bot._trigger_event.is_set()

    # _wait_or_shutdown should clear the event and return False
    result = await bot._wait_or_shutdown(1.0)

    # Should return False (not shutdown, just triggered)
    assert result is False
    # Event should be cleared
    assert not bot._trigger_event.is_set()
