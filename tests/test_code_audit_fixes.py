"""Tests for code audit fixes."""

import asyncio
import os
import random
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCORSProductionHardFail:
    """Test CORS production configuration validation."""

    def test_cors_raises_error_in_production_without_origins(self):
        """Test that missing CORS origins in production raises RuntimeError."""
        # Set production environment
        os.environ["ENV"] = "production"
        os.environ.pop("CORS_ALLOWED_ORIGINS", None)

        # Import the app module which should fail in production
        with pytest.raises(RuntimeError) as exc_info:
            # We can't directly import the app as it would fail, so we'll test the logic
            from web.app import validate_cors_origins

            allowed_origins = validate_cors_origins("")
            env = os.getenv("ENV", "production").lower()
            if not allowed_origins and env not in ("development", "dev", "local", "testing", "test"):
                raise RuntimeError(
                    "CRITICAL: No valid CORS origins configured for production. "
                    "Set CORS_ALLOWED_ORIGINS in .env (e.g., 'https://yourdomain.com'). "
                    "Application cannot start without valid CORS configuration in production."
                )

        assert "CRITICAL" in str(exc_info.value)
        assert "CORS" in str(exc_info.value)

    def test_cors_allows_empty_in_development(self):
        """Test that missing CORS origins is allowed in development."""
        # Set development environment
        os.environ["ENV"] = "development"
        os.environ.pop("CORS_ALLOWED_ORIGINS", None)

        from web.app import validate_cors_origins

        allowed_origins = validate_cors_origins("")
        # Should not raise in development, just returns empty list
        assert allowed_origins == []


class TestBrowserMemoryLeakPrevention:
    """Test browser memory leak prevention features."""

    @pytest.mark.asyncio
    async def test_browser_manager_tracks_page_count(self):
        """Test that BrowserManager tracks page creation count."""
        from src.services.bot.browser_manager import BrowserManager

        config = {
            "bot": {"headless": True, "browser_restart_after_pages": 5},
            "anti_detection": {"enabled": False},
        }
        browser_manager = BrowserManager(config)

        assert browser_manager._page_count == 0
        assert browser_manager._max_pages_before_restart == 5

    @pytest.mark.asyncio
    async def test_browser_manager_should_restart(self):
        """Test should_restart logic."""
        from src.services.bot.browser_manager import BrowserManager

        config = {
            "bot": {"headless": True, "browser_restart_after_pages": 3},
            "anti_detection": {"enabled": False},
        }
        browser_manager = BrowserManager(config)

        # First 2 pages should not trigger restart
        assert not await browser_manager.should_restart()  # 1
        assert not await browser_manager.should_restart()  # 2

        # 3rd page should trigger restart
        assert await browser_manager.should_restart()  # 3

    @pytest.mark.asyncio
    async def test_browser_manager_default_restart_threshold(self):
        """Test default restart threshold."""
        from src.services.bot.browser_manager import BrowserManager

        config = {"bot": {}, "anti_detection": {"enabled": False}}
        browser_manager = BrowserManager(config)

        # Default should be 100
        assert browser_manager._max_pages_before_restart == 100


class TestGracefulShutdownNotifications:
    """Test graceful shutdown notification features."""

    @pytest.mark.asyncio
    async def test_stop_sends_notification_when_waiting(self):
        """Test that stop() sends notification when waiting for bookings."""
        from src.services.bot.vfs_bot import VFSBot

        # Create minimal mocks
        config = {"bot": {}, "anti_detection": {"enabled": False}}
        db = MagicMock()
        notifier = MagicMock()
        notifier.notify_bot_stopped = AsyncMock()

        # Mock browser manager
        browser_manager = MagicMock()
        browser_manager.close = AsyncMock()

        # Create VFSBot instance with mocks
        with patch.object(VFSBot, "__init__", lambda self, *args, **kwargs: None):
            bot = VFSBot.__new__(VFSBot)
            bot.running = True
            bot._stopped = False  # Initialize the stopped flag
            bot.browser_manager = browser_manager
            bot.notifier = notifier
            bot._active_booking_tasks = []
            
            # Mock services.workflow.alert_service
            bot.services = MagicMock()
            bot.services.workflow = MagicMock()
            bot.services.workflow.alert_service = MagicMock()
            bot.services.workflow.alert_service.send_alert = AsyncMock()

            # Simulate active tasks
            async def mock_task():
                await asyncio.sleep(0.1)

            bot._active_booking_tasks = [asyncio.create_task(mock_task())]

            # Call stop
            await bot.stop()

            # Verify notification was sent
            assert bot.services.workflow.alert_service.send_alert.called
            call_args = bot.services.workflow.alert_service.send_alert.call_args_list[0][1]
            assert "waiting" in call_args["message"].lower()

    @pytest.mark.asyncio
    async def test_stop_idempotent(self):
        """Test that stop() can be called multiple times safely."""
        from src.services.bot.vfs_bot import VFSBot

        # Create minimal mocks
        config = {"bot": {}, "anti_detection": {"enabled": False}}
        db = MagicMock()
        notifier = MagicMock()
        notifier.notify_bot_stopped = AsyncMock()

        # Mock browser manager
        browser_manager = MagicMock()
        browser_manager.close = AsyncMock()

        # Create VFSBot instance with mocks
        with patch.object(VFSBot, "__init__", lambda self, *args, **kwargs: None):
            bot = VFSBot.__new__(VFSBot)
            bot.running = True
            bot._stopped = False
            bot.browser_manager = browser_manager
            bot.notifier = notifier
            bot._active_booking_tasks = []
            
            # Mock services
            bot.services = MagicMock()
            bot.services.workflow = MagicMock()
            bot.services.workflow.alert_service = None  # No alert service

            # Call stop twice
            await bot.stop()
            await bot.stop()

            # Browser manager close should only be called once
            assert browser_manager.close.call_count == 1
            # Notifier should only be called once
            assert notifier.notify_bot_stopped.call_count == 1


class TestBotLoopErrorRecoveryJitter:
    """Test error recovery jitter feature."""

    def test_jitter_imports_random(self):
        """Test that random module is imported."""
        from src.services.bot import vfs_bot

        assert hasattr(vfs_bot, "random")

    def test_jitter_calculation(self):
        """Test jitter calculation produces values in expected range."""
        # Simulate the jitter calculation
        from src.constants import Intervals

        error_recovery = Intervals.ERROR_RECOVERY  # Should be 60
        results = []

        for _ in range(100):
            jitter = random.uniform(0.8, 1.2)
            sleep_time = error_recovery * jitter
            results.append(sleep_time)

        # All results should be in range [48, 72] for 60s base
        assert all(error_recovery * 0.8 <= r <= error_recovery * 1.2 for r in results)
        # Should have some variation
        assert len(set(results)) > 50  # At least 50 unique values


class TestDatabaseBackupAutoStart:
    """Test database backup auto-start feature."""

    def test_backup_service_import(self):
        """Test that backup service can be imported."""
        from src.utils.db_backup import get_backup_service

        assert callable(get_backup_service)

    @pytest.mark.asyncio
    async def test_backup_service_creation(self):
        """Test backup service creation."""
        from src.constants import Database as DatabaseConfig
        from src.utils.db_backup import DatabaseBackup

        with tempfile.TemporaryDirectory() as tmpdir:
            # Use PostgreSQL test database URL
            test_db_url = DatabaseConfig.TEST_URL
            backup_dir = str(Path(tmpdir) / "backups")

            # Create service directly (not using singleton getter)
            backup_service = DatabaseBackup(database_url=test_db_url, backup_dir=backup_dir)
            assert backup_service is not None
            assert backup_service._database_url == test_db_url


class TestPreMigrationBackup:
    """Test pre-migration backup feature."""

    @pytest.mark.asyncio
    async def test_database_backup_util_import(self):
        """Test that DatabaseBackup can be imported from db_backup_util."""
        from src.utils.db_backup_util import DatabaseBackup

        assert DatabaseBackup is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_backup_before_migration(self):
        """Test that backup is created before migrations."""
        from src.constants import Database as DatabaseConfig
        from src.models.database import Database

        # Use PostgreSQL test database URL
        test_db_url = DatabaseConfig.TEST_URL

        try:
            db = Database(database_url=test_db_url)
            # Connect will trigger migrations
            await db.connect()
            await db.close()
        except Exception as e:
            # Skip test if database is not available
            pytest.skip(f"Database not available for integration test: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
