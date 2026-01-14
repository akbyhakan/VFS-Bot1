import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from selector_watcher import SelectorWatcher
from selector_health import SelectorHealth


class TestSelectorWatcherExtended:
    """Extended tests for SelectorWatcher functionality."""

    @pytest.fixture
    def mock_config(self):
        return {
            "selectors": {
                "date_picker": "#date-select",
                "submit_button": "button[type='submit']",
                "form_container": ".form-wrapper"
            },
            "check_interval": 3600,
            "alert_threshold": 3
        }

    @pytest.fixture
    def watcher(self, mock_config):
        return SelectorWatcher(mock_config)

    def test_watcher_initialization(self, watcher, mock_config):
        """Test that watcher initializes with correct config."""
        assert watcher.config == mock_config
        assert watcher.selectors == mock_config["selectors"]
        assert watcher.alert_threshold == 3

    def test_selector_health_default_interval(self):
        """Test SelectorHealth uses correct default interval."""
        checker = SelectorHealth()
        # Default interval should be 12 hours (43200 seconds)
        assert checker.check_interval == 43200  # 12 hours (SelectorHealth.DEFAULT_INTERVAL)

    def test_selector_validation(self, watcher):
        """Test selector validation logic."""
        valid_selector = "#valid-id"
        invalid_selector = ""
        
        assert watcher.validate_selector(valid_selector) is True
        assert watcher.validate_selector(invalid_selector) is False

    @pytest.mark.asyncio
    async def test_async_health_check(self, watcher):
        """Test async health check functionality."""
        with patch.object(watcher, '_check_selector', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True
            result = await watcher.run_health_check()
            assert result["status"] == "healthy"

    def test_alert_on_threshold_exceeded(self, watcher):
        """Test that alerts are triggered when threshold is exceeded."""
        watcher.failure_count = 4
        assert watcher.should_alert() is True

    def test_no_alert_under_threshold(self, watcher):
        """Test that no alert is triggered under threshold."""
        watcher.failure_count = 2
        assert watcher.should_alert() is False

    def test_reset_failure_count(self, watcher):
        """Test failure count reset functionality."""
        watcher.failure_count = 5
        watcher.reset_failures()
        assert watcher.failure_count == 0

    def test_selector_update(self, watcher):
        """Test updating a selector."""
        new_selector = "#new-date-picker"
        watcher.update_selector("date_picker", new_selector)
        assert watcher.selectors["date_picker"] == new_selector

    def test_get_all_selectors(self, watcher, mock_config):
        """Test getting all configured selectors."""
        selectors = watcher.get_all_selectors()
        assert selectors == mock_config["selectors"]

    @pytest.mark.parametrize("selector,expected", [
        ("#valid-id", True),
        (".valid-class", True),
        ("button[type='submit']", True),
        ("", False),
        (None, False),
    ])
    def test_selector_validation_parametrized(self, watcher, selector, expected):
        """Parametrized test for selector validation."""
        assert watcher.validate_selector(selector) == expected
