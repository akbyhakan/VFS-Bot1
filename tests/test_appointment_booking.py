"""Tests for appointment booking service, focusing on smart time selection."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from src.services.booking import BookingOrchestrator


class MockLocator:
    """Mock Playwright locator."""

    def __init__(self, text_content):
        self._text_content = text_content
        self.clicked = False

    async def text_content(self):
        return self._text_content

    async def click(self):
        self.clicked = True


class TestSelectPreferredTime:
    """Tests for select_preferred_time method."""

    @pytest.fixture
    def service(self):
        """Create BookingOrchestrator instance with minimal config."""
        config = {
            "vfs": {"mission": "nld"},
            "applicants": [{"first_name": "Test"}],
        }
        return BookingOrchestrator(config)

    @pytest.fixture
    def mock_page(self):
        """Create mock Playwright page."""
        page = AsyncMock()
        page.wait_for_selector = AsyncMock()
        page.locator = Mock()
        return page

    @pytest.mark.asyncio
    async def test_select_preferred_time_prefers_0900_plus(self, service, mock_page):
        """Test that 09:00+ slots are preferred over earlier times."""
        # Setup: Mix of 08:00, 09:00, and 10:00 slots
        slots = [
            MockLocator("08:30"),
            MockLocator("09:00"),
            MockLocator("10:30"),
        ]

        mock_page.locator.return_value.all = AsyncMock(return_value=slots)

        # Execute
        result = await service.select_preferred_time(mock_page)

        # Assert: Should select 09:00 (first 09:00+ slot)
        assert result is True
        # Verify that a 09:00+ slot was clicked (not the 08:30 slot)
        assert not slots[0].clicked  # 08:30 should not be clicked
        assert slots[1].clicked or slots[2].clicked  # Either 09:00 or 10:30 should be clicked

    @pytest.mark.asyncio
    async def test_select_preferred_time_fallback_0800(self, service, mock_page):
        """Test that 08:00-08:59 slots are used when no 09:00+ available."""
        # Setup: Only 08:00 range slots
        slots = [
            MockLocator("08:00"),
            MockLocator("08:30"),
            MockLocator("08:45"),
        ]

        mock_page.locator.return_value.all = AsyncMock(return_value=slots)

        # Execute
        result = await service.select_preferred_time(mock_page)

        # Assert: Should select first 08:00 slot as fallback
        assert result is True
        assert slots[0].clicked  # First 08:00 slot should be clicked

    @pytest.mark.asyncio
    async def test_select_preferred_time_skip_before_0800(self, service, mock_page):
        """Test that slots before 08:00 are skipped."""
        # Setup: Only early morning slots
        slots = [
            MockLocator("06:00"),
            MockLocator("07:00"),
            MockLocator("07:30"),
        ]

        mock_page.locator.return_value.all = AsyncMock(return_value=slots)

        # Execute
        result = await service.select_preferred_time(mock_page)

        # Assert: Should return False (no acceptable slots)
        assert result is False

    @pytest.mark.asyncio
    async def test_select_preferred_time_mixed_slots(self, service, mock_page):
        """Test correct selection with mixed time slots."""
        # Setup: Mix including before 08:00, 08:00-09:00, and 09:00+
        slots = [
            MockLocator("07:00"),  # Skip
            MockLocator("08:15"),  # Fallback
            MockLocator("09:30"),  # Preferred (should be selected)
            MockLocator("11:00"),  # Preferred
        ]

        mock_page.locator.return_value.all = AsyncMock(return_value=slots)

        # Execute
        result = await service.select_preferred_time(mock_page)

        # Assert: Should select first 09:00+ slot (09:30)
        assert result is True
        assert not slots[0].clicked  # 07:00 should not be clicked
        assert not slots[1].clicked  # 08:15 should not be clicked
        assert slots[2].clicked  # 09:30 should be clicked

    @pytest.mark.asyncio
    async def test_select_preferred_time_no_slots(self, service, mock_page):
        """Test behavior when no time slots are available."""
        # Setup: Empty slots list
        mock_page.locator.return_value.all = AsyncMock(return_value=[])

        # Execute
        result = await service.select_preferred_time(mock_page)

        # Assert: Should return False
        assert result is False

    @pytest.mark.asyncio
    async def test_select_preferred_time_invalid_time_format(self, service, mock_page):
        """Test handling of invalid time format."""
        # Setup: Invalid time formats mixed with valid
        slots = [
            MockLocator("invalid"),
            MockLocator("09:00"),
            MockLocator("not a time"),
        ]

        mock_page.locator.return_value.all = AsyncMock(return_value=slots)

        # Execute
        result = await service.select_preferred_time(mock_page)

        # Assert: Should still select valid 09:00 slot
        assert result is True
        assert slots[1].clicked  # 09:00 should be clicked

    @pytest.mark.asyncio
    async def test_select_preferred_time_empty_text_content(self, service, mock_page):
        """Test handling of slots with empty text content."""
        # Setup: Mix of empty and valid slots
        slots = [
            MockLocator(None),
            MockLocator(""),
            MockLocator("09:00"),
        ]

        mock_page.locator.return_value.all = AsyncMock(return_value=slots)

        # Execute
        result = await service.select_preferred_time(mock_page)

        # Assert: Should find and select the valid 09:00 slot
        assert result is True
        assert slots[2].clicked  # Valid 09:00 slot should be clicked

    @pytest.mark.asyncio
    async def test_select_preferred_time_exception_handling(self, service, mock_page):
        """Test that exceptions are handled gracefully."""
        # Setup: Simulate an exception during selector wait
        mock_page.wait_for_selector.side_effect = Exception("Selector timeout")

        # Execute
        result = await service.select_preferred_time(mock_page)

        # Assert: Should return False on exception
        assert result is False

    @pytest.mark.asyncio
    async def test_select_preferred_time_boundary_08_00(self, service, mock_page):
        """Test boundary condition: exactly 08:00."""
        # Setup: Exactly 08:00 slot
        slots = [MockLocator("08:00")]

        mock_page.locator.return_value.all = AsyncMock(return_value=slots)

        # Execute
        result = await service.select_preferred_time(mock_page)

        # Assert: 08:00 should be accepted as fallback
        assert result is True

    @pytest.mark.asyncio
    async def test_select_preferred_time_boundary_09_00(self, service, mock_page):
        """Test boundary condition: exactly 09:00."""
        # Setup: Exactly 09:00 slot
        slots = [MockLocator("09:00")]

        mock_page.locator.return_value.all = AsyncMock(return_value=slots)

        # Execute
        result = await service.select_preferred_time(mock_page)

        # Assert: 09:00 should be accepted as preferred
        assert result is True

    @pytest.mark.asyncio
    async def test_select_preferred_time_whitespace_handling(self, service, mock_page):
        """Test that time strings with whitespace are handled correctly."""
        # Setup: Times with extra whitespace
        slots = [
            MockLocator("  09:00  "),
            MockLocator("\t10:30\n"),
        ]

        mock_page.locator.return_value.all = AsyncMock(return_value=slots)

        # Execute
        result = await service.select_preferred_time(mock_page)

        # Assert: Should strip whitespace and select correctly
        assert result is True
        assert slots[0].clicked  # First 09:00+ slot should be clicked
