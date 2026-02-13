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
