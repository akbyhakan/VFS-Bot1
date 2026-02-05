"""Tests for adaptive_scheduler module."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from src.services.adaptive_scheduler import AdaptiveScheduler


class TestAdaptiveScheduler:
    """Tests for AdaptiveScheduler class."""

    def test_init_default_timezone(self):
        """Test initialization with default timezone."""
        scheduler = AdaptiveScheduler()

        assert scheduler.timezone == ZoneInfo("Europe/Istanbul")
        assert scheduler.country_multiplier == 1.0

    def test_init_custom_timezone(self):
        """Test initialization with custom timezone."""
        scheduler = AdaptiveScheduler(timezone="Europe/Amsterdam", country_multiplier=1.5)

        assert scheduler.timezone == ZoneInfo("Europe/Amsterdam")
        assert scheduler.country_multiplier == 1.5

    @patch("src.services.adaptive_scheduler.datetime")
    def test_get_current_mode_peak(self, mock_datetime):
        """Test getting current mode during peak hours."""
        mock_datetime.now.return_value = datetime(
            2024, 1, 1, 9, 0, tzinfo=ZoneInfo("Europe/Istanbul")
        )

        scheduler = AdaptiveScheduler()
        mode = scheduler.get_current_mode()

        assert mode == "peak"

    @patch("src.services.adaptive_scheduler.datetime")
    def test_get_current_mode_normal(self, mock_datetime):
        """Test getting current mode during normal hours."""
        mock_datetime.now.return_value = datetime(
            2024, 1, 1, 11, 0, tzinfo=ZoneInfo("Europe/Istanbul")
        )

        scheduler = AdaptiveScheduler()
        mode = scheduler.get_current_mode()

        assert mode == "normal"

    @patch("src.services.adaptive_scheduler.datetime")
    def test_get_current_mode_low(self, mock_datetime):
        """Test getting current mode during low activity hours."""
        mock_datetime.now.return_value = datetime(
            2024, 1, 1, 20, 0, tzinfo=ZoneInfo("Europe/Istanbul")
        )

        scheduler = AdaptiveScheduler()
        mode = scheduler.get_current_mode()

        assert mode == "low"

    @patch("src.services.adaptive_scheduler.datetime")
    def test_get_current_mode_sleep(self, mock_datetime):
        """Test getting current mode during sleep hours."""
        mock_datetime.now.return_value = datetime(
            2024, 1, 1, 3, 0, tzinfo=ZoneInfo("Europe/Istanbul")
        )

        scheduler = AdaptiveScheduler()
        mode = scheduler.get_current_mode()

        assert mode == "sleep"

    @patch("src.services.adaptive_scheduler.datetime")
    def test_get_optimal_interval_peak(self, mock_datetime):
        """Test getting optimal interval during peak hours."""
        mock_datetime.now.return_value = datetime(
            2024, 1, 1, 9, 0, tzinfo=ZoneInfo("Europe/Istanbul")
        )

        scheduler = AdaptiveScheduler()
        interval = scheduler.get_optimal_interval()

        # Should be between 15 and 30 seconds for peak
        assert 15 <= interval <= 30

    @patch("src.services.adaptive_scheduler.datetime")
    def test_get_optimal_interval_with_multiplier(self, mock_datetime):
        """Test getting optimal interval with country multiplier."""
        mock_datetime.now.return_value = datetime(
            2024, 1, 1, 9, 0, tzinfo=ZoneInfo("Europe/Istanbul")
        )

        scheduler = AdaptiveScheduler(country_multiplier=2.0)
        interval = scheduler.get_optimal_interval()

        # Should be reduced due to multiplier, but minimum 10 seconds
        assert interval >= 10

    @patch("src.services.adaptive_scheduler.datetime")
    def test_get_optimal_interval_minimum(self, mock_datetime):
        """Test that optimal interval never goes below 10 seconds."""
        mock_datetime.now.return_value = datetime(
            2024, 1, 1, 9, 0, tzinfo=ZoneInfo("Europe/Istanbul")
        )

        # Very high multiplier to test minimum
        scheduler = AdaptiveScheduler(country_multiplier=10.0)
        interval = scheduler.get_optimal_interval()

        assert interval >= 10

    @patch("src.services.adaptive_scheduler.datetime")
    def test_get_mode_info(self, mock_datetime):
        """Test getting mode information."""
        mock_datetime.now.return_value = datetime(
            2024, 1, 1, 9, 0, tzinfo=ZoneInfo("Europe/Istanbul")
        )

        scheduler = AdaptiveScheduler(country_multiplier=1.5)
        mode_info = scheduler.get_mode_info()

        assert mode_info["mode"] == "peak"
        assert "description" in mode_info
        assert "interval_range" in mode_info
        assert mode_info["current_hour"] == 9
        assert mode_info["country_multiplier"] == 1.5

    @patch("src.services.adaptive_scheduler.datetime")
    def test_is_sleep_mode_true(self, mock_datetime):
        """Test is_sleep_mode returns True during sleep hours."""
        mock_datetime.now.return_value = datetime(
            2024, 1, 1, 3, 0, tzinfo=ZoneInfo("Europe/Istanbul")
        )

        scheduler = AdaptiveScheduler()

        assert scheduler.is_sleep_mode() is True

    @patch("src.services.adaptive_scheduler.datetime")
    def test_is_sleep_mode_false(self, mock_datetime):
        """Test is_sleep_mode returns False during active hours."""
        mock_datetime.now.return_value = datetime(
            2024, 1, 1, 9, 0, tzinfo=ZoneInfo("Europe/Istanbul")
        )

        scheduler = AdaptiveScheduler()

        assert scheduler.is_sleep_mode() is False

    def test_should_pause_default(self):
        """Test should_pause returns False by default."""
        scheduler = AdaptiveScheduler()

        assert scheduler.should_pause() is False
