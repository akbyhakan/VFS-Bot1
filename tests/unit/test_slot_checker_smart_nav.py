"""Tests for SlotChecker smart navigation feature."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import VFSBotError
from src.services.bot.page_state_detector import PageState, PageStateResult
from src.services.bot.slot_checker import SlotChecker


class TestSlotCheckerSmartNavigation:
    """Test smart navigation feature in SlotChecker."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return {
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tur",
                "language": "tr",
                "mission": "turkey-istanbul",
            }
        }

    @pytest.fixture
    def mock_rate_limiter(self):
        """Create mock rate limiter."""
        rate_limiter = MagicMock()
        rate_limiter.acquire = AsyncMock()
        return rate_limiter

    @pytest.fixture
    def mock_page_state_detector(self):
        """Create mock page state detector."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_smart_nav_skips_navigation_when_on_appointment_page(
        self, config, mock_rate_limiter, mock_page_state_detector
    ):
        """Test that safe_navigate is NOT called when already on appointment page."""
        # Setup page state detector to indicate we're already on appointment page
        mock_page_state_detector.detect = AsyncMock(
            return_value=PageStateResult(
                state=PageState.APPOINTMENT_PAGE,
                confidence=0.85,
                url="https://visa.vfsglobal.com/tur/tr/turkey-istanbul/appointment",
                details={},
            )
        )

        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=mock_page_state_detector,
        )

        mock_page = AsyncMock()

        with patch("src.services.bot.slot_checker.safe_navigate") as mock_safe_navigate:
            mock_safe_navigate.return_value = True

            # Mock page.select_option and page.locator to avoid errors
            mock_page.select_option = AsyncMock()
            mock_page.locator.return_value.count = AsyncMock(return_value=0)

            result = await slot_checker.check_slots(
                mock_page, "Centre Name", "Visa Category", "Subcategory"
            )

            # Verify safe_navigate was NOT called
            mock_safe_navigate.assert_not_called()
            # Verify page state detector was called
            mock_page_state_detector.detect.assert_called_once_with(mock_page)

    @pytest.mark.asyncio
    async def test_smart_nav_navigates_when_on_different_page(
        self, config, mock_rate_limiter, mock_page_state_detector
    ):
        """Test that safe_navigate IS called when on a different page."""
        # Setup page state detector to indicate we're on login page
        mock_page_state_detector.detect = AsyncMock(
            return_value=PageStateResult(
                state=PageState.LOGIN_PAGE,
                confidence=0.90,
                url="https://visa.vfsglobal.com/tur/tr/turkey-istanbul/login",
                details={},
            )
        )

        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=mock_page_state_detector,
        )

        mock_page = AsyncMock()

        with patch("src.services.bot.slot_checker.safe_navigate") as mock_safe_navigate:
            mock_safe_navigate.return_value = True

            # Mock page.select_option and page.locator to avoid errors
            mock_page.select_option = AsyncMock()
            mock_page.locator.return_value.count = AsyncMock(return_value=0)

            result = await slot_checker.check_slots(
                mock_page, "Centre Name", "Visa Category", "Subcategory"
            )

            # Verify safe_navigate WAS called
            mock_safe_navigate.assert_called_once()
            # Verify page state detector was called
            mock_page_state_detector.detect.assert_called_once_with(mock_page)

    @pytest.mark.asyncio
    async def test_smart_nav_raises_on_session_expired(
        self, config, mock_rate_limiter, mock_page_state_detector
    ):
        """Test that VFSBotError(recoverable=True) is raised when session expired."""
        # Setup page state detector to indicate session expired
        mock_page_state_detector.detect = AsyncMock(
            return_value=PageStateResult(
                state=PageState.SESSION_EXPIRED,
                confidence=0.95,
                url="https://visa.vfsglobal.com/tur/tr/turkey-istanbul/appointment",
                details={},
            )
        )

        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=mock_page_state_detector,
        )

        mock_page = AsyncMock()

        with pytest.raises(VFSBotError) as exc_info:
            await slot_checker.check_slots(
                mock_page, "Centre Name", "Visa Category", "Subcategory"
            )

        assert exc_info.value.recoverable is True
        assert "Page recovery needed" in str(exc_info.value)
        assert "SESSION_EXPIRED" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_smart_nav_raises_on_cloudflare(
        self, config, mock_rate_limiter, mock_page_state_detector
    ):
        """Test that VFSBotError(recoverable=True) is raised on Cloudflare challenge."""
        # Setup page state detector to indicate Cloudflare challenge
        mock_page_state_detector.detect = AsyncMock(
            return_value=PageStateResult(
                state=PageState.CLOUDFLARE_CHALLENGE,
                confidence=0.95,
                url="https://visa.vfsglobal.com/tur/tr/turkey-istanbul/appointment",
                details={},
            )
        )

        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=mock_page_state_detector,
        )

        mock_page = AsyncMock()

        with pytest.raises(VFSBotError) as exc_info:
            await slot_checker.check_slots(
                mock_page, "Centre Name", "Visa Category", "Subcategory"
            )

        assert exc_info.value.recoverable is True
        assert "Page recovery needed" in str(exc_info.value)
        assert "CLOUDFLARE_CHALLENGE" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_smart_nav_falls_back_when_no_detector(self, config, mock_rate_limiter):
        """Test old behavior when page_state_detector=None (always navigate)."""
        # No page state detector
        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=None,
        )

        mock_page = AsyncMock()

        with patch("src.services.bot.slot_checker.safe_navigate") as mock_safe_navigate:
            mock_safe_navigate.return_value = True

            # Mock page.select_option and page.locator to avoid errors
            mock_page.select_option = AsyncMock()
            mock_page.locator.return_value.count = AsyncMock(return_value=0)

            result = await slot_checker.check_slots(
                mock_page, "Centre Name", "Visa Category", "Subcategory"
            )

            # Verify safe_navigate WAS called (old behavior)
            mock_safe_navigate.assert_called_once()

    @pytest.mark.asyncio
    async def test_smart_nav_falls_back_on_detection_error(
        self, config, mock_rate_limiter, mock_page_state_detector
    ):
        """Test that navigation proceeds normally if detect() raises an exception."""
        # Setup page state detector to raise an exception
        mock_page_state_detector.detect = AsyncMock(side_effect=RuntimeError("Detection failed"))

        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=mock_page_state_detector,
        )

        mock_page = AsyncMock()

        with patch("src.services.bot.slot_checker.safe_navigate") as mock_safe_navigate:
            mock_safe_navigate.return_value = True

            # Mock page.select_option and page.locator to avoid errors
            mock_page.select_option = AsyncMock()
            mock_page.locator.return_value.count = AsyncMock(return_value=0)

            result = await slot_checker.check_slots(
                mock_page, "Centre Name", "Visa Category", "Subcategory"
            )

            # Verify safe_navigate WAS called (fallback behavior)
            mock_safe_navigate.assert_called_once()
            # Verify page state detector was called
            mock_page_state_detector.detect.assert_called_once_with(mock_page)

    @pytest.mark.asyncio
    async def test_smart_nav_navigates_on_low_confidence(
        self, config, mock_rate_limiter, mock_page_state_detector
    ):
        """Test that navigation happens when confidence < 0.70."""
        # Setup page state detector with low confidence
        mock_page_state_detector.detect = AsyncMock(
            return_value=PageStateResult(
                state=PageState.APPOINTMENT_PAGE,
                confidence=0.65,  # Below threshold
                url="https://visa.vfsglobal.com/tur/tr/turkey-istanbul/appointment",
                details={},
            )
        )

        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=mock_page_state_detector,
        )

        mock_page = AsyncMock()

        with patch("src.services.bot.slot_checker.safe_navigate") as mock_safe_navigate:
            mock_safe_navigate.return_value = True

            # Mock page.select_option and page.locator to avoid errors
            mock_page.select_option = AsyncMock()
            mock_page.locator.return_value.count = AsyncMock(return_value=0)

            result = await slot_checker.check_slots(
                mock_page, "Centre Name", "Visa Category", "Subcategory"
            )

            # Verify safe_navigate WAS called (low confidence)
            mock_safe_navigate.assert_called_once()
            # Verify page state detector was called
            mock_page_state_detector.detect.assert_called_once_with(mock_page)

    @pytest.mark.asyncio
    async def test_smart_nav_navigates_when_unknown_state(
        self, config, mock_rate_limiter, mock_page_state_detector
    ):
        """Test that safe_navigate IS called when state is UNKNOWN."""
        # Setup page state detector to indicate unknown state
        mock_page_state_detector.detect = AsyncMock(
            return_value=PageStateResult(
                state=PageState.UNKNOWN,
                confidence=0.30,
                url="https://visa.vfsglobal.com/tur/tr/turkey-istanbul/some-page",
                details={},
            )
        )

        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=mock_page_state_detector,
        )

        mock_page = AsyncMock()

        with patch("src.services.bot.slot_checker.safe_navigate") as mock_safe_navigate:
            mock_safe_navigate.return_value = True

            # Mock page.select_option and page.locator to avoid errors
            mock_page.select_option = AsyncMock()
            mock_page.locator.return_value.count = AsyncMock(return_value=0)

            result = await slot_checker.check_slots(
                mock_page, "Centre Name", "Visa Category", "Subcategory"
            )

            # Verify safe_navigate WAS called
            mock_safe_navigate.assert_called_once()
            # Verify page state detector was called
            mock_page_state_detector.detect.assert_called_once_with(mock_page)

    @pytest.mark.asyncio
    async def test_check_slots_insufficient_capacity(
        self, config, mock_rate_limiter, mock_page_state_detector
    ):
        """Test that check_slots returns None when slot capacity is insufficient."""
        # Setup page state detector to skip navigation
        mock_page_state_detector.detect = AsyncMock(
            return_value=PageStateResult(
                state=PageState.APPOINTMENT_PAGE,
                confidence=0.85,
                url="https://visa.vfsglobal.com/tur/tr/turkey-istanbul/appointment",
                details={},
            )
        )

        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=mock_page_state_detector,
        )

        mock_page = AsyncMock()

        with patch("src.services.bot.slot_checker.safe_navigate") as mock_safe_navigate:
            mock_safe_navigate.return_value = True

            # Mock page.select_option
            mock_page.select_option = AsyncMock()

            # Mock slot available (count > 0)
            mock_locator_count = MagicMock()
            mock_locator_count.count = AsyncMock(return_value=1)

            # Mock slot details
            mock_first = MagicMock()
            mock_first.text_content = AsyncMock(side_effect=["2024-02-15", "10:00", "1"])

            mock_page.locator = MagicMock(return_value=mock_locator_count)
            mock_page.locator.return_value.first = mock_first

            # Call with required_capacity=2, but slot has capacity=1
            result = await slot_checker.check_slots(
                mock_page, "Centre Name", "Visa Category", "Subcategory", required_capacity=2
            )

            # Should return None due to insufficient capacity
            assert result is None

    @pytest.mark.asyncio
    async def test_check_slots_sufficient_capacity(
        self, config, mock_rate_limiter, mock_page_state_detector
    ):
        """Test that check_slots returns slot info when capacity is sufficient."""
        # Setup page state detector to skip navigation
        mock_page_state_detector.detect = AsyncMock(
            return_value=PageStateResult(
                state=PageState.APPOINTMENT_PAGE,
                confidence=0.85,
                url="https://visa.vfsglobal.com/tur/tr/turkey-istanbul/appointment",
                details={},
            )
        )

        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=mock_page_state_detector,
        )

        mock_page = AsyncMock()

        with patch("src.services.bot.slot_checker.safe_navigate") as mock_safe_navigate:
            mock_safe_navigate.return_value = True

            # Mock page.select_option
            mock_page.select_option = AsyncMock()

            # Mock slot available (count > 0)
            mock_locator_count = MagicMock()
            mock_locator_count.count = AsyncMock(return_value=1)

            # Mock slot details
            mock_first = MagicMock()
            mock_first.text_content = AsyncMock(side_effect=["2024-02-15", "10:00", "3"])

            mock_page.locator = MagicMock(return_value=mock_locator_count)
            mock_page.locator.return_value.first = mock_first

            # Call with required_capacity=2, slot has capacity=3
            result = await slot_checker.check_slots(
                mock_page, "Centre Name", "Visa Category", "Subcategory", required_capacity=2
            )

            # Should return slot info with capacity
            assert result is not None
            assert result["date"] == "2024-02-15"
            assert result["time"] == "10:00"
            assert result["capacity"] == 3

    @pytest.mark.asyncio
    async def test_check_slots_capacity_selector_not_found_fallback(
        self, config, mock_rate_limiter, mock_page_state_detector
    ):
        """Test graceful fallback when capacity selector is not found."""
        # Setup page state detector to skip navigation
        mock_page_state_detector.detect = AsyncMock(
            return_value=PageStateResult(
                state=PageState.APPOINTMENT_PAGE,
                confidence=0.85,
                url="https://visa.vfsglobal.com/tur/tr/turkey-istanbul/appointment",
                details={},
            )
        )

        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=mock_page_state_detector,
        )

        mock_page = AsyncMock()

        with patch("src.services.bot.slot_checker.safe_navigate") as mock_safe_navigate:
            mock_safe_navigate.return_value = True

            # Mock page.select_option
            mock_page.select_option = AsyncMock()

            # Mock slot available (count > 0)
            mock_locator_count = MagicMock()
            mock_locator_count.count = AsyncMock(return_value=1)

            # Mock slot details - capacity selector throws exception
            mock_first = MagicMock()
            call_count = [0]

            def side_effect_with_exception():
                call_count[0] += 1
                if call_count[0] == 1:
                    return "2024-02-15"
                elif call_count[0] == 2:
                    return "10:00"
                else:
                    raise Exception("Capacity selector not found")

            mock_first.text_content = AsyncMock(side_effect=side_effect_with_exception)

            mock_page.locator = MagicMock(return_value=mock_locator_count)
            mock_page.locator.return_value.first = mock_first

            # Call with required_capacity=2, but capacity selector fails
            result = await slot_checker.check_slots(
                mock_page, "Centre Name", "Visa Category", "Subcategory", required_capacity=2
            )

            # Should still return slot info (graceful fallback)
            assert result is not None
            assert result["date"] == "2024-02-15"
            assert result["time"] == "10:00"
            assert "capacity" not in result  # No capacity field when selector fails

    @pytest.mark.asyncio
    async def test_check_slots_date_not_in_preferred_list(
        self, config, mock_rate_limiter, mock_page_state_detector
    ):
        """Test that check_slots returns None when slot date is not in preferred list."""
        # Setup page state detector to skip navigation
        mock_page_state_detector.detect = AsyncMock(
            return_value=PageStateResult(
                state=PageState.APPOINTMENT_PAGE,
                confidence=0.85,
                url="https://visa.vfsglobal.com/tur/tr/turkey-istanbul/appointment",
                details={},
            )
        )

        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=mock_page_state_detector,
        )

        mock_page = AsyncMock()

        with patch("src.services.bot.slot_checker.safe_navigate") as mock_safe_navigate:
            mock_safe_navigate.return_value = True

            # Mock page.select_option
            mock_page.select_option = AsyncMock()

            # Mock slot available (count > 0)
            mock_locator_count = MagicMock()
            mock_locator_count.count = AsyncMock(return_value=1)

            # Mock slot details - date is 15/03/2026 (not in preferred list)
            mock_first = MagicMock()
            mock_first.text_content = AsyncMock(side_effect=["15/03/2026", "10:00"])

            mock_page.locator = MagicMock(return_value=mock_locator_count)
            mock_page.locator.return_value.first = mock_first

            # Call with preferred_dates that don't include the slot date
            result = await slot_checker.check_slots(
                mock_page,
                "Centre Name",
                "Visa Category",
                "Subcategory",
                required_capacity=1,
                preferred_dates=["20/03/2026", "25/03/2026"],
            )

            # Should return None because date doesn't match
            assert result is None

    @pytest.mark.asyncio
    async def test_check_slots_date_in_preferred_list(
        self, config, mock_rate_limiter, mock_page_state_detector
    ):
        """Test that check_slots returns slot info when date is in preferred list."""
        # Setup page state detector to skip navigation
        mock_page_state_detector.detect = AsyncMock(
            return_value=PageStateResult(
                state=PageState.APPOINTMENT_PAGE,
                confidence=0.85,
                url="https://visa.vfsglobal.com/tur/tr/turkey-istanbul/appointment",
                details={},
            )
        )

        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=mock_page_state_detector,
        )

        mock_page = AsyncMock()

        with patch("src.services.bot.slot_checker.safe_navigate") as mock_safe_navigate:
            mock_safe_navigate.return_value = True

            # Mock page.select_option
            mock_page.select_option = AsyncMock()

            # Mock slot available (count > 0)
            mock_locator_count = MagicMock()
            mock_locator_count.count = AsyncMock(return_value=1)

            # Mock slot details - date is 20/03/2026 (in preferred list)
            mock_first = MagicMock()
            mock_first.text_content = AsyncMock(side_effect=["20/03/2026", "10:00"])

            mock_page.locator = MagicMock(return_value=mock_locator_count)
            mock_page.locator.return_value.first = mock_first

            # Call with preferred_dates that include the slot date
            result = await slot_checker.check_slots(
                mock_page,
                "Centre Name",
                "Visa Category",
                "Subcategory",
                required_capacity=1,
                preferred_dates=["20/03/2026", "25/03/2026"],
            )

            # Should return slot info
            assert result is not None
            assert result["date"] == "20/03/2026"
            assert result["time"] == "10:00"

    @pytest.mark.asyncio
    async def test_check_slots_empty_preferred_dates_accepts_any(
        self, config, mock_rate_limiter, mock_page_state_detector
    ):
        """Test that empty preferred_dates list accepts any date."""
        # Setup page state detector to skip navigation
        mock_page_state_detector.detect = AsyncMock(
            return_value=PageStateResult(
                state=PageState.APPOINTMENT_PAGE,
                confidence=0.85,
                url="https://visa.vfsglobal.com/tur/tr/turkey-istanbul/appointment",
                details={},
            )
        )

        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=mock_page_state_detector,
        )

        mock_page = AsyncMock()

        with patch("src.services.bot.slot_checker.safe_navigate") as mock_safe_navigate:
            mock_safe_navigate.return_value = True

            # Mock page.select_option
            mock_page.select_option = AsyncMock()

            # Mock slot available (count > 0)
            mock_locator_count = MagicMock()
            mock_locator_count.count = AsyncMock(return_value=1)

            # Mock slot details - any date
            mock_first = MagicMock()
            mock_first.text_content = AsyncMock(side_effect=["15/03/2026", "10:00"])

            mock_page.locator = MagicMock(return_value=mock_locator_count)
            mock_page.locator.return_value.first = mock_first

            # Call with empty preferred_dates list
            result = await slot_checker.check_slots(
                mock_page,
                "Centre Name",
                "Visa Category",
                "Subcategory",
                required_capacity=1,
                preferred_dates=[],
            )

            # Should return slot info (empty list = no filter)
            assert result is not None
            assert result["date"] == "15/03/2026"
            assert result["time"] == "10:00"

    @pytest.mark.asyncio
    async def test_check_slots_none_preferred_dates_accepts_any(
        self, config, mock_rate_limiter, mock_page_state_detector
    ):
        """Test that None preferred_dates accepts any date."""
        # Setup page state detector to skip navigation
        mock_page_state_detector.detect = AsyncMock(
            return_value=PageStateResult(
                state=PageState.APPOINTMENT_PAGE,
                confidence=0.85,
                url="https://visa.vfsglobal.com/tur/tr/turkey-istanbul/appointment",
                details={},
            )
        )

        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=mock_page_state_detector,
        )

        mock_page = AsyncMock()

        with patch("src.services.bot.slot_checker.safe_navigate") as mock_safe_navigate:
            mock_safe_navigate.return_value = True

            # Mock page.select_option
            mock_page.select_option = AsyncMock()

            # Mock slot available (count > 0)
            mock_locator_count = MagicMock()
            mock_locator_count.count = AsyncMock(return_value=1)

            # Mock slot details - any date
            mock_first = MagicMock()
            mock_first.text_content = AsyncMock(side_effect=["15/03/2026", "10:00"])

            mock_page.locator = MagicMock(return_value=mock_locator_count)
            mock_page.locator.return_value.first = mock_first

            # Call with None preferred_dates (default)
            result = await slot_checker.check_slots(
                mock_page,
                "Centre Name",
                "Visa Category",
                "Subcategory",
                required_capacity=1,
                preferred_dates=None,
            )

            # Should return slot info (None = no filter)
            assert result is not None
            assert result["date"] == "15/03/2026"
            assert result["time"] == "10:00"

    @pytest.mark.asyncio
    async def test_check_slots_date_format_normalization(
        self, config, mock_rate_limiter, mock_page_state_detector
    ):
        """Test that date formats are normalized for comparison (DD-MM-YYYY vs DD/MM/YYYY)."""
        # Setup page state detector to skip navigation
        mock_page_state_detector.detect = AsyncMock(
            return_value=PageStateResult(
                state=PageState.APPOINTMENT_PAGE,
                confidence=0.85,
                url="https://visa.vfsglobal.com/tur/tr/turkey-istanbul/appointment",
                details={},
            )
        )

        slot_checker = SlotChecker(
            config=config,
            rate_limiter=mock_rate_limiter,
            page_state_detector=mock_page_state_detector,
        )

        mock_page = AsyncMock()

        with patch("src.services.bot.slot_checker.safe_navigate") as mock_safe_navigate:
            mock_safe_navigate.return_value = True

            # Mock page.select_option
            mock_page.select_option = AsyncMock()

            # Mock slot available (count > 0)
            mock_locator_count = MagicMock()
            mock_locator_count.count = AsyncMock(return_value=1)

            # Mock slot details - date with slash format
            mock_first = MagicMock()
            mock_first.text_content = AsyncMock(side_effect=["20/03/2026", "10:00"])

            mock_page.locator = MagicMock(return_value=mock_locator_count)
            mock_page.locator.return_value.first = mock_first

            # Call with preferred_dates in dash format (should match after normalization)
            result = await slot_checker.check_slots(
                mock_page,
                "Centre Name",
                "Visa Category",
                "Subcategory",
                required_capacity=1,
                preferred_dates=["20-03-2026", "25-03-2026"],
            )

            # Should return slot info (formats normalized and matched)
            assert result is not None
            assert result["date"] == "20/03/2026"
            assert result["time"] == "10:00"
