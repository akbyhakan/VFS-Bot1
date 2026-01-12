"""Tests for helper utilities."""

import pytest
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.helpers import (
    smart_fill,
    smart_click,
    wait_for_selector_smart,
    random_delay,
    safe_navigate,
    safe_screenshot,
)


class TestSmartFill:
    """Test smart_fill function."""

    @pytest.mark.asyncio
    async def test_smart_fill_without_human_sim(self):
        """Test smart_fill without human simulation."""
        page = AsyncMock()
        await smart_fill(page, "#email", "test@example.com")

        page.fill.assert_awaited_once_with("#email", "test@example.com")

    @pytest.mark.asyncio
    async def test_smart_fill_with_human_sim(self):
        """Test smart_fill with human simulation."""
        page = AsyncMock()
        human_sim = MagicMock()
        human_sim.human_type = AsyncMock()

        await smart_fill(page, "#email", "test@example.com", human_sim=human_sim)

        human_sim.human_type.assert_awaited_once_with(page, "#email", "test@example.com")
        page.fill.assert_not_called()

    @pytest.mark.asyncio
    async def test_smart_fill_with_delay(self):
        """Test smart_fill with delay."""
        page = AsyncMock()
        start_time = asyncio.get_event_loop().time()

        await smart_fill(page, "#email", "test@example.com", delay=0.1)

        elapsed = asyncio.get_event_loop().time() - start_time
        assert elapsed >= 0.1
        page.fill.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_smart_fill_raises_exception(self):
        """Test smart_fill raises exception on error."""
        page = AsyncMock()
        page.fill.side_effect = Exception("Fill failed")

        with pytest.raises(Exception, match="Fill failed"):
            await smart_fill(page, "#email", "test@example.com")


class TestSmartClick:
    """Test smart_click function."""

    @pytest.mark.asyncio
    async def test_smart_click_without_human_sim(self):
        """Test smart_click without human simulation."""
        page = AsyncMock()
        await smart_click(page, "#submit")

        page.click.assert_awaited_once_with("#submit")

    @pytest.mark.asyncio
    async def test_smart_click_with_human_sim(self):
        """Test smart_click with human simulation."""
        page = AsyncMock()
        human_sim = MagicMock()
        human_sim.human_click = AsyncMock()

        await smart_click(page, "#submit", human_sim=human_sim)

        human_sim.human_click.assert_awaited_once_with(page, "#submit")
        page.click.assert_not_called()

    @pytest.mark.asyncio
    async def test_smart_click_with_delay(self):
        """Test smart_click with delay."""
        page = AsyncMock()
        start_time = asyncio.get_event_loop().time()

        await smart_click(page, "#submit", delay=0.1)

        elapsed = asyncio.get_event_loop().time() - start_time
        assert elapsed >= 0.1
        page.click.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_smart_click_raises_exception(self):
        """Test smart_click raises exception on error."""
        page = AsyncMock()
        page.click.side_effect = Exception("Click failed")

        with pytest.raises(Exception, match="Click failed"):
            await smart_click(page, "#submit")


class TestWaitForSelectorSmart:
    """Test wait_for_selector_smart function."""

    @pytest.mark.asyncio
    async def test_wait_for_selector_default_timeout(self):
        """Test wait_for_selector with default timeout."""
        page = AsyncMock()

        await wait_for_selector_smart(page, "#element")

        page.wait_for_selector.assert_awaited_once()
        args, kwargs = page.wait_for_selector.call_args
        assert args[0] == "#element"
        assert "timeout" in kwargs
        assert kwargs["state"] == "visible"

    @pytest.mark.asyncio
    async def test_wait_for_selector_custom_timeout(self):
        """Test wait_for_selector with custom timeout."""
        page = AsyncMock()

        await wait_for_selector_smart(page, "#element", timeout=5000)

        page.wait_for_selector.assert_awaited_once_with("#element", timeout=5000, state="visible")

    @pytest.mark.asyncio
    async def test_wait_for_selector_custom_state(self):
        """Test wait_for_selector with custom state."""
        page = AsyncMock()

        await wait_for_selector_smart(page, "#element", state="attached")

        page.wait_for_selector.assert_awaited_once()
        args, kwargs = page.wait_for_selector.call_args
        assert kwargs["state"] == "attached"

    @pytest.mark.asyncio
    async def test_wait_for_selector_raises_exception(self):
        """Test wait_for_selector raises exception on timeout."""
        page = AsyncMock()
        page.wait_for_selector.side_effect = Exception("Selector not found")

        with pytest.raises(Exception, match="Selector not found"):
            await wait_for_selector_smart(page, "#element")


class TestRandomDelay:
    """Test random_delay function."""

    @pytest.mark.asyncio
    async def test_random_delay_default(self):
        """Test random_delay with default values."""
        start_time = asyncio.get_event_loop().time()

        await random_delay()

        elapsed = asyncio.get_event_loop().time() - start_time
        # Default is 0.1 to 0.5 seconds
        assert elapsed >= 0.1
        assert elapsed <= 0.6  # Add small buffer

    @pytest.mark.asyncio
    async def test_random_delay_custom(self):
        """Test random_delay with custom values."""
        start_time = asyncio.get_event_loop().time()

        await random_delay(min_seconds=0.2, max_seconds=0.3)

        elapsed = asyncio.get_event_loop().time() - start_time
        assert elapsed >= 0.2
        assert elapsed <= 0.4  # Add small buffer


class TestSafeNavigate:
    """Test safe_navigate function."""

    @pytest.mark.asyncio
    async def test_safe_navigate_success(self):
        """Test successful navigation."""
        page = AsyncMock()

        result = await safe_navigate(page, "https://example.com")

        assert result is True
        page.goto.assert_awaited_once()
        args, kwargs = page.goto.call_args
        assert args[0] == "https://example.com"
        assert kwargs["wait_until"] == "networkidle"

    @pytest.mark.asyncio
    async def test_safe_navigate_custom_wait_until(self):
        """Test navigation with custom wait_until."""
        page = AsyncMock()

        result = await safe_navigate(page, "https://example.com", wait_until="load")

        assert result is True
        page.goto.assert_awaited_once()
        args, kwargs = page.goto.call_args
        assert kwargs["wait_until"] == "load"

    @pytest.mark.asyncio
    async def test_safe_navigate_custom_timeout(self):
        """Test navigation with custom timeout."""
        page = AsyncMock()

        result = await safe_navigate(page, "https://example.com", timeout=60000)

        assert result is True
        page.goto.assert_awaited_once()
        args, kwargs = page.goto.call_args
        assert kwargs["timeout"] == 60000

    @pytest.mark.asyncio
    async def test_safe_navigate_failure(self):
        """Test navigation failure."""
        page = AsyncMock()
        page.goto.side_effect = Exception("Navigation failed")

        result = await safe_navigate(page, "https://example.com")

        assert result is False


class TestSafeScreenshot:
    """Test safe_screenshot function."""

    @pytest.mark.asyncio
    async def test_safe_screenshot_success(self):
        """Test successful screenshot."""
        page = AsyncMock()

        result = await safe_screenshot(page, "/tmp/test.png")

        assert result is True
        page.screenshot.assert_awaited_once_with(path="/tmp/test.png", full_page=True)

    @pytest.mark.asyncio
    async def test_safe_screenshot_not_full_page(self):
        """Test screenshot without full page."""
        page = AsyncMock()

        result = await safe_screenshot(page, "/tmp/test.png", full_page=False)

        assert result is True
        page.screenshot.assert_awaited_once_with(path="/tmp/test.png", full_page=False)

    @pytest.mark.asyncio
    async def test_safe_screenshot_failure(self):
        """Test screenshot failure."""
        page = AsyncMock()
        page.screenshot.side_effect = Exception("Screenshot failed")

        result = await safe_screenshot(page, "/tmp/test.png")

        assert result is False
