"""Tests for helper utilities."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.helpers import (
    smart_fill,
    smart_click,
    wait_for_selector_smart,
    random_delay,
    safe_navigate,
    safe_screenshot,
)


@pytest.fixture
def mock_page():
    """Create a mock Playwright page."""
    page = AsyncMock()
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.goto = AsyncMock()
    page.screenshot = AsyncMock()
    return page


@pytest.fixture
def mock_human_sim():
    """Create a mock HumanSimulator."""
    human_sim = MagicMock()
    human_sim.human_type = AsyncMock()
    human_sim.human_click = AsyncMock()
    return human_sim


@pytest.mark.asyncio
async def test_smart_fill_without_human_sim(mock_page):
    """Test smart_fill without human simulation."""
    await smart_fill(mock_page, "#email", "test@example.com")
    mock_page.fill.assert_called_once_with("#email", "test@example.com")


@pytest.mark.asyncio
async def test_smart_fill_with_human_sim(mock_page, mock_human_sim):
    """Test smart_fill with human simulation."""
    await smart_fill(mock_page, "#email", "test@example.com", human_sim=mock_human_sim)
    mock_human_sim.human_type.assert_called_once_with(mock_page, "#email", "test@example.com")
    mock_page.fill.assert_not_called()


@pytest.mark.asyncio
async def test_smart_fill_with_delay(mock_page):
    """Test smart_fill with delay."""
    await smart_fill(mock_page, "#email", "test@example.com", delay=0.1)
    mock_page.fill.assert_called_once()


@pytest.mark.asyncio
async def test_smart_fill_exception(mock_page):
    """Test smart_fill handles exceptions."""
    mock_page.fill.side_effect = Exception("Fill failed")
    
    with pytest.raises(Exception, match="Fill failed"):
        await smart_fill(mock_page, "#email", "test@example.com")


@pytest.mark.asyncio
async def test_smart_click_without_human_sim(mock_page):
    """Test smart_click without human simulation."""
    await smart_click(mock_page, "#submit")
    mock_page.click.assert_called_once_with("#submit")


@pytest.mark.asyncio
async def test_smart_click_with_human_sim(mock_page, mock_human_sim):
    """Test smart_click with human simulation."""
    await smart_click(mock_page, "#submit", human_sim=mock_human_sim)
    mock_human_sim.human_click.assert_called_once_with(mock_page, "#submit")
    mock_page.click.assert_not_called()


@pytest.mark.asyncio
async def test_smart_click_with_delay(mock_page):
    """Test smart_click with delay."""
    await smart_click(mock_page, "#submit", delay=0.1)
    mock_page.click.assert_called_once()


@pytest.mark.asyncio
async def test_smart_click_exception(mock_page):
    """Test smart_click handles exceptions."""
    mock_page.click.side_effect = Exception("Click failed")
    
    with pytest.raises(Exception, match="Click failed"):
        await smart_click(mock_page, "#submit")


@pytest.mark.asyncio
async def test_wait_for_selector_smart_default(mock_page):
    """Test wait_for_selector_smart with defaults."""
    await wait_for_selector_smart(mock_page, "#element")
    mock_page.wait_for_selector.assert_called_once()
    args = mock_page.wait_for_selector.call_args
    assert args[0][0] == "#element"
    assert args[1]["state"] == "visible"


@pytest.mark.asyncio
async def test_wait_for_selector_smart_custom_timeout(mock_page):
    """Test wait_for_selector_smart with custom timeout."""
    await wait_for_selector_smart(mock_page, "#element", timeout=5000)
    args = mock_page.wait_for_selector.call_args
    assert args[1]["timeout"] == 5000


@pytest.mark.asyncio
async def test_wait_for_selector_smart_custom_state(mock_page):
    """Test wait_for_selector_smart with custom state."""
    await wait_for_selector_smart(mock_page, "#element", state="hidden")
    args = mock_page.wait_for_selector.call_args
    assert args[1]["state"] == "hidden"


@pytest.mark.asyncio
async def test_wait_for_selector_smart_timeout_exception(mock_page):
    """Test wait_for_selector_smart handles timeout."""
    mock_page.wait_for_selector.side_effect = Exception("Timeout")
    
    with pytest.raises(Exception, match="Timeout"):
        await wait_for_selector_smart(mock_page, "#element")


@pytest.mark.asyncio
async def test_random_delay_default():
    """Test random_delay with default values."""
    import time
    start = time.time()
    await random_delay()
    elapsed = time.time() - start
    # Should be at least minimum delay (even if very small)
    assert elapsed >= 0


@pytest.mark.asyncio
async def test_random_delay_custom():
    """Test random_delay with custom values."""
    import time
    start = time.time()
    await random_delay(min_seconds=0.1, max_seconds=0.2)
    elapsed = time.time() - start
    assert 0.1 <= elapsed <= 0.3  # Small buffer for execution time


@pytest.mark.asyncio
async def test_safe_navigate_success(mock_page):
    """Test safe_navigate successful navigation."""
    result = await safe_navigate(mock_page, "https://example.com")
    assert result is True
    mock_page.goto.assert_called_once()
    args = mock_page.goto.call_args
    assert args[0][0] == "https://example.com"
    assert args[1]["wait_until"] == "networkidle"


@pytest.mark.asyncio
async def test_safe_navigate_custom_wait(mock_page):
    """Test safe_navigate with custom wait condition."""
    result = await safe_navigate(mock_page, "https://example.com", wait_until="load")
    assert result is True
    args = mock_page.goto.call_args
    assert args[1]["wait_until"] == "load"


@pytest.mark.asyncio
async def test_safe_navigate_custom_timeout(mock_page):
    """Test safe_navigate with custom timeout."""
    result = await safe_navigate(mock_page, "https://example.com", timeout=60000)
    assert result is True
    args = mock_page.goto.call_args
    assert args[1]["timeout"] == 60000


@pytest.mark.asyncio
async def test_safe_navigate_failure(mock_page):
    """Test safe_navigate handles navigation failure."""
    mock_page.goto.side_effect = Exception("Navigation failed")
    result = await safe_navigate(mock_page, "https://example.com")
    assert result is False


@pytest.mark.asyncio
async def test_safe_screenshot_success(mock_page, tmp_path):
    """Test safe_screenshot successful screenshot."""
    filepath = str(tmp_path / "test.png")
    result = await safe_screenshot(mock_page, filepath)
    assert result is True
    mock_page.screenshot.assert_called_once_with(path=filepath, full_page=True)


@pytest.mark.asyncio
async def test_safe_screenshot_not_full_page(mock_page, tmp_path):
    """Test safe_screenshot with full_page=False."""
    filepath = str(tmp_path / "test.png")
    result = await safe_screenshot(mock_page, filepath, full_page=False)
    assert result is True
    args = mock_page.screenshot.call_args
    assert args[1]["full_page"] is False


@pytest.mark.asyncio
async def test_safe_screenshot_failure(mock_page, tmp_path):
    """Test safe_screenshot handles screenshot failure."""
    mock_page.screenshot.side_effect = Exception("Screenshot failed")
    filepath = str(tmp_path / "test.png")
    result = await safe_screenshot(mock_page, filepath)
    assert result is False
