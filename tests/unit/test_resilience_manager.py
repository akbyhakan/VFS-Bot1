"""Tests for ResilienceManager - central orchestrator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import Locator, Page

from src.core.exceptions import SelectorNotFoundError
from src.resilience import ResilienceManager


class TestResilienceManagerInitialization:
    """Tests for ResilienceManager initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        manager = ResilienceManager()

        assert manager.country_code == "default"
        assert manager.selectors_file == "config/selectors.yaml"
        assert manager.logs_dir == "logs/errors"
        assert manager.enable_ai_repair is True
        assert manager.enable_hot_reload is True
        assert manager.selector_manager is not None
        assert manager.forensic_logger is not None
        assert manager.smart_wait is not None

    def test_init_with_custom_country(self):
        """Test initialization with custom country code."""
        manager = ResilienceManager(country_code="fra")

        assert manager.country_code == "fra"
        assert manager.selector_manager.country_code == "fra"
        assert manager.forensic_logger.country_code == "fra"

    def test_init_with_ai_repair_disabled(self):
        """Test initialization with AI repair disabled."""
        manager = ResilienceManager(enable_ai_repair=False)

        assert manager.ai_repair is None

    def test_init_with_hot_reload_disabled(self):
        """Test initialization with hot-reload disabled."""
        manager = ResilienceManager(enable_hot_reload=False)

        assert manager.enable_hot_reload is False


class TestResilienceManagerLifecycle:
    """Tests for ResilienceManager lifecycle methods."""

    @pytest.mark.asyncio
    async def test_start_with_hot_reload_enabled(self):
        """Test start() starts hot-reload watcher when enabled."""
        manager = ResilienceManager(enable_hot_reload=True)
        manager.selector_manager.start_watching = AsyncMock()

        await manager.start()

        manager.selector_manager.start_watching.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_with_hot_reload_disabled(self):
        """Test start() doesn't start watcher when disabled."""
        manager = ResilienceManager(enable_hot_reload=False)

        await manager.start()

        # Should not raise error

    @pytest.mark.asyncio
    async def test_stop_stops_watcher(self):
        """Test stop() stops hot-reload watcher."""
        manager = ResilienceManager(enable_hot_reload=True)
        manager.selector_manager.is_watching = True
        manager.selector_manager.stop_watching = AsyncMock()

        await manager.stop()

        manager.selector_manager.stop_watching.assert_called_once()


class TestResilienceManagerFindElement:
    """Tests for ResilienceManager.find_element()."""

    @pytest.mark.asyncio
    async def test_find_element_success(self):
        """Test find_element returns locator on success."""
        manager = ResilienceManager()
        page = MagicMock(spec=Page)
        expected_locator = MagicMock(spec=Locator)

        manager.smart_wait.find_element = AsyncMock(return_value=expected_locator)

        result = await manager.find_element(page, "login.email_input")

        assert result == expected_locator
        manager.smart_wait.find_element.assert_called_once_with(
            page, "login.email_input", 10000, None
        )

    @pytest.mark.asyncio
    async def test_find_element_with_custom_timeout(self):
        """Test find_element respects custom timeout."""
        manager = ResilienceManager()
        page = MagicMock(spec=Page)
        expected_locator = MagicMock(spec=Locator)

        manager.smart_wait.find_element = AsyncMock(return_value=expected_locator)

        await manager.find_element(page, "login.email_input", timeout=20000)

        manager.smart_wait.find_element.assert_called_once_with(
            page, "login.email_input", 20000, None
        )

    @pytest.mark.asyncio
    async def test_find_element_captures_forensics_on_failure(self):
        """Test find_element captures forensic incident on failure."""
        manager = ResilienceManager()
        page = MagicMock(spec=Page)

        error = SelectorNotFoundError(
            selector_name="login.email_input", tried_selectors=["#email", ".email-input"]
        )
        manager.smart_wait.find_element = AsyncMock(side_effect=error)
        manager.forensic_logger.capture_incident = AsyncMock()

        with pytest.raises(SelectorNotFoundError):
            await manager.find_element(page, "login.email_input", action_context="login")

        manager.forensic_logger.capture_incident.assert_called_once()
        call_args = manager.forensic_logger.capture_incident.call_args
        assert call_args[1]["page"] == page
        assert call_args[1]["error"] == error


class TestResilienceManagerConvenienceMethods:
    """Tests for ResilienceManager convenience methods."""

    @pytest.mark.asyncio
    async def test_safe_click(self):
        """Test safe_click finds element and clicks it."""
        manager = ResilienceManager()
        page = MagicMock(spec=Page)
        locator = MagicMock(spec=Locator)
        locator.click = AsyncMock()

        manager.find_element = AsyncMock(return_value=locator)

        await manager.safe_click(page, "login.submit_button")

        manager.find_element.assert_called_once_with(
            page, "login.submit_button", 10000, None
        )
        locator.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_safe_fill(self):
        """Test safe_fill finds element and fills value."""
        manager = ResilienceManager()
        page = MagicMock(spec=Page)
        locator = MagicMock(spec=Locator)
        locator.fill = AsyncMock()

        manager.find_element = AsyncMock(return_value=locator)

        await manager.safe_fill(page, "login.email_input", "test@example.com")

        manager.find_element.assert_called_once()
        locator.fill.assert_called_once_with("test@example.com")

    @pytest.mark.asyncio
    async def test_safe_select(self):
        """Test safe_select finds element and selects option."""
        manager = ResilienceManager()
        page = MagicMock(spec=Page)
        locator = MagicMock(spec=Locator)
        locator.select_option = AsyncMock()

        manager.find_element = AsyncMock(return_value=locator)

        await manager.safe_select(page, "appointment.centre_dropdown", "London")

        manager.find_element.assert_called_once()
        locator.select_option.assert_called_once_with("London")


class TestResilienceManagerReload:
    """Tests for manual selector reload."""

    def test_reload_selectors(self):
        """Test manual selector reload triggers manager reload."""
        manager = ResilienceManager()
        manager.selector_manager.reload = MagicMock()

        manager.reload_selectors()

        manager.selector_manager.reload.assert_called_once()


class TestResilienceManagerStatus:
    """Tests for status reporting."""

    def test_get_status(self):
        """Test get_status returns comprehensive status."""
        manager = ResilienceManager(country_code="fra", enable_ai_repair=True)
        manager.selector_manager.get_status = MagicMock(
            return_value={"reload_count": 5}
        )
        manager.forensic_logger.get_status = MagicMock(
            return_value={"total_incidents": 10}
        )
        manager.ai_repair.enabled = True

        status = manager.get_status()

        assert status["country_code"] == "fra"
        assert status["enable_ai_repair"] is True
        assert status["enable_hot_reload"] is True
        assert status["selector_manager"]["reload_count"] == 5
        assert status["forensic_logger"]["total_incidents"] == 10
        assert status["ai_repair_enabled"] is True
