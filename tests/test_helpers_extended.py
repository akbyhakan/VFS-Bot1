"""Extended tests for helpers.py - Target 100% coverage."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from playwright.async_api import Page

from src.utils.helpers import (
    smart_fill,
    smart_click,
    wait_for_selector_smart,
    random_delay,
    safe_navigate,
    safe_screenshot,
)
from src.constants import Intervals, Timeouts


@pytest.mark.asyncio
async def test_smart_fill_without_human_sim():
    """Test smart_fill without human simulation."""
    page = AsyncMock(spec=Page)
    await smart_fill(page, "#input", "test text")
    page.fill.assert_called_once_with("#input", "test text")


@pytest.mark.asyncio
async def test_smart_fill_with_human_sim():
    """Test smart_fill with human simulation."""
    page = AsyncMock(spec=Page)
    human_sim = MagicMock()
    human_sim.human_type = AsyncMock()
    await smart_fill(page, "#input", "test text", human_sim=human_sim)
    human_sim.human_type.assert_called_once_with(page, "#input", "test text")
    page.fill.assert_not_called()


@pytest.mark.asyncio
async def test_smart_fill_with_delay():
    """Test smart_fill with delay."""
    page = AsyncMock(spec=Page)
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await smart_fill(page, "#input", "test text", delay=0.5)
        mock_sleep.assert_called_once_with(0.5)
    page.fill.assert_called_once()


@pytest.mark.asyncio
async def test_smart_fill_error_handling():
    """Test smart_fill error handling."""
    page = AsyncMock(spec=Page)
    page.fill.side_effect = Exception("Fill failed")
    with pytest.raises(Exception, match="Fill failed"):
        await smart_fill(page, "#input", "test text")


@pytest.mark.asyncio
async def test_smart_click_without_human_sim():
    """Test smart_click without human simulation."""
    page = AsyncMock(spec=Page)
    await smart_click(page, "#button")
    page.click.assert_called_once_with("#button")


@pytest.mark.asyncio
async def test_smart_click_with_human_sim():
    """Test smart_click with human simulation."""
    page = AsyncMock(spec=Page)
    human_sim = MagicMock()
    human_sim.human_click = AsyncMock()
    await smart_click(page, "#button", human_sim=human_sim)
    human_sim.human_click.assert_called_once_with(page, "#button")
    page.click.assert_not_called()


@pytest.mark.asyncio
async def test_smart_click_with_delay():
    """Test smart_click with delay."""
    page = AsyncMock(spec=Page)
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await smart_click(page, "#button", delay=1.0)
        mock_sleep.assert_called_once_with(1.0)
    page.click.assert_called_once()


@pytest.mark.asyncio
async def test_smart_click_error_handling():
    """Test smart_click error handling."""
    page = AsyncMock(spec=Page)
    page.click.side_effect = Exception("Click failed")
    with pytest.raises(Exception, match="Click failed"):
        await smart_click(page, "#button")


@pytest.mark.asyncio
async def test_wait_for_selector_smart_default():
    """Test wait_for_selector_smart with default timeout."""
    page = AsyncMock(spec=Page)
    await wait_for_selector_smart(page, "#selector")
    page.wait_for_selector.assert_called_once_with(
        "#selector", timeout=Timeouts.SELECTOR_WAIT, state="visible"
    )


@pytest.mark.asyncio
async def test_wait_for_selector_smart_custom_timeout():
    """Test wait_for_selector_smart with custom timeout."""
    page = AsyncMock(spec=Page)
    await wait_for_selector_smart(page, "#selector", timeout=5000)
    page.wait_for_selector.assert_called_once_with("#selector", timeout=5000, state="visible")


@pytest.mark.asyncio
async def test_wait_for_selector_smart_different_states():
    """Test wait_for_selector_smart with different states."""
    page = AsyncMock(spec=Page)

    # Test hidden state
    await wait_for_selector_smart(page, "#selector", state="hidden")
    page.wait_for_selector.assert_called_with("#selector", timeout=Timeouts.SELECTOR_WAIT, state="hidden")

    # Test attached state
    await wait_for_selector_smart(page, "#selector", state="attached")
    page.wait_for_selector.assert_called_with("#selector", timeout=Timeouts.SELECTOR_WAIT, state="attached")


@pytest.mark.asyncio
async def test_wait_for_selector_smart_error():
    """Test wait_for_selector_smart error handling."""
    page = AsyncMock(spec=Page)
    page.wait_for_selector.side_effect = Exception("Selector not found")
    with pytest.raises(Exception, match="Selector not found"):
        await wait_for_selector_smart(page, "#missing")


@pytest.mark.asyncio
async def test_random_delay_default():
    """Test random_delay with default values."""
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await random_delay()
        # Verify sleep was called with a value between defaults
        call_args = mock_sleep.call_args[0][0]
        assert Intervals.HUMAN_DELAY_MIN <= call_args <= Intervals.HUMAN_DELAY_MAX


@pytest.mark.asyncio
async def test_random_delay_custom():
    """Test random_delay with custom values."""
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await random_delay(min_seconds=1.0, max_seconds=2.0)
        call_args = mock_sleep.call_args[0][0]
        assert 1.0 <= call_args <= 2.0


@pytest.mark.asyncio
async def test_safe_navigate_success():
    """Test safe_navigate successful navigation."""
    page = AsyncMock(spec=Page)
    result = await safe_navigate(page, "https://example.com")
    assert result is True
    page.goto.assert_called_once_with(
        "https://example.com", wait_until="networkidle", timeout=Timeouts.NAVIGATION
    )


@pytest.mark.asyncio
async def test_safe_navigate_custom_wait_until():
    """Test safe_navigate with custom wait_until."""
    page = AsyncMock(spec=Page)
    result = await safe_navigate(page, "https://example.com", wait_until="load")
    assert result is True
    page.goto.assert_called_once_with(
        "https://example.com", wait_until="load", timeout=Timeouts.NAVIGATION
    )


@pytest.mark.asyncio
async def test_safe_navigate_custom_timeout():
    """Test safe_navigate with custom timeout."""
    page = AsyncMock(spec=Page)
    result = await safe_navigate(page, "https://example.com", timeout=60000)
    assert result is True
    page.goto.assert_called_once_with(
        "https://example.com", wait_until="networkidle", timeout=60000
    )


@pytest.mark.asyncio
async def test_safe_navigate_failure():
    """Test safe_navigate with navigation failure."""
    page = AsyncMock(spec=Page)
    page.goto.side_effect = Exception("Navigation timeout")
    result = await safe_navigate(page, "https://example.com")
    assert result is False


@pytest.mark.asyncio
async def test_safe_screenshot_success():
    """Test safe_screenshot successful capture."""
    page = AsyncMock(spec=Page)
    result = await safe_screenshot(page, "/tmp/test.png")
    assert result is True
    page.screenshot.assert_called_once_with(path="/tmp/test.png", full_page=True)


@pytest.mark.asyncio
async def test_safe_screenshot_not_full_page():
    """Test safe_screenshot with full_page=False."""
    page = AsyncMock(spec=Page)
    result = await safe_screenshot(page, "/tmp/test.png", full_page=False)
    assert result is True
    page.screenshot.assert_called_once_with(path="/tmp/test.png", full_page=False)


@pytest.mark.asyncio
async def test_safe_screenshot_failure():
    """Test safe_screenshot with capture failure."""
    page = AsyncMock(spec=Page)
    page.screenshot.side_effect = Exception("Screenshot failed")
    result = await safe_screenshot(page, "/tmp/test.png")
    assert result is False
