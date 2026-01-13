"""Simple tests for bot_service (VFSBot in services/) to increase coverage."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.bot_service import VFSBot
from src.models.database import Database
from src.services.notification import NotificationService


class TestBotServiceInit:
    """Test VFSBot (bot_service) initialization."""

    def test_init_basic(self):
        """Test basic initialization."""
        config = {
            "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tur", "mission": "deu"},
            "captcha": {"provider": "manual"},
            "bot": {"headless": True, "check_interval": 60},
        }
        db = MagicMock(spec=Database)
        notifier = MagicMock(spec=NotificationService)

        bot = VFSBot(config=config, db=db, notifier=notifier)

        assert bot.config == config
        assert bot.db == db
        assert bot.notifier == notifier
        assert bot.running is False

    def test_init_sets_components(self):
        """Test initialization sets components."""
        config = {
            "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tur", "mission": "deu"},
            "captcha": {"provider": "manual"},
            "bot": {"headless": True, "check_interval": 60},
        }
        db = MagicMock(spec=Database)
        notifier = MagicMock(spec=NotificationService)

        bot = VFSBot(config=config, db=db, notifier=notifier)

        assert hasattr(bot, "captcha_solver")
        assert hasattr(bot, "rate_limiter")

    def test_circuit_breaker_init(self):
        """Test circuit breaker initialization."""
        config = {
            "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tur", "mission": "deu"},
            "captcha": {"provider": "manual"},
            "bot": {"headless": True},
        }
        db = MagicMock(spec=Database)
        notifier = MagicMock(spec=NotificationService)

        bot = VFSBot(config=config, db=db, notifier=notifier)

        # Circuit breaker should be initialized
        assert hasattr(bot, "circuit_breaker")


@pytest.mark.asyncio
class TestBotServiceMethods:
    """Test bot service methods."""

    async def test_setup_method_exists(self):
        """Test setup method exists."""
        config = {
            "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tur", "mission": "deu"},
            "captcha": {"provider": "manual"},
            "bot": {"headless": True},
        }
        db = MagicMock(spec=Database)
        notifier = MagicMock(spec=NotificationService)

        bot = VFSBot(config=config, db=db, notifier=notifier)

        assert hasattr(bot, "setup")
        assert callable(bot.setup)

    async def test_cleanup_method_exists(self):
        """Test cleanup method exists."""
        config = {
            "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tur", "mission": "deu"},
            "captcha": {"provider": "manual"},
            "bot": {"headless": True},
        }
        db = MagicMock(spec=Database)
        notifier = MagicMock(spec=NotificationService)

        bot = VFSBot(config=config, db=db, notifier=notifier)

        assert hasattr(bot, "cleanup")
        assert callable(bot.cleanup)
