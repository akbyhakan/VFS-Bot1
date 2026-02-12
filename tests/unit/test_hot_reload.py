"""Tests for HotReloadableSelectorManager."""

import asyncio
import time
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.resilience import HotReloadableSelectorManager


class TestHotReloadableInitialization:
    """Tests for HotReloadableSelectorManager initialization."""

    def test_extends_country_aware_selector_manager(self):
        """Test that HotReloadableSelectorManager extends CountryAwareSelectorManager."""
        manager = HotReloadableSelectorManager(country_code="fra")

        # Should have all CountryAwareSelectorManager properties
        assert hasattr(manager, "country_code")
        assert hasattr(manager, "selectors_file")
        assert hasattr(manager, "get")
        assert hasattr(manager, "get_with_fallback")

        # Should have hot-reload properties
        assert hasattr(manager, "poll_interval")
        assert hasattr(manager, "start_watching")
        assert hasattr(manager, "stop_watching")

    def test_init_with_default_poll_interval(self):
        """Test initialization with default poll interval."""
        manager = HotReloadableSelectorManager()

        assert manager.poll_interval == 5.0  # Default from Resilience constants

    def test_init_with_custom_poll_interval(self):
        """Test initialization with custom poll interval."""
        manager = HotReloadableSelectorManager(poll_interval=10.0)

        assert manager.poll_interval == 10.0

    def test_init_sets_initial_stats(self):
        """Test initialization sets initial file stats."""
        manager = HotReloadableSelectorManager()

        assert manager._reload_count == 0
        assert manager._is_watching is False
        assert manager._watch_task is None


class TestFileChangeDetection:
    """Tests for file change detection."""

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.stat")
    def test_has_file_changed_detects_mtime_change(self, mock_stat, mock_exists):
        """Test _has_file_changed detects modification time change."""
        mock_exists.return_value = True

        manager = HotReloadableSelectorManager()
        manager._last_mtime = 1000.0
        manager._last_size = 500

        # Simulate file modification
        mock_stat_result = MagicMock()
        mock_stat_result.st_mtime = 2000.0  # Changed
        mock_stat_result.st_size = 500  # Same size
        mock_stat.return_value = mock_stat_result

        assert manager._has_file_changed() is True

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.stat")
    def test_has_file_changed_detects_size_change(self, mock_stat, mock_exists):
        """Test _has_file_changed detects size change."""
        mock_exists.return_value = True

        manager = HotReloadableSelectorManager()
        manager._last_mtime = 1000.0
        manager._last_size = 500

        # Simulate file size change
        mock_stat_result = MagicMock()
        mock_stat_result.st_mtime = 1000.0  # Same mtime
        mock_stat_result.st_size = 1000  # Changed size
        mock_stat.return_value = mock_stat_result

        assert manager._has_file_changed() is True

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.stat")
    def test_has_file_changed_no_change(self, mock_stat, mock_exists):
        """Test _has_file_changed returns False when no change."""
        mock_exists.return_value = True

        manager = HotReloadableSelectorManager()
        manager._last_mtime = 1000.0
        manager._last_size = 500

        # Simulate no change
        mock_stat_result = MagicMock()
        mock_stat_result.st_mtime = 1000.0
        mock_stat_result.st_size = 500
        mock_stat.return_value = mock_stat_result

        assert manager._has_file_changed() is False

    @patch("pathlib.Path.exists")
    def test_has_file_changed_file_not_exists(self, mock_exists):
        """Test _has_file_changed returns False when file doesn't exist."""
        mock_exists.return_value = False

        manager = HotReloadableSelectorManager()

        assert manager._has_file_changed() is False


class TestWatchingLifecycle:
    """Tests for start/stop watching lifecycle."""

    @pytest.mark.asyncio
    async def test_start_watching(self):
        """Test start_watching creates background task."""
        manager = HotReloadableSelectorManager()

        await manager.start_watching()

        assert manager._is_watching is True
        assert manager._watch_task is not None
        assert isinstance(manager._watch_task, asyncio.Task)

        # Cleanup
        await manager.stop_watching()

    @pytest.mark.asyncio
    async def test_start_watching_already_running(self):
        """Test start_watching when already running doesn't create duplicate."""
        manager = HotReloadableSelectorManager()

        await manager.start_watching()
        first_task = manager._watch_task

        await manager.start_watching()  # Call again

        # Should be same task
        assert manager._watch_task is first_task

        # Cleanup
        await manager.stop_watching()

    @pytest.mark.asyncio
    async def test_stop_watching(self):
        """Test stop_watching cancels background task."""
        manager = HotReloadableSelectorManager()

        await manager.start_watching()
        assert manager._is_watching is True

        await manager.stop_watching()

        assert manager._is_watching is False
        assert manager._watch_task is None

    @pytest.mark.asyncio
    async def test_stop_watching_not_running(self):
        """Test stop_watching when not running doesn't raise error."""
        manager = HotReloadableSelectorManager()

        await manager.stop_watching()  # Should not raise

        assert manager._is_watching is False


class TestReloadOnChange:
    """Tests for automatic reload when file changes."""

    @pytest.mark.asyncio
    async def test_reload_triggers_on_file_change(self):
        """Test that file change triggers reload."""
        manager = HotReloadableSelectorManager(poll_interval=0.1)
        manager.reload = MagicMock()
        manager._has_file_changed = MagicMock(side_effect=[False, True, False])

        await manager.start_watching()

        # Wait for at least one poll cycle
        await asyncio.sleep(0.3)

        await manager.stop_watching()

        # reload should have been called once when _has_file_changed returned True
        assert manager.reload.call_count >= 1

    @pytest.mark.asyncio
    async def test_reload_count_increments(self):
        """Test reload_count increments on each reload."""
        manager = HotReloadableSelectorManager(poll_interval=0.1)
        initial_count = manager._reload_count

        # Manually trigger reload
        manager._has_file_changed = MagicMock(return_value=True)
        manager.reload = MagicMock()

        await manager.start_watching()
        await asyncio.sleep(0.3)
        await manager.stop_watching()

        assert manager._reload_count > initial_count


class TestProperties:
    """Tests for properties."""

    @pytest.mark.asyncio
    async def test_is_watching_property(self):
        """Test is_watching property reflects watching state."""
        manager = HotReloadableSelectorManager()

        assert manager.is_watching is False

        await manager.start_watching()
        assert manager.is_watching is True

        await manager.stop_watching()
        assert manager.is_watching is False

    def test_reload_count_property(self):
        """Test reload_count property returns correct value."""
        manager = HotReloadableSelectorManager()

        assert manager.reload_count == 0

        manager._reload_count = 5
        assert manager.reload_count == 5


class TestGetStatus:
    """Tests for get_status method."""

    @patch("pathlib.Path.exists")
    def test_get_status_returns_correct_structure(self, mock_exists):
        """Test get_status returns comprehensive status dictionary."""
        mock_exists.return_value = True

        manager = HotReloadableSelectorManager(
            country_code="fra", poll_interval=10.0
        )
        manager._reload_count = 3
        manager._is_watching = True

        status = manager.get_status()

        assert status["country_code"] == "fra"
        assert "config/selectors.yaml" in status["selectors_file"]
        assert status["is_watching"] is True
        assert status["poll_interval"] == 10.0
        assert status["reload_count"] == 3
        assert "file_exists" in status
        assert "last_mtime" in status
        assert "last_size" in status
