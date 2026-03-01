"""Tests for CloudflareHandler."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.utils.anti_detection.cloudflare_handler import CloudflareHandler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def handler():
    """Default CloudflareHandler with standard config."""
    return CloudflareHandler()


@pytest.fixture
def handler_fast():
    """CloudflareHandler with max_wait_time=1 for timeout tests."""
    return CloudflareHandler(config={"max_wait_time": 1})


@pytest.fixture
def handler_manual_captcha():
    """CloudflareHandler with manual_captcha=True and max_wait_time=1."""
    return CloudflareHandler(config={"manual_captcha": True, "max_wait_time": 1})


@pytest.fixture
def mock_page():
    """Mock Playwright page."""
    page = MagicMock()
    page.title = AsyncMock(return_value="")
    page.content = AsyncMock(return_value="")
    locator_mock = MagicMock()
    locator_mock.count = AsyncMock(return_value=0)
    page.locator = MagicMock(return_value=locator_mock)
    page.wait_for_function = AsyncMock(return_value=None)
    page.wait_for_selector = AsyncMock(return_value=None)
    return page


# ---------------------------------------------------------------------------
# __init__ tests
# ---------------------------------------------------------------------------


class TestCloudflareHandlerInit:
    """Tests for CloudflareHandler.__init__."""

    def test_default_config_values(self):
        """Default config: enabled=True, max_wait_time=30, max_retries=3, manual_captcha=False."""
        h = CloudflareHandler()
        assert h.enabled is True
        assert h.max_wait_time == 30
        assert h.max_retries == 3
        assert h.manual_captcha is False

    def test_custom_config_values(self):
        """Custom config values are applied."""
        h = CloudflareHandler(
            config={"enabled": False, "max_wait_time": 60, "max_retries": 5, "manual_captcha": True}
        )
        assert h.enabled is False
        assert h.max_wait_time == 60
        assert h.max_retries == 5
        assert h.manual_captcha is True

    def test_none_config_uses_defaults(self):
        """Passing None as config falls back to defaults."""
        h = CloudflareHandler(config=None)
        assert h.enabled is True
        assert h.max_wait_time == 30
        assert h.max_retries == 3
        assert h.manual_captcha is False

    def test_partial_config_uses_defaults_for_missing_keys(self):
        """Partial config uses defaults for missing keys."""
        h = CloudflareHandler(config={"max_wait_time": 10})
        assert h.enabled is True
        assert h.max_wait_time == 10
        assert h.max_retries == 3
        assert h.manual_captcha is False


# ---------------------------------------------------------------------------
# detect_cloudflare_challenge tests
# ---------------------------------------------------------------------------


class TestDetectCloudflareChallenge:
    """Tests for CloudflareHandler.detect_cloudflare_challenge."""

    @pytest.mark.asyncio
    async def test_no_challenge_returns_none(self, handler, mock_page):
        """Clean page → returns None."""
        result = await handler.detect_cloudflare_challenge(mock_page)
        assert result is None

    @pytest.mark.asyncio
    async def test_waiting_room_detected_via_title(self, handler, mock_page):
        """Title containing 'Waiting Room' is detected."""
        mock_page.title.return_value = "Waiting Room - Please Wait"
        result = await handler.detect_cloudflare_challenge(mock_page)
        assert result == "waiting_room"

    @pytest.mark.asyncio
    async def test_waiting_room_detected_via_title_case_insensitive(self, handler, mock_page):
        """Title detection is case-insensitive."""
        mock_page.title.return_value = "WAITING ROOM"
        result = await handler.detect_cloudflare_challenge(mock_page)
        assert result == "waiting_room"

    @pytest.mark.asyncio
    async def test_waiting_room_detected_via_content(self, handler, mock_page):
        """Page content containing 'waiting room' is detected."""
        mock_page.content.return_value = "<html><body>Waiting Room</body></html>"
        result = await handler.detect_cloudflare_challenge(mock_page)
        assert result == "waiting_room"

    @pytest.mark.asyncio
    async def test_browser_check_detected_via_title(self, handler, mock_page):
        """Title 'Just a moment...' is detected as browser_check."""
        mock_page.title.return_value = "Just a moment..."
        result = await handler.detect_cloudflare_challenge(mock_page)
        assert result == "browser_check"

    @pytest.mark.asyncio
    async def test_browser_check_detected_case_insensitive(self, handler, mock_page):
        """Browser check detection is case-insensitive."""
        mock_page.title.return_value = "JUST A MOMENT"
        result = await handler.detect_cloudflare_challenge(mock_page)
        assert result == "browser_check"

    @pytest.mark.asyncio
    async def test_turnstile_detected_via_locator_count(self, handler, mock_page):
        """Turnstile iframe present → returns 'turnstile'."""
        mock_page.locator.return_value.count = AsyncMock(return_value=1)
        result = await handler.detect_cloudflare_challenge(mock_page)
        assert result == "turnstile"

    @pytest.mark.asyncio
    async def test_blocked_403_with_cloudflare_in_content(self, handler, mock_page):
        """403 forbidden + cloudflare in content → 'blocked'."""
        mock_page.content.return_value = "403 Forbidden - Cloudflare"
        result = await handler.detect_cloudflare_challenge(mock_page)
        assert result == "blocked"

    @pytest.mark.asyncio
    async def test_blocked_503_with_cloudflare_in_content(self, handler, mock_page):
        """503 service unavailable + cloudflare in content → 'blocked'."""
        mock_page.content.return_value = "503 Service Unavailable - cloudflare"
        result = await handler.detect_cloudflare_challenge(mock_page)
        assert result == "blocked"

    @pytest.mark.asyncio
    async def test_non_cloudflare_403_returns_none(self, handler, mock_page):
        """403 without 'cloudflare' in content → returns None."""
        mock_page.content.return_value = "403 Forbidden - Access denied"
        result = await handler.detect_cloudflare_challenge(mock_page)
        assert result is None

    @pytest.mark.asyncio
    async def test_priority_waiting_room_over_turnstile(self, handler, mock_page):
        """waiting_room title takes priority over turnstile iframe."""
        mock_page.title.return_value = "Waiting Room"
        mock_page.locator.return_value.count = AsyncMock(return_value=1)
        result = await handler.detect_cloudflare_challenge(mock_page)
        assert result == "waiting_room"

    @pytest.mark.asyncio
    async def test_priority_browser_check_over_turnstile(self, handler, mock_page):
        """browser_check title takes priority over turnstile iframe."""
        mock_page.title.return_value = "Just a moment..."
        mock_page.locator.return_value.count = AsyncMock(return_value=1)
        result = await handler.detect_cloudflare_challenge(mock_page)
        assert result == "browser_check"

    @pytest.mark.asyncio
    async def test_exception_during_detection_returns_none(self, handler, mock_page):
        """General exception during detection → returns None."""
        mock_page.title.side_effect = Exception("page crashed")
        result = await handler.detect_cloudflare_challenge(mock_page)
        assert result is None

    @pytest.mark.asyncio
    async def test_timeout_error_during_detection_returns_none(self, handler, mock_page):
        """TimeoutError during detection → returns None."""
        mock_page.title.side_effect = asyncio.TimeoutError()
        result = await handler.detect_cloudflare_challenge(mock_page)
        assert result is None


# ---------------------------------------------------------------------------
# handle_waiting_room tests
# ---------------------------------------------------------------------------


class TestHandleWaitingRoom:
    """Tests for CloudflareHandler.handle_waiting_room."""

    @pytest.mark.asyncio
    async def test_event_driven_success(self, handler, mock_page):
        """wait_for_function resolves → returns True."""
        mock_page.wait_for_function = AsyncMock(return_value=None)
        result = await handler.handle_waiting_room(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_timeout_with_fallback_cleared(self, handler_fast, mock_page):
        """Timeout but title no longer contains 'waiting room' → returns True."""
        mock_page.wait_for_function = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_page.title.return_value = "VFS Appointment"
        result = await handler_fast.handle_waiting_room(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_timeout_with_fallback_still_in_waiting_room(self, handler_fast, mock_page):
        """Timeout and title still has 'waiting room' → returns False."""
        mock_page.wait_for_function = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_page.title.return_value = "Waiting Room"
        result = await handler_fast.handle_waiting_room(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_false(self, handler, mock_page):
        """Unexpected exception → returns False."""
        mock_page.wait_for_function = AsyncMock(side_effect=RuntimeError("unexpected"))
        result = await handler.handle_waiting_room(mock_page)
        assert result is False


# ---------------------------------------------------------------------------
# handle_turnstile tests
# ---------------------------------------------------------------------------


class TestHandleTurnstile:
    """Tests for CloudflareHandler.handle_turnstile."""

    @pytest.mark.asyncio
    async def test_auto_solve_event_driven_success(self, handler, mock_page):
        """wait_for_selector state=detached resolves → True."""
        mock_page.wait_for_selector = AsyncMock(return_value=None)
        result = await handler.handle_turnstile(mock_page)
        assert result is True
        mock_page.wait_for_selector.assert_called_once_with(
            handler.TURNSTILE_IFRAME_SELECTOR,
            state="detached",
        )

    @pytest.mark.asyncio
    async def test_auto_solve_timeout_with_fallback_cleared(self, handler_fast, mock_page):
        """Timeout but iframe count=0 after fallback → True."""
        mock_page.wait_for_selector = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_page.locator.return_value.count = AsyncMock(return_value=0)
        result = await handler_fast.handle_turnstile(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_auto_solve_timeout_with_iframe_still_present(self, handler_fast, mock_page):
        """Timeout and iframe still present → False."""
        mock_page.wait_for_selector = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_page.locator.return_value.count = AsyncMock(return_value=1)
        result = await handler_fast.handle_turnstile(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_manual_captcha_success(self, handler_manual_captcha, mock_page):
        """Manual captcha mode: sleep + iframe gone → True."""
        mock_page.locator.return_value.count = AsyncMock(return_value=0)
        result = await handler_manual_captcha.handle_turnstile(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_manual_captcha_timeout_iframe_still_present(self, handler_manual_captcha, mock_page):
        """Manual captcha mode: iframe still present → False."""
        mock_page.locator.return_value.count = AsyncMock(return_value=1)
        result = await handler_manual_captcha.handle_turnstile(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_false(self, handler, mock_page):
        """Unexpected exception → False."""
        mock_page.wait_for_selector = AsyncMock(side_effect=RuntimeError("unexpected"))
        result = await handler.handle_turnstile(mock_page)
        assert result is False


# ---------------------------------------------------------------------------
# handle_browser_check tests
# ---------------------------------------------------------------------------


class TestHandleBrowserCheck:
    """Tests for CloudflareHandler.handle_browser_check."""

    @pytest.mark.asyncio
    async def test_event_driven_success(self, handler, mock_page):
        """wait_for_function resolves → True."""
        mock_page.wait_for_function = AsyncMock(return_value=None)
        result = await handler.handle_browser_check(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_timeout_with_fallback_cleared(self, handler_fast, mock_page):
        """Timeout but title no longer 'just a moment' → True."""
        mock_page.wait_for_function = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_page.title.return_value = "VFS Appointment"
        result = await handler_fast.handle_browser_check(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_timeout_not_cleared(self, handler_fast, mock_page):
        """Timeout and title still 'just a moment' → False."""
        mock_page.wait_for_function = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_page.title.return_value = "Just a moment..."
        result = await handler_fast.handle_browser_check(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_false(self, handler, mock_page):
        """Unexpected exception → False."""
        mock_page.wait_for_function = AsyncMock(side_effect=RuntimeError("unexpected"))
        result = await handler.handle_browser_check(mock_page)
        assert result is False


# ---------------------------------------------------------------------------
# handle_challenge dispatcher tests
# ---------------------------------------------------------------------------


class TestHandleChallenge:
    """Tests for CloudflareHandler.handle_challenge."""

    @pytest.mark.asyncio
    async def test_handler_disabled_returns_true_without_detection(self, mock_page):
        """Disabled handler skips detection and returns True."""
        h = CloudflareHandler(config={"enabled": False})
        # Ensure detect is NOT called by making title raise if it were called
        mock_page.title = AsyncMock(side_effect=AssertionError("detect should not be called"))
        result = await h.handle_challenge(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_no_challenge_returns_true(self, handler, mock_page):
        """No challenge detected → True."""
        result = await handler.handle_challenge(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_dispatches_to_handle_waiting_room(self, handler, mock_page, monkeypatch):
        """waiting_room challenge dispatches to handle_waiting_room."""
        monkeypatch.setattr(
            handler, "detect_cloudflare_challenge", AsyncMock(return_value="waiting_room")
        )
        monkeypatch.setattr(handler, "handle_waiting_room", AsyncMock(return_value=True))
        result = await handler.handle_challenge(mock_page)
        assert result is True
        handler.handle_waiting_room.assert_called_once_with(mock_page)

    @pytest.mark.asyncio
    async def test_dispatches_to_handle_browser_check(self, handler, mock_page, monkeypatch):
        """browser_check challenge dispatches to handle_browser_check."""
        monkeypatch.setattr(
            handler, "detect_cloudflare_challenge", AsyncMock(return_value="browser_check")
        )
        monkeypatch.setattr(handler, "handle_browser_check", AsyncMock(return_value=True))
        result = await handler.handle_challenge(mock_page)
        assert result is True
        handler.handle_browser_check.assert_called_once_with(mock_page)

    @pytest.mark.asyncio
    async def test_dispatches_to_handle_turnstile(self, handler, mock_page, monkeypatch):
        """turnstile challenge dispatches to handle_turnstile."""
        monkeypatch.setattr(
            handler, "detect_cloudflare_challenge", AsyncMock(return_value="turnstile")
        )
        monkeypatch.setattr(handler, "handle_turnstile", AsyncMock(return_value=True))
        result = await handler.handle_challenge(mock_page)
        assert result is True
        handler.handle_turnstile.assert_called_once_with(mock_page)

    @pytest.mark.asyncio
    async def test_blocked_returns_false(self, handler, mock_page, monkeypatch):
        """blocked challenge → False."""
        monkeypatch.setattr(
            handler, "detect_cloudflare_challenge", AsyncMock(return_value="blocked")
        )
        result = await handler.handle_challenge(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_error_in_dispatcher_returns_false(self, handler, mock_page, monkeypatch):
        """Exception during dispatcher → False."""
        monkeypatch.setattr(
            handler,
            "detect_cloudflare_challenge",
            AsyncMock(side_effect=RuntimeError("crash")),
        )
        result = await handler.handle_challenge(mock_page)
        assert result is False


# ---------------------------------------------------------------------------
# Constants & edge case tests
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests for CloudflareHandler constants."""

    def test_challenge_types_contains_expected_keys(self):
        """CHALLENGE_TYPES dict has all expected keys."""
        expected = {"waiting_room", "turnstile", "browser_check", "blocked"}
        assert expected == set(CloudflareHandler.CHALLENGE_TYPES.keys())

    def test_turnstile_iframe_selector_contains_cloudflare_domain(self):
        """TURNSTILE_IFRAME_SELECTOR contains 'challenges.cloudflare.com'."""
        assert "challenges.cloudflare.com" in CloudflareHandler.TURNSTILE_IFRAME_SELECTOR

    def test_detection_selector_is_broader_than_iframe_selector(self):
        """TURNSTILE_DETECTION_SELECTOR is broader (longer) than TURNSTILE_IFRAME_SELECTOR."""
        assert len(CloudflareHandler.TURNSTILE_DETECTION_SELECTOR) > len(
            CloudflareHandler.TURNSTILE_IFRAME_SELECTOR
        )
