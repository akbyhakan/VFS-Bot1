"""Edge-case tests for SlotChecker.check_slots() and _normalize_date()."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import VFSBotError
from src.services.bot.slot_checker import SlotChecker, SlotCheckerDeps


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config():
    """Minimal config required by SlotChecker."""
    return {"vfs": {"mission": "test"}}


@pytest.fixture
def mock_rate_limiter():
    """Mock RateLimiter."""
    rl = MagicMock()
    rl.acquire = AsyncMock()
    return rl


@pytest.fixture
def mock_page_state_detector():
    """Mock PageStateDetector (not used in edge-case tests; navigation is patched)."""
    return MagicMock()


def _make_slot_checker(config, rate_limiter, *, page_state_detector=None, error_capture=None):
    """Helper: create SlotChecker with a patched selector_manager to avoid import errors."""
    deps = SlotCheckerDeps(
        page_state_detector=page_state_detector,
        selector_manager=MagicMock(),
        error_capture=error_capture,
    )
    return SlotChecker(config=config, rate_limiter=rate_limiter, deps=deps)


def _make_page_with_slots(date_side_effect, time_side_effect=None):
    """
    Build a mock page that reports 1 available slot, with configurable
    text_content side-effects for date and time locators.
    """
    page = MagicMock()
    page.select_option = AsyncMock()

    # Single locator mock: count() returns 1 (slots available), and .first.text_content()
    # returns the supplied side_effect values in order.
    mock_first = MagicMock()
    if time_side_effect is not None:
        mock_first.text_content = AsyncMock(
            side_effect=[date_side_effect, time_side_effect]
        )
    else:
        mock_first.text_content = AsyncMock(side_effect=date_side_effect)

    mock_locator = MagicMock()
    mock_locator.count = AsyncMock(return_value=1)
    mock_locator.first = mock_first

    page.locator = MagicMock(return_value=mock_locator)
    return page


# ---------------------------------------------------------------------------
# TimeoutError handling
# ---------------------------------------------------------------------------


class TestTimeoutErrorHandling:
    """TimeoutError when reading text_content → check_slots returns None."""

    @pytest.mark.asyncio
    async def test_timeout_reading_date_returns_none(self, config, mock_rate_limiter):
        """TimeoutError reading date text_content → None."""
        checker = _make_slot_checker(config, mock_rate_limiter)

        mock_first = MagicMock()
        mock_first.text_content = AsyncMock(side_effect=asyncio.TimeoutError())

        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_locator.first = mock_first

        page = MagicMock()
        page.select_option = AsyncMock()
        page.locator = MagicMock(return_value=mock_locator)

        with patch("src.services.bot.slot_checker.navigate_to_appointment_page"):
            result = await checker.check_slots(page, "Centre", "Cat", "Subcat")

        assert result is None

    @pytest.mark.asyncio
    async def test_timeout_reading_time_returns_none(self, config, mock_rate_limiter):
        """TimeoutError reading time text_content → None."""
        checker = _make_slot_checker(config, mock_rate_limiter)

        mock_first = MagicMock()
        # First call (date) succeeds; second call (time) times out
        mock_first.text_content = AsyncMock(
            side_effect=["15/03/2026", asyncio.TimeoutError()]
        )

        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_locator.first = mock_first

        page = MagicMock()
        page.select_option = AsyncMock()
        page.locator = MagicMock(return_value=mock_locator)

        with patch("src.services.bot.slot_checker.navigate_to_appointment_page"):
            result = await checker.check_slots(page, "Centre", "Cat", "Subcat")

        assert result is None


# ---------------------------------------------------------------------------
# Empty / None text_content
# ---------------------------------------------------------------------------


class TestEmptyOrNoneContent:
    """Empty strings and None from text_content → check_slots returns None."""

    @pytest.mark.asyncio
    async def test_empty_date_string_returns_none(self, config, mock_rate_limiter):
        """date='' with slots available → None."""
        checker = _make_slot_checker(config, mock_rate_limiter)
        page = _make_page_with_slots(date_side_effect="", time_side_effect="10:00")

        with patch("src.services.bot.slot_checker.navigate_to_appointment_page"):
            result = await checker.check_slots(page, "Centre", "Cat", "Subcat")

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_time_string_returns_none(self, config, mock_rate_limiter):
        """time='' with slots available → None."""
        checker = _make_slot_checker(config, mock_rate_limiter)
        page = _make_page_with_slots(date_side_effect="15/03/2026", time_side_effect="")

        with patch("src.services.bot.slot_checker.navigate_to_appointment_page"):
            result = await checker.check_slots(page, "Centre", "Cat", "Subcat")

        assert result is None

    @pytest.mark.asyncio
    async def test_none_text_content_returns_none(self, config, mock_rate_limiter):
        """None from text_content → None (date strips to empty string)."""
        checker = _make_slot_checker(config, mock_rate_limiter)
        page = _make_page_with_slots(date_side_effect=None, time_side_effect="10:00")

        with patch("src.services.bot.slot_checker.navigate_to_appointment_page"):
            result = await checker.check_slots(page, "Centre", "Cat", "Subcat")

        assert result is None


# ---------------------------------------------------------------------------
# Error capture integration
# ---------------------------------------------------------------------------


class TestErrorCaptureIntegration:
    """General exceptions trigger error_capture.capture(); VFSBotError is re-raised."""

    @pytest.mark.asyncio
    async def test_general_exception_triggers_error_capture(
        self, config, mock_rate_limiter
    ):
        """RuntimeError calls error_capture.capture() with correct context."""
        mock_error_capture = MagicMock()
        mock_error_capture.capture = AsyncMock()

        deps = SlotCheckerDeps(
            selector_manager=MagicMock(),
            error_capture=mock_error_capture,
        )
        checker = SlotChecker(config=config, rate_limiter=mock_rate_limiter, deps=deps)

        page = MagicMock()
        page.select_option = AsyncMock(side_effect=RuntimeError("boom"))

        with patch("src.services.bot.slot_checker.navigate_to_appointment_page"):
            result = await checker.check_slots(page, "CentreA", "Cat", "Subcat")

        assert result is None
        mock_error_capture.capture.assert_called_once()
        call_args = mock_error_capture.capture.call_args
        # positional: page, exception
        assert call_args[0][0] is page
        assert isinstance(call_args[0][1], RuntimeError)
        # keyword: context
        ctx = call_args[1]["context"] if "context" in call_args[1] else call_args[0][2]
        assert ctx["step"] == "check_slots"
        assert ctx["centre"] == "CentreA"

    @pytest.mark.asyncio
    async def test_vfs_bot_error_is_reraised_without_capture(
        self, config, mock_rate_limiter
    ):
        """VFSBotError propagates without calling error_capture.capture()."""
        mock_error_capture = MagicMock()
        mock_error_capture.capture = AsyncMock()

        deps = SlotCheckerDeps(
            selector_manager=MagicMock(),
            error_capture=mock_error_capture,
        )
        checker = SlotChecker(config=config, rate_limiter=mock_rate_limiter, deps=deps)

        page = MagicMock()
        page.select_option = AsyncMock(
            side_effect=VFSBotError("session expired", recoverable=True)
        )

        with patch("src.services.bot.slot_checker.navigate_to_appointment_page"):
            with pytest.raises(VFSBotError):
                await checker.check_slots(page, "Centre", "Cat", "Subcat")

        mock_error_capture.capture.assert_not_called()


# ---------------------------------------------------------------------------
# CloudflareHandler integration
# ---------------------------------------------------------------------------


class TestCloudflareHandlerIntegration:
    """When cloudflare_handler is set, handle_challenge(page) is called."""

    @pytest.mark.asyncio
    async def test_cloudflare_handle_challenge_is_called(
        self, config, mock_rate_limiter
    ):
        """cloudflare_handler.handle_challenge(page) is called during check_slots."""
        mock_cf = MagicMock()
        mock_cf.handle_challenge = AsyncMock(return_value=True)

        deps = SlotCheckerDeps(
            selector_manager=MagicMock(),
            cloudflare_handler=mock_cf,
        )
        checker = SlotChecker(config=config, rate_limiter=mock_rate_limiter, deps=deps)

        page = MagicMock()
        page.select_option = AsyncMock()
        page.locator = MagicMock(return_value=MagicMock(count=AsyncMock(return_value=0)))

        with patch("src.services.bot.slot_checker.navigate_to_appointment_page"):
            await checker.check_slots(page, "Centre", "Cat", "Subcat")

        mock_cf.handle_challenge.assert_called_once_with(page)


# ---------------------------------------------------------------------------
# _normalize_date unit tests
# ---------------------------------------------------------------------------


class TestNormalizeDate:
    """Unit tests for SlotChecker._normalize_date."""

    @pytest.fixture
    def checker(self, config, mock_rate_limiter):
        return _make_slot_checker(config, mock_rate_limiter)

    def test_dd_slash_mm_slash_yyyy_unchanged(self, checker):
        assert checker._normalize_date("15/03/2026") == "15/03/2026"

    def test_dd_dash_mm_dash_yyyy(self, checker):
        assert checker._normalize_date("15-03-2026") == "15/03/2026"

    def test_dd_dot_mm_dot_yyyy(self, checker):
        assert checker._normalize_date("15.03.2026") == "15/03/2026"

    def test_yyyy_dash_mm_dash_dd(self, checker):
        assert checker._normalize_date("2026-03-15") == "15/03/2026"

    def test_yyyy_slash_mm_slash_dd(self, checker):
        assert checker._normalize_date("2026/03/15") == "15/03/2026"

    def test_yyyy_dot_mm_dot_dd(self, checker):
        assert checker._normalize_date("2026.03.15") == "15/03/2026"

    def test_whitespace_is_trimmed(self, checker):
        assert checker._normalize_date("  15/03/2026  ") == "15/03/2026"
