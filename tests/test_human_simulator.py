"""Tests for human simulator functionality."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.anti_detection.human_simulator import HumanSimulator


class TestHumanSimulator:
    """Test human simulator functionality."""

    def test_init_default(self):
        """Test HumanSimulator initialization with defaults."""
        simulator = HumanSimulator()

        assert simulator.config == {}
        assert simulator.mouse_steps == 20
        assert simulator.typing_wpm_range == [40, 80]
        assert simulator.click_delay_range == [0.1, 0.5]
        assert simulator.random_actions is True

    def test_init_custom_config(self):
        """Test HumanSimulator initialization with custom config."""
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

    def test_bezier_curve_points_count(self):
        """Test Bézier curve generates correct number of points."""
        start = (0, 0)
        end = (100, 100)
        steps = 20

        points = HumanSimulator.bezier_curve(start, end, steps)

        assert len(points) == steps

    def test_bezier_curve_start_end_points(self):
        """Test Bézier curve starts and ends at correct positions."""
        start = (50, 75)
        end = (200, 150)
        steps = 30

        points = HumanSimulator.bezier_curve(start, end, steps)

        # First point should be at start
        assert abs(points[0][0] - start[0]) < 1
        assert abs(points[0][1] - start[1]) < 1

        # Last point should be at end
        assert abs(points[-1][0] - end[0]) < 1
        assert abs(points[-1][1] - end[1]) < 1

    def test_bezier_curve_with_numpy(self):
        """Test Bézier curve with numpy available."""
        start = (0, 0)
        end = (100, 100)
        steps = 15

        points = HumanSimulator.bezier_curve(start, end, steps)

        assert len(points) == steps
        # Verify points are tuples/lists with 2 elements
        for point in points:
            assert len(point) == 2

    def test_bezier_curve_without_numpy(self):
        """Test Bézier curve fallback without numpy."""
        with patch("src.utils.anti_detection.human_simulator.np", None):
            start = (10, 20)
            end = (110, 120)
            steps = 25

            points = HumanSimulator.bezier_curve(start, end, steps)

            assert len(points) == steps
            # Verify curve starts and ends correctly
            assert abs(points[0][0] - start[0]) < 1
            assert abs(points[-1][0] - end[0]) < 1

    @pytest.mark.asyncio
    async def test_human_mouse_move(self):
        """Test human mouse movement."""
        simulator = HumanSimulator()
        mock_page = AsyncMock()

        await simulator.human_mouse_move(mock_page, 500, 300)

        # Verify mouse.move was called multiple times
        assert mock_page.mouse.move.call_count >= 15
        assert mock_page.mouse.move.call_count <= 30

    @pytest.mark.asyncio
    async def test_human_mouse_move_error(self):
        """Test human mouse movement handles errors."""
        simulator = HumanSimulator()
        mock_page = AsyncMock()
        mock_page.mouse.move.side_effect = Exception("Mouse error")

        # Should not raise exception
        await simulator.human_mouse_move(mock_page, 500, 300)

    @pytest.mark.asyncio
    async def test_human_click_success(self):
        """Test human click success."""
        simulator = HumanSimulator()
        mock_page = AsyncMock()
        mock_element = MagicMock()
        mock_element.wait_for = AsyncMock()
        mock_element.bounding_box = AsyncMock(
            return_value={"x": 100, "y": 100, "width": 50, "height": 30}
        )

        mock_page.locator = MagicMock(return_value=mock_element)

        result = await simulator.human_click(mock_page, "#button")

        assert result is True
        mock_element.wait_for.assert_called_once()
        mock_page.mouse.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_human_click_no_bounding_box(self):
        """Test human click when bounding box is not available."""
        simulator = HumanSimulator()
        mock_page = AsyncMock()
        mock_element = MagicMock()
        mock_element.wait_for = AsyncMock()
        mock_element.bounding_box = AsyncMock(return_value=None)

        mock_page.locator = MagicMock(return_value=mock_element)

        result = await simulator.human_click(mock_page, "#button")

        assert result is False

    @pytest.mark.asyncio
    async def test_human_click_error(self):
        """Test human click handles errors."""
        simulator = HumanSimulator()
        mock_page = AsyncMock()
        mock_element = MagicMock()
        mock_element.wait_for = AsyncMock(side_effect=Exception("Element not found"))

        mock_page.locator = MagicMock(return_value=mock_element)

        result = await simulator.human_click(mock_page, "#button")

        assert result is False

    @pytest.mark.asyncio
    async def test_human_type_success(self):
        """Test human typing success."""
        simulator = HumanSimulator({"typing_wpm_range": [60, 60]})  # Fixed WPM for testing
        mock_page = AsyncMock()
        mock_element = MagicMock()
        mock_element.wait_for = AsyncMock()
        mock_element.bounding_box = AsyncMock(
            return_value={"x": 100, "y": 100, "width": 200, "height": 30}
        )

        mock_page.locator = MagicMock(return_value=mock_element)

        result = await simulator.human_type(mock_page, "#input", "test")

        assert result is True
        # Verify keyboard.type was called for each character
        assert mock_page.keyboard.type.call_count == 4  # "test" has 4 characters

    @pytest.mark.asyncio
    async def test_human_type_error(self):
        """Test human typing handles errors."""
        simulator = HumanSimulator()
        mock_page = AsyncMock()
        mock_element = MagicMock()
        mock_element.wait_for = AsyncMock(side_effect=Exception("Element not visible"))

        mock_page.locator = MagicMock(return_value=mock_element)

        result = await simulator.human_type(mock_page, "#input", "test")

        assert result is False

    @pytest.mark.asyncio
    async def test_random_scroll(self):
        """Test random scroll behavior."""
        simulator = HumanSimulator()
        mock_page = AsyncMock()

        await simulator.random_scroll(mock_page)

        # Verify wheel was called multiple times (3-7 chunks)
        assert mock_page.mouse.wheel.call_count >= 3
        assert mock_page.mouse.wheel.call_count <= 7

    @pytest.mark.asyncio
    async def test_random_scroll_error(self):
        """Test random scroll handles errors."""
        simulator = HumanSimulator()
        mock_page = AsyncMock()
        mock_page.mouse.wheel.side_effect = Exception("Scroll error")

        # Should not raise exception
        await simulator.random_scroll(mock_page)

    @pytest.mark.asyncio
    async def test_random_human_action_scroll(self):
        """Test random human action - scroll."""
        simulator = HumanSimulator()
        mock_page = AsyncMock()

        # Force scroll action
        with patch("random.choice", return_value="scroll"):
            await simulator.random_human_action(mock_page)

            # Verify scroll was performed
            assert mock_page.mouse.wheel.call_count >= 3

    @pytest.mark.asyncio
    async def test_random_human_action_mouse_move(self):
        """Test random human action - mouse move."""
        simulator = HumanSimulator()
        mock_page = AsyncMock()

        # Force mouse_move action
        with patch("random.choice", return_value="mouse_move"):
            await simulator.random_human_action(mock_page)

            # Verify mouse move was performed
            assert mock_page.mouse.move.call_count >= 15

    @pytest.mark.asyncio
    async def test_random_human_action_pause(self):
        """Test random human action - pause."""
        simulator = HumanSimulator()
        mock_page = AsyncMock()

        # Force pause action
        with patch("random.choice", return_value="pause"):
            await simulator.random_human_action(mock_page)

            # No mouse actions should be called
            mock_page.mouse.move.assert_not_called()
            mock_page.mouse.wheel.assert_not_called()

    @pytest.mark.asyncio
    async def test_random_human_action_disabled(self):
        """Test random human action when disabled."""
        simulator = HumanSimulator({"random_actions": False})
        mock_page = AsyncMock()

        await simulator.random_human_action(mock_page)

        # No actions should be performed
        mock_page.mouse.move.assert_not_called()
        mock_page.mouse.wheel.assert_not_called()

    @pytest.mark.asyncio
    async def test_random_human_action_error(self):
        """Test random human action handles errors."""
        simulator = HumanSimulator()
        mock_page = AsyncMock()
        mock_page.mouse.wheel.side_effect = Exception("Action error")

        with patch("random.choice", return_value="scroll"):
            # Should not raise exception
            await simulator.random_human_action(mock_page)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
