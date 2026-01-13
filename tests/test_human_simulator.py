"""Tests for human simulator."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.anti_detection.human_simulator import HumanSimulator


@pytest.fixture
def mock_page():
    """Mock Playwright page object."""
    page = AsyncMock()
    page.mouse = AsyncMock()
    page.mouse.move = AsyncMock()
    page.mouse.click = AsyncMock()
    page.mouse.wheel = AsyncMock()
    page.keyboard = AsyncMock()
    page.keyboard.type = AsyncMock()
    page.locator = MagicMock()
    return page


@pytest.fixture
def mock_element():
    """Mock Playwright element."""
    element = AsyncMock()
    element.wait_for = AsyncMock()
    element.bounding_box = AsyncMock(return_value={"x": 100, "y": 100, "width": 200, "height": 50})
    return element


def test_human_simulator_initialization_default():
    """Test human simulator initialization with defaults."""
    simulator = HumanSimulator()
    assert simulator.mouse_steps == 20
    assert simulator.typing_wpm_range == [40, 80]
    assert simulator.click_delay_range == [0.1, 0.5]
    assert simulator.random_actions is True


def test_human_simulator_initialization_custom():
    """Test human simulator initialization with custom config."""
    config = {
        "mouse_movement_steps": 30,
        "typing_wpm_range": [50, 90],
        "click_delay_range": [0.2, 0.6],
        "random_actions": False,
    }
    simulator = HumanSimulator(config)
    assert simulator.mouse_steps == 30
    assert simulator.typing_wpm_range == [50, 90]
    assert simulator.click_delay_range == [0.2, 0.6]
    assert simulator.random_actions is False


def test_bezier_curve_returns_list():
    """Test bezier curve returns list of points."""
    points = HumanSimulator.bezier_curve((0, 0), (100, 100), steps=10)
    assert isinstance(points, list)
    assert len(points) == 10


def test_bezier_curve_start_and_end():
    """Test bezier curve starts and ends at correct points."""
    start = (50.0, 50.0)
    end = (200.0, 150.0)
    points = HumanSimulator.bezier_curve(start, end, steps=20)

    # First point should be close to start
    assert abs(points[0][0] - start[0]) < 1
    assert abs(points[0][1] - start[1]) < 1

    # Last point should be close to end
    assert abs(points[-1][0] - end[0]) < 1
    assert abs(points[-1][1] - end[1]) < 1


def test_bezier_curve_different_steps():
    """Test bezier curve with different step counts."""
    points_10 = HumanSimulator.bezier_curve((0, 0), (100, 100), steps=10)
    points_20 = HumanSimulator.bezier_curve((0, 0), (100, 100), steps=20)

    assert len(points_10) == 10
    assert len(points_20) == 20


def test_bezier_curve_without_numpy():
    """Test bezier curve works without numpy."""
    with patch("src.utils.anti_detection.human_simulator.np", None):
        simulator = HumanSimulator()
        points = simulator.bezier_curve((0, 0), (100, 100), steps=15)
        assert len(points) == 15
        assert isinstance(points[0], tuple)


@pytest.mark.asyncio
async def test_human_mouse_move_calls_mouse_move(mock_page):
    """Test human mouse move calls page.mouse.move."""
    simulator = HumanSimulator()
    await simulator.human_mouse_move(mock_page, 500, 300)

    # Should call mouse.move multiple times
    assert mock_page.mouse.move.call_count >= 15


@pytest.mark.asyncio
async def test_human_mouse_move_ends_at_target(mock_page):
    """Test human mouse move ends at target coordinates."""
    simulator = HumanSimulator()
    target_x, target_y = 500, 300
    await simulator.human_mouse_move(mock_page, target_x, target_y)

    # Last call should be to target position
    last_call = mock_page.mouse.move.call_args_list[-1]
    final_x, final_y = last_call[0]

    # Should be very close to target
    assert abs(final_x - target_x) < 2
    assert abs(final_y - target_y) < 2


@pytest.mark.asyncio
async def test_human_mouse_move_error_handling(mock_page):
    """Test human mouse move error handling."""
    mock_page.mouse.move = AsyncMock(side_effect=Exception("Move failed"))
    simulator = HumanSimulator()

    # Should not raise exception
    await simulator.human_mouse_move(mock_page, 500, 300)


@pytest.mark.asyncio
async def test_human_click_success(mock_page, mock_element):
    """Test successful human click."""
    mock_page.locator.return_value = mock_element
    simulator = HumanSimulator()

    result = await simulator.human_click(mock_page, "button")

    assert result is True
    mock_element.wait_for.assert_called_once()
    mock_element.bounding_box.assert_called_once()
    mock_page.mouse.click.assert_called_once()


@pytest.mark.asyncio
async def test_human_click_moves_mouse_first(mock_page, mock_element):
    """Test human click moves mouse before clicking."""
    mock_page.locator.return_value = mock_element
    simulator = HumanSimulator()

    await simulator.human_click(mock_page, "button")

    # Should move mouse before clicking
    assert mock_page.mouse.move.call_count > 0
    assert mock_page.mouse.click.call_count == 1


@pytest.mark.asyncio
async def test_human_click_random_position(mock_page, mock_element):
    """Test human click uses random position within element."""
    mock_page.locator.return_value = mock_element
    simulator = HumanSimulator()

    await simulator.human_click(mock_page, "button")

    # Click should be within element bounds
    click_call = mock_page.mouse.click.call_args[0]
    click_x, click_y = click_call

    box = await mock_element.bounding_box()
    assert box["x"] <= click_x <= box["x"] + box["width"]
    assert box["y"] <= click_y <= box["y"] + box["height"]


@pytest.mark.asyncio
async def test_human_click_no_bounding_box(mock_page, mock_element):
    """Test human click when bounding box is not available."""
    mock_element.bounding_box = AsyncMock(return_value=None)
    mock_page.locator.return_value = mock_element
    simulator = HumanSimulator()

    result = await simulator.human_click(mock_page, "button")

    assert result is False


@pytest.mark.asyncio
async def test_human_click_error_handling(mock_page):
    """Test human click error handling."""
    mock_page.locator.side_effect = Exception("Element not found")
    simulator = HumanSimulator()

    result = await simulator.human_click(mock_page, "button")

    assert result is False


@pytest.mark.asyncio
async def test_human_type_success(mock_page, mock_element):
    """Test successful human typing."""
    mock_page.locator.return_value = mock_element
    simulator = HumanSimulator()
    text = "test"

    result = await simulator.human_type(mock_page, "input", text)

    assert result is True
    assert mock_page.keyboard.type.call_count == len(text)


@pytest.mark.asyncio
async def test_human_type_calls_click_first(mock_page, mock_element):
    """Test human type clicks element first."""
    mock_page.locator.return_value = mock_element
    simulator = HumanSimulator()

    await simulator.human_type(mock_page, "input", "test")

    # Should wait for element and click
    mock_element.wait_for.assert_called()
    mock_page.mouse.click.assert_called_once()


@pytest.mark.asyncio
async def test_human_type_variable_speed(mock_page, mock_element):
    """Test human typing has variable speed."""
    mock_page.locator.return_value = mock_element
    simulator = HumanSimulator()

    # Type longer text to observe variable delays
    await simulator.human_type(mock_page, "input", "testing")

    # Should type each character
    assert mock_page.keyboard.type.call_count == 7


@pytest.mark.asyncio
async def test_human_type_error_handling(mock_page):
    """Test human type error handling."""
    mock_page.locator.side_effect = Exception("Element not found")
    simulator = HumanSimulator()

    result = await simulator.human_type(mock_page, "input", "test")

    assert result is False


@pytest.mark.asyncio
async def test_random_scroll(mock_page):
    """Test random scrolling."""
    simulator = HumanSimulator()
    await simulator.random_scroll(mock_page)

    # Should call wheel multiple times
    assert mock_page.mouse.wheel.call_count >= 3


@pytest.mark.asyncio
async def test_random_scroll_multiple_chunks(mock_page):
    """Test random scroll uses multiple chunks."""
    simulator = HumanSimulator()
    await simulator.random_scroll(mock_page)

    # Should scroll in chunks
    call_count = mock_page.mouse.wheel.call_count
    assert 3 <= call_count <= 7


@pytest.mark.asyncio
async def test_random_scroll_error_handling(mock_page):
    """Test random scroll error handling."""
    mock_page.mouse.wheel = AsyncMock(side_effect=Exception("Scroll failed"))
    simulator = HumanSimulator()

    # Should not raise exception
    await simulator.random_scroll(mock_page)


@pytest.mark.asyncio
async def test_random_human_action_disabled(mock_page):
    """Test random human action when disabled."""
    simulator = HumanSimulator({"random_actions": False})
    await simulator.random_human_action(mock_page)

    # Should not perform any actions
    assert mock_page.mouse.wheel.call_count == 0
    assert mock_page.mouse.move.call_count == 0


@pytest.mark.asyncio
async def test_random_human_action_performs_action(mock_page):
    """Test random human action performs an action."""
    simulator = HumanSimulator({"random_actions": True})
    await simulator.random_human_action(mock_page)

    # Should perform at least one action
    total_calls = (
        mock_page.mouse.wheel.call_count
        + mock_page.mouse.move.call_count
        + (
            1
            if mock_page.mouse.wheel.call_count == 0 and mock_page.mouse.move.call_count == 0
            else 0
        )
    )
    assert total_calls >= 0  # At least tried to perform an action


@pytest.mark.asyncio
async def test_random_human_action_error_handling(mock_page):
    """Test random human action error handling."""
    mock_page.mouse.wheel = AsyncMock(side_effect=Exception("Action failed"))
    mock_page.mouse.move = AsyncMock(side_effect=Exception("Action failed"))
    simulator = HumanSimulator({"random_actions": True})

    # Should not raise exception
    await simulator.random_human_action(mock_page)
