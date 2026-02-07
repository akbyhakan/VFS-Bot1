"""Tests for BotController singleton."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.bot_controller import BotController
from src.models.database import Database
from src.services.notification import NotificationService


@pytest_asyncio.fixture
async def database():
    """Create a test database."""
    db = Database("test_bot_controller.db")
    await db.connect()
    yield db
    await db.close()
    # Cleanup
    Path("test_bot_controller.db").unlink(missing_ok=True)


@pytest.fixture
def config():
    """Test configuration."""
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
        "appointments": {"preferred_dates": [], "preferred_times": [], "random_selection": True},
        "selector_health_check": {"enabled": False},
    }


@pytest_asyncio.fixture
async def notifier(config):
    """Create a test notification service."""
    return NotificationService(config["notifications"])


@pytest_asyncio.fixture(autouse=True)
async def reset_controller():
    """Reset BotController singleton before each test."""
    await BotController.reset_instance()
    yield
    await BotController.reset_instance()


@pytest.mark.asyncio
async def test_singleton_pattern():
    """Test that BotController follows singleton pattern."""
    controller1 = await BotController.get_instance()
    controller2 = await BotController.get_instance()
    assert controller1 is controller2


@pytest.mark.asyncio
async def test_initial_status_not_configured():
    """Test initial status before configuration."""
    controller = await BotController.get_instance()
    status = controller.get_status()
    assert status["status"] == "not_configured"
    assert status["running"] is False


@pytest.mark.asyncio
async def test_configure(config, database, notifier):
    """Test controller configuration."""
    controller = await BotController.get_instance()
    await controller.configure(config, database, notifier)
    status = controller.get_status()
    assert status["status"] == "stopped"
    assert status["running"] is False


@pytest.mark.asyncio
async def test_start_without_configure():
    """Test starting bot without configuration."""
    controller = await BotController.get_instance()
    result = await controller.start_bot()
    assert result["status"] == "error"
    assert "not configured" in result["message"].lower()


@pytest.mark.asyncio
@patch("src.core.bot_controller.VFSBot")
async def test_start_bot_success(mock_vfsbot, config, database, notifier):
    """Test successful bot start."""
    # Mock VFSBot
    mock_bot_instance = AsyncMock()
    mock_bot_instance.running = True
    mock_bot_instance.start = AsyncMock()
    mock_bot_instance.cleanup = AsyncMock()
    mock_vfsbot.return_value = mock_bot_instance

    controller = await BotController.get_instance()
    await controller.configure(config, database, notifier)

    result = await controller.start_bot()
    assert result["status"] == "success"
    assert result["message"] == "Bot started"
    assert controller.is_running is True

    # Clean up
    await controller.stop_bot()


@pytest.mark.asyncio
@patch("src.core.bot_controller.VFSBot")
async def test_start_bot_already_running(mock_vfsbot, config, database, notifier):
    """Test starting bot when already running."""
    # Mock VFSBot
    mock_bot_instance = AsyncMock()
    mock_bot_instance.running = True
    mock_bot_instance.start = AsyncMock()
    mock_bot_instance.stop = AsyncMock()
    mock_bot_instance.cleanup = AsyncMock()
    mock_vfsbot.return_value = mock_bot_instance

    controller = await BotController.get_instance()
    await controller.configure(config, database, notifier)

    # Start bot first time
    await controller.start_bot()

    # Try to start again
    result = await controller.start_bot()
    assert result["status"] == "error"
    assert "already running" in result["message"].lower()

    # Clean up
    await controller.stop_bot()


@pytest.mark.asyncio
@patch("src.core.bot_controller.VFSBot")
async def test_concurrent_start_guard(mock_vfsbot, config, database, notifier):
    """Test concurrent start protection."""
    # Mock VFSBot with slow start
    mock_bot_instance = AsyncMock()
    mock_bot_instance.running = True
    mock_bot_instance.cleanup = AsyncMock()

    async def slow_start():
        await asyncio.sleep(0.5)

    mock_bot_instance.start = AsyncMock(side_effect=slow_start)
    mock_bot_instance.stop = AsyncMock()
    mock_vfsbot.return_value = mock_bot_instance

    controller = await BotController.get_instance()
    await controller.configure(config, database, notifier)

    # Start two concurrent start operations
    task1 = asyncio.create_task(controller.start_bot())
    await asyncio.sleep(0.1)  # Small delay to ensure first task starts
    task2 = asyncio.create_task(controller.start_bot())

    result1, result2 = await asyncio.gather(task1, task2)

    # One should succeed, one should fail with "already starting"
    results = [result1, result2]
    success_count = sum(1 for r in results if r["status"] == "success")
    starting_count = sum(1 for r in results if "starting" in r.get("message", "").lower())

    assert success_count == 1
    assert starting_count == 1

    # Clean up
    await controller.stop_bot()


@pytest.mark.asyncio
async def test_stop_not_running(config, database, notifier):
    """Test stopping bot when not running."""
    controller = await BotController.get_instance()
    await controller.configure(config, database, notifier)

    result = await controller.stop_bot()
    assert result["status"] == "error"
    assert "not running" in result["message"].lower()


@pytest.mark.asyncio
@patch("src.core.bot_controller.VFSBot")
async def test_stop_bot_success(mock_vfsbot, config, database, notifier):
    """Test successful bot stop."""
    # Mock VFSBot
    mock_bot_instance = AsyncMock()
    mock_bot_instance.running = True
    mock_bot_instance.start = AsyncMock()
    mock_bot_instance.stop = AsyncMock()
    mock_bot_instance.cleanup = AsyncMock()
    mock_vfsbot.return_value = mock_bot_instance

    controller = await BotController.get_instance()
    await controller.configure(config, database, notifier)

    # Start and stop bot
    await controller.start_bot()
    result = await controller.stop_bot()

    assert result["status"] == "success"
    assert result["message"] == "Bot stopped"
    assert controller.is_running is False


@pytest.mark.asyncio
@patch("src.core.bot_controller.VFSBot")
async def test_restart_bot(mock_vfsbot, config, database, notifier):
    """Test bot restart."""
    # Mock VFSBot
    mock_bot_instance = AsyncMock()
    mock_bot_instance.running = True
    mock_bot_instance.start = AsyncMock()
    mock_bot_instance.stop = AsyncMock()
    mock_bot_instance.cleanup = AsyncMock()
    mock_vfsbot.return_value = mock_bot_instance

    controller = await BotController.get_instance()
    await controller.configure(config, database, notifier)

    # Start bot
    await controller.start_bot()

    # Restart bot
    result = await controller.restart_bot()

    assert result["status"] == "success"
    assert controller.is_running is True

    # Clean up
    await controller.stop_bot()


@pytest.mark.asyncio
async def test_trigger_check_now_not_running(config, database, notifier):
    """Test triggering check when bot not running."""
    controller = await BotController.get_instance()
    await controller.configure(config, database, notifier)

    result = await controller.trigger_check_now()
    assert result["status"] == "error"
    assert "not running" in result["message"].lower()


@pytest.mark.asyncio
@patch("src.core.bot_controller.VFSBot")
async def test_trigger_check_now_success(mock_vfsbot, config, database, notifier):
    """Test triggering manual check."""
    # Mock VFSBot
    mock_bot_instance = AsyncMock()
    mock_bot_instance.running = True
    mock_bot_instance.start = AsyncMock()
    mock_bot_instance.stop = AsyncMock()
    mock_bot_instance.cleanup = AsyncMock()
    mock_vfsbot.return_value = mock_bot_instance

    controller = await BotController.get_instance()
    await controller.configure(config, database, notifier)

    # Start bot and trigger check
    await controller.start_bot()
    result = await controller.trigger_check_now()

    assert result["status"] == "success"

    # Clean up
    await controller.stop_bot()


@pytest.mark.asyncio
@patch("src.core.bot_controller.VFSBot")
async def test_status_transitions(mock_vfsbot, config, database, notifier):
    """Test status transitions through bot lifecycle."""
    # Mock VFSBot
    mock_bot_instance = AsyncMock()
    mock_bot_instance.running = True
    mock_bot_instance.start = AsyncMock()
    mock_bot_instance.stop = AsyncMock()
    mock_bot_instance.cleanup = AsyncMock()
    mock_vfsbot.return_value = mock_bot_instance

    controller = await BotController.get_instance()

    # Initial: not_configured
    status = controller.get_status()
    assert status["status"] == "not_configured"

    # After configure: stopped
    await controller.configure(config, database, notifier)
    status = controller.get_status()
    assert status["status"] == "stopped"

    # After start: running
    await controller.start_bot()
    status = controller.get_status()
    assert status["status"] == "running"

    # After stop: stopped
    await controller.stop_bot()
    status = controller.get_status()
    assert status["status"] == "stopped"


@pytest.mark.asyncio
@patch("src.core.bot_controller.VFSBot")
async def test_error_handling_in_start(mock_vfsbot, config, database, notifier):
    """Test error handling during bot start."""
    # Mock VFSBot to raise exception
    mock_vfsbot.side_effect = Exception("Test error")

    controller = await BotController.get_instance()
    await controller.configure(config, database, notifier)

    result = await controller.start_bot()
    assert result["status"] == "error"
    assert "Failed to start bot" in result["message"]
    assert controller.is_running is False


@pytest.mark.asyncio
async def test_is_running_property(config, database, notifier):
    """Test is_running property."""
    controller = await BotController.get_instance()
    await controller.configure(config, database, notifier)

    # Initially not running
    assert controller.is_running is False

    # After failed start attempt
    result = await controller.start_bot()
    # Will fail because we haven't mocked VFSBot, but that's ok
    assert controller.is_running is False


@pytest.mark.asyncio
async def test_reset_instance():
    """Test reset_instance for testing."""
    controller1 = await BotController.get_instance()
    await BotController.reset_instance()
    controller2 = await BotController.get_instance()

    # Should be different instances after reset
    assert controller1 is not controller2
