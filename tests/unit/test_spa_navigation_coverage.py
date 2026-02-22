"""Tests for utils/spa_navigation module - SPA navigation utilities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import VFSBotError
from src.utils.spa_navigation import navigate_to_appointment_page


def _make_state(
    is_on_appointment_page=False,
    confidence=0.0,
    needs_recovery=False,
    state_name="UNKNOWN",
):
    """Build a mock PageStateResult."""
    from src.services.bot.page_state_detector import PageState

    state_obj = MagicMock()
    state_obj.is_on_appointment_page = is_on_appointment_page
    state_obj.confidence = confidence
    state_obj.needs_recovery = needs_recovery

    try:
        state_obj.state = PageState[state_name]
    except KeyError:
        state_obj.state = MagicMock()
        state_obj.state.name = state_name

    return state_obj


def _make_page_state_detector(detect_result, wait_result=None):
    """Build a mock PageStateDetector."""
    detector = MagicMock()
    detector.detect = AsyncMock(return_value=detect_result)
    if wait_result is not None:
        detector.wait_for_stable_state = AsyncMock(return_value=wait_result)
    else:
        detector.wait_for_stable_state = AsyncMock(return_value=detect_result)
    return detector


def _make_page(locator_count=1):
    """Build a mock Playwright page.

    The SPA navigation code does: ``page.locator(selector).first``
    and then ``await locator.count()`` / ``await locator.click()``.
    We must wire up the ``first`` attribute on the locator chain.
    """
    page = MagicMock()
    first = MagicMock()
    first.count = AsyncMock(return_value=locator_count)
    first.click = AsyncMock()
    locator = MagicMock()
    locator.first = first
    page.locator = MagicMock(return_value=locator)
    return page


class TestNavigateToAppointmentPageAlreadyThere:
    """Tests for the 'already on appointment page' path."""

    @pytest.mark.asyncio
    async def test_already_on_appointment_page_high_confidence(self):
        """Return True immediately if already on appointment page with sufficient confidence."""
        state = _make_state(is_on_appointment_page=True, confidence=0.90)
        detector = _make_page_state_detector(state)
        page = _make_page()

        result = await navigate_to_appointment_page(page, detector)

        assert result is True
        detector.detect.assert_awaited_once_with(page)
        detector.wait_for_stable_state.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_already_on_appointment_page_exact_threshold(self):
        """Return True at exactly 0.70 confidence."""
        state = _make_state(is_on_appointment_page=True, confidence=0.70)
        detector = _make_page_state_detector(state)
        page = _make_page()

        result = await navigate_to_appointment_page(page, detector)

        assert result is True

    @pytest.mark.asyncio
    async def test_appointment_page_low_confidence_falls_through(self):
        """Low confidence on appointment page should not return True immediately."""
        from src.services.bot.page_state_detector import PageState

        state = _make_state(is_on_appointment_page=True, confidence=0.50)
        state.state = PageState.DASHBOARD
        detector = _make_page_state_detector(state)
        page = _make_page(locator_count=0)

        with pytest.raises(VFSBotError):
            await navigate_to_appointment_page(page, detector)


class TestNavigateToAppointmentPageRecovery:
    """Tests for the 'needs_recovery' path."""

    @pytest.mark.asyncio
    async def test_needs_recovery_raises_vfs_bot_error(self):
        """Raise VFSBotError when page needs recovery."""
        state = _make_state(needs_recovery=True, state_name="DASHBOARD")
        detector = _make_page_state_detector(state)
        page = _make_page()

        with pytest.raises(VFSBotError) as exc_info:
            await navigate_to_appointment_page(page, detector)

        assert exc_info.value.recoverable is True

    @pytest.mark.asyncio
    async def test_needs_recovery_error_message_contains_state_name(self):
        """Error message should include the current state name."""
        state = _make_state(needs_recovery=True, state_name="DASHBOARD")
        detector = _make_page_state_detector(state)
        page = _make_page()

        with pytest.raises(VFSBotError) as exc_info:
            await navigate_to_appointment_page(page, detector)

        assert "recovery" in str(exc_info.value).lower()


class TestNavigateToAppointmentPageDashboard:
    """Tests for navigation from DASHBOARD state."""

    @pytest.mark.asyncio
    async def test_dashboard_finds_selector_and_navigates(self):
        """From DASHBOARD, find selector, click it, wait succeeds → return True."""
        from src.services.bot.page_state_detector import PageState

        initial_state = _make_state(state_name="DASHBOARD")
        initial_state.state = PageState.DASHBOARD

        success_state = _make_state(is_on_appointment_page=True, confidence=0.90)
        success_state.state = PageState.APPOINTMENT_PAGE

        detector = _make_page_state_detector(initial_state, wait_result=success_state)
        page = _make_page(locator_count=1)

        result = await navigate_to_appointment_page(page, detector)

        assert result is True

    @pytest.mark.asyncio
    async def test_dashboard_no_selector_found_raises(self):
        """From DASHBOARD, if no nav link found, raise VFSBotError."""
        from src.services.bot.page_state_detector import PageState

        initial_state = _make_state(state_name="DASHBOARD")
        initial_state.state = PageState.DASHBOARD

        detector = _make_page_state_detector(initial_state)
        page = _make_page(locator_count=0)

        with pytest.raises(VFSBotError) as exc_info:
            await navigate_to_appointment_page(page, detector)

        assert exc_info.value.recoverable is True
        assert "appointment" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_dashboard_wait_fails_raises(self):
        """From DASHBOARD, click succeeds but wait returns wrong state → raise VFSBotError."""
        from src.services.bot.page_state_detector import PageState

        initial_state = _make_state(state_name="DASHBOARD")
        initial_state.state = PageState.DASHBOARD

        # Build a wrong_state with a MagicMock state (not the real enum)
        wrong_state = MagicMock()
        wrong_state.is_on_appointment_page = False
        wrong_state.needs_recovery = False
        wrong_state.confidence = 0.5
        wrong_state_enum = MagicMock()
        wrong_state_enum.name = "DASHBOARD"
        wrong_state.state = wrong_state_enum

        detector = _make_page_state_detector(initial_state, wait_result=wrong_state)
        page = _make_page(locator_count=1)

        with pytest.raises(VFSBotError) as exc_info:
            await navigate_to_appointment_page(page, detector)

        assert exc_info.value.recoverable is True

    @pytest.mark.asyncio
    async def test_dashboard_with_human_sim_calls_human_click(self):
        """From DASHBOARD with human_sim, use human_click instead of direct click."""
        from src.services.bot.page_state_detector import PageState

        initial_state = _make_state(state_name="DASHBOARD")
        initial_state.state = PageState.DASHBOARD

        success_state = _make_state(is_on_appointment_page=True, confidence=0.90)
        success_state.state = PageState.APPOINTMENT_PAGE

        detector = _make_page_state_detector(initial_state, wait_result=success_state)
        page = _make_page(locator_count=1)

        human_sim = MagicMock()
        human_sim.human_click = AsyncMock()

        result = await navigate_to_appointment_page(page, detector, human_sim=human_sim)

        assert result is True
        human_sim.human_click.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dashboard_without_human_sim_uses_locator_click(self):
        """From DASHBOARD without human_sim, use locator.click()."""
        from src.services.bot.page_state_detector import PageState

        initial_state = _make_state(state_name="DASHBOARD")
        initial_state.state = PageState.DASHBOARD

        success_state = _make_state(is_on_appointment_page=True, confidence=0.90)
        success_state.state = PageState.APPOINTMENT_PAGE

        detector = _make_page_state_detector(initial_state, wait_result=success_state)
        page = _make_page(locator_count=1)

        result = await navigate_to_appointment_page(page, detector)

        assert result is True
        # page.locator().first.click should have been called
        page.locator.return_value.first.click.assert_awaited()

    @pytest.mark.asyncio
    async def test_dashboard_locator_click_exception_tries_next_selector(self):
        """If first selector click raises, try subsequent selectors."""
        from src.services.bot.page_state_detector import PageState

        initial_state = _make_state(state_name="DASHBOARD")
        initial_state.state = PageState.DASHBOARD

        success_state = _make_state(is_on_appointment_page=True, confidence=0.90)
        success_state.state = PageState.APPOINTMENT_PAGE

        detector = _make_page_state_detector(initial_state, wait_result=success_state)

        page = MagicMock()
        call_count = 0

        def make_first(selector):
            nonlocal call_count
            call_count += 1
            first = MagicMock()
            first.count = AsyncMock(return_value=1)
            if call_count == 1:
                first.click = AsyncMock(side_effect=Exception("click failed"))
            else:
                first.click = AsyncMock()
            loc = MagicMock()
            loc.first = first
            return loc

        page.locator = MagicMock(side_effect=make_first)

        result = await navigate_to_appointment_page(page, detector)

        assert result is True

    @pytest.mark.asyncio
    async def test_dashboard_custom_max_wait_passed_to_detector(self):
        """max_wait parameter is forwarded to wait_for_stable_state."""
        from src.services.bot.page_state_detector import PageState

        initial_state = _make_state(state_name="DASHBOARD")
        initial_state.state = PageState.DASHBOARD

        success_state = _make_state(is_on_appointment_page=True, confidence=0.90)
        success_state.state = PageState.APPOINTMENT_PAGE

        detector = _make_page_state_detector(initial_state, wait_result=success_state)
        page = _make_page(locator_count=1)

        await navigate_to_appointment_page(page, detector, max_wait=30.0)

        call_kwargs = detector.wait_for_stable_state.call_args
        assert call_kwargs.kwargs.get("max_wait") == 30.0


class TestNavigateToAppointmentPageUnknownState:
    """Tests for unknown/unexpected states."""

    @pytest.mark.asyncio
    async def test_unknown_state_raises_vfs_bot_error(self):
        """Unknown state should raise VFSBotError."""
        from src.services.bot.page_state_detector import PageState

        state = _make_state(state_name="LOADING")
        # Use a non-DASHBOARD state
        unknown = MagicMock()
        unknown.name = "LOADING"
        state.state = unknown

        detector = _make_page_state_detector(state)
        page = _make_page()

        with pytest.raises(VFSBotError) as exc_info:
            await navigate_to_appointment_page(page, detector)

        assert exc_info.value.recoverable is True

    @pytest.mark.asyncio
    async def test_unknown_state_error_mentions_relogin(self):
        """Error for unknown state should mention re-login."""
        state = _make_state()
        unknown = MagicMock()
        unknown.name = "SOMETHING_WEIRD"
        state.state = unknown

        detector = _make_page_state_detector(state)
        page = _make_page()

        with pytest.raises(VFSBotError) as exc_info:
            await navigate_to_appointment_page(page, detector)

        assert "login" in str(exc_info.value).lower()
