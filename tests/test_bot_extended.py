"""Extended tests for bot.py - Target 60%+ coverage."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.bot import VFSBot
from src.models.database import Database
from src.services.notification import NotificationService


@pytest.fixture
def bot_config():
    """Standard bot configuration."""
    return {
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tur",
            "mission": "deu",
        },
        "credentials": {"email": "test@example.com", "password": "testpass"},
        "captcha": {"provider": "manual", "manual_timeout": 60},
        "anti_detection": {"enabled": False},
        "bot": {
            "headless": True,
            "screenshot_on_error": False,
        },
    }


@pytest.fixture
def bot_config_with_anti_detection():
    """Bot configuration with anti-detection enabled."""
    return {
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tur",
            "mission": "deu",
        },
        "credentials": {"email": "test@example.com", "password": "testpass"},
        "captcha": {"provider": "manual"},
        "anti_detection": {"enabled": True},
        "human_behavior": {},
        "session": {"save_file": "data/session.json"},
        "cloudflare": {},
        "proxy": {},
        "bot": {"headless": True},
    }


@pytest.fixture
def mock_database():
    """Mock database instance."""
    db = AsyncMock(spec=Database)
    db.get_active_users = AsyncMock(return_value=[])
    return db


@pytest.fixture
def mock_notifier():
    """Mock notification service."""
    notifier = AsyncMock(spec=NotificationService)
    notifier.notify_bot_started = AsyncMock()
    notifier.notify_bot_stopped = AsyncMock()
    return notifier


def test_bot_initialization_basic(bot_config, mock_database, mock_notifier):
    """Test basic VFSBot initialization."""
    bot = VFSBot(config=bot_config, db=mock_database, notifier=mock_notifier)

    assert bot.config == bot_config
    assert bot.db == mock_database
    assert bot.notifier == mock_notifier
    assert bot.browser is None
    assert bot.context is None
    assert bot.running is False


def test_bot_initialization_with_anti_detection_disabled(bot_config, mock_database, mock_notifier):
    """Test VFSBot initialization with anti-detection disabled."""
    bot = VFSBot(config=bot_config, db=mock_database, notifier=mock_notifier)

    assert bot.anti_detection_enabled is False
    assert bot.human_sim is None
    assert bot.header_manager is None
    assert bot.session_manager is None
    assert bot.cloudflare_handler is None
    assert bot.proxy_manager is None


def test_bot_initialization_with_anti_detection_enabled(
    bot_config_with_anti_detection, mock_database, mock_notifier
):
    """Test VFSBot initialization with anti-detection enabled."""
    bot = VFSBot(
        config=bot_config_with_anti_detection, db=mock_database, notifier=mock_notifier
    )

    assert bot.anti_detection_enabled is True
    assert bot.human_sim is not None
    assert bot.header_manager is not None
    assert bot.session_manager is not None
    assert bot.cloudflare_handler is not None
    assert bot.proxy_manager is not None


def test_bot_captcha_solver_initialization(bot_config, mock_database, mock_notifier):
    """Test that captcha solver is initialized."""
    bot = VFSBot(config=bot_config, db=mock_database, notifier=mock_notifier)

    assert bot.captcha_solver is not None
    assert bot.captcha_solver.provider == "manual"
    assert bot.captcha_solver.manual_timeout == 60


def test_bot_centre_fetcher_initialization(bot_config, mock_database, mock_notifier):
    """Test that centre fetcher is initialized."""
    bot = VFSBot(config=bot_config, db=mock_database, notifier=mock_notifier)

    assert bot.centre_fetcher is not None
    assert bot.centre_fetcher.base_url == "https://visa.vfsglobal.com"
    assert bot.centre_fetcher.country == "tur"
    assert bot.centre_fetcher.mission == "deu"


def test_bot_rate_limiter_initialization(bot_config, mock_database, mock_notifier):
    """Test that rate limiter is initialized."""
    bot = VFSBot(config=bot_config, db=mock_database, notifier=mock_notifier)

    assert bot.rate_limiter is not None


@pytest.mark.asyncio
async def test_bot_stop(bot_config, mock_database, mock_notifier):
    """Test bot stop method."""
    bot = VFSBot(config=bot_config, db=mock_database, notifier=mock_notifier)
    bot.running = True

    # Mock browser and context
    bot.browser = AsyncMock()
    bot.browser.close = AsyncMock()
    bot.context = AsyncMock()
    bot.context.close = AsyncMock()

    await bot.stop()

    assert bot.running is False
    bot.context.close.assert_called_once()
    bot.browser.close.assert_called_once()
    mock_notifier.notify_bot_stopped.assert_called_once()


@pytest.mark.asyncio
async def test_bot_stop_without_browser(bot_config, mock_database, mock_notifier):
    """Test bot stop when no browser is running."""
    bot = VFSBot(config=bot_config, db=mock_database, notifier=mock_notifier)
    bot.running = True

    await bot.stop()

    assert bot.running is False
    mock_notifier.notify_bot_stopped.assert_called_once()

