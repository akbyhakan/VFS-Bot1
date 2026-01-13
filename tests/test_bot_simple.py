"""Simple tests for VFSBot to increase coverage."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.bot import VFSBot
from src.database import Database
from src.notification import NotificationService


class TestVFSBotInit:
    """Test VFSBot initialization."""

    def test_init_basic(self):
        """Test basic initialization."""
        config = {
            "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tur", "mission": "deu"},
            "captcha": {"provider": "manual"},
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
        }
        db = MagicMock(spec=Database)
        notifier = MagicMock(spec=NotificationService)

        bot = VFSBot(config=config, db=db, notifier=notifier)

        assert hasattr(bot, "captcha_solver")
        assert hasattr(bot, "rate_limiter")
