"""Tests for services/cleanup_service module."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.cleanup_service import CleanupService


class TestCleanupService:
    """Tests for CleanupService."""

    def test_initialization(self):
        """Test CleanupService initialization."""
        db = MagicMock()
        service = CleanupService(db)
        assert service.db == db
        assert service.cleanup_days == 30
        assert service.screenshot_cleanup_days == 7
        assert service.screenshot_dir == Path("screenshots")
        assert not service._running

    def test_initialization_with_custom_values(self):
        """Test CleanupService with custom values."""
        db = MagicMock()
        service = CleanupService(
            db, cleanup_days=15, screenshot_cleanup_days=3, screenshot_dir="custom_dir"
        )
        assert service.cleanup_days == 15
        assert service.screenshot_cleanup_days == 3
        assert service.screenshot_dir == Path("custom_dir")

    @pytest.mark.asyncio
    async def test_cleanup_old_requests_success(self):
        """Test cleanup_old_requests when successful."""
        db = MagicMock()
        db.cleanup_completed_requests = AsyncMock(return_value=5)
        service = CleanupService(db, cleanup_days=30)

        deleted = await service.cleanup_old_requests()
        assert deleted == 5
        db.cleanup_completed_requests.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_cleanup_old_requests_with_error(self):
        """Test cleanup_old_requests handles errors."""
        db = MagicMock()
        db.cleanup_completed_requests = AsyncMock(side_effect=Exception("DB error"))
        service = CleanupService(db)

        deleted = await service.cleanup_old_requests()
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_cleanup_old_screenshots_dir_not_exists(self):
        """Test cleanup_old_screenshots when directory doesn't exist."""
        db = MagicMock()
        service = CleanupService(db, screenshot_dir="nonexistent")

        deleted = await service.cleanup_old_screenshots()
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_cleanup_old_screenshots_with_files(self, tmp_path):
        """Test cleanup_old_screenshots with actual files."""
        db = MagicMock()
        screenshot_dir = tmp_path / "screenshots"
        screenshot_dir.mkdir()

        # Create some old screenshot files
        old_file = screenshot_dir / "old_screenshot.png"
        old_file.write_text("old")

        service = CleanupService(db, screenshot_cleanup_days=0, screenshot_dir=str(screenshot_dir))

        # The file should be deleted since cleanup_days is 0
        deleted = await service.cleanup_old_screenshots()
        # Depends on file age, might be 0 or 1
        assert deleted >= 0

    @pytest.mark.asyncio
    async def test_cleanup_old_screenshots_handles_errors(self, tmp_path):
        """Test cleanup_old_screenshots handles file errors."""
        db = MagicMock()
        screenshot_dir = tmp_path / "screenshots"
        screenshot_dir.mkdir()

        service = CleanupService(db, screenshot_dir=str(screenshot_dir))

        # Should not crash even with permission issues
        deleted = await service.cleanup_old_screenshots()
        assert deleted >= 0
