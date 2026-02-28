"""Tests for selector health monitoring."""

import pytest

from src.selector import CountryAwareSelectorManager, SelectorHealthCheck

# Add parent directory to path for imports


class TestSelectorHealthCheck:
    """Test selector health check functionality."""

    def test_init(self):
        """Test SelectorHealthCheck initialization."""
        sm = CountryAwareSelectorManager()
        health_checker = SelectorHealthCheck(sm)

        assert health_checker.selector_manager == sm
        assert health_checker.notifier is None
        assert health_checker.check_interval == 3600
        assert health_checker.health_status == {}
        assert health_checker.last_check is None
        assert health_checker.shutdown_event is None
        assert health_checker.critical_failure_threshold == 0.5

    def test_init_with_custom_interval(self):
        """Test SelectorHealthCheck with custom interval."""
        sm = CountryAwareSelectorManager()
        health_checker = SelectorHealthCheck(sm, check_interval=1800)

        assert health_checker.check_interval == 1800


class TestSelectorManager:
    """Test SelectorManager get_fallbacks method."""

    def test_get_fallbacks_with_list(self):
        """Test get_fallbacks returns fallback selectors."""
        sm = CountryAwareSelectorManager()
        fallbacks = sm.get_fallbacks("login.email_input")

        # Should return a list (may be empty or contain fallbacks)
        assert isinstance(fallbacks, list)

    def test_get_fallbacks_nonexistent(self):
        """Test get_fallbacks for nonexistent selector."""
        sm = CountryAwareSelectorManager()
        fallbacks = sm.get_fallbacks("nonexistent.selector")

        # Should return empty list for nonexistent selectors
        assert fallbacks == []
