"""Tests for PageStateDetector module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.bot.page_state_detector import (
    _ACTIONABLE_STATES,
    _PRIORITY_STATES,
    _RECOVERY_STATES,
    PageState,
    PageStateDetector,
    PageStateResult,
)


@pytest.fixture
def mock_page():
    """Create a mock Playwright page object."""
    page = AsyncMock()
    page.url = "https://visa.vfsglobal.com/tur/en/deu/login"
    page.title = AsyncMock(return_value="VFS Global - Login")
    page.content = AsyncMock(return_value="<html><body>Test Page</body></html>")
    page.locator = MagicMock()
    return page


@pytest.fixture
def mock_cloudflare_handler():
    """Create a mock CloudflareHandler."""
    handler = AsyncMock()
    handler.detect_cloudflare_challenge = AsyncMock(return_value=None)
    return handler


@pytest.fixture
def detector_config():
    """Minimal configuration for detector."""
    return {
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tur",
            "mission": "deu",
        }
    }


@pytest.fixture
def detector(detector_config, mock_cloudflare_handler):
    """Create a PageStateDetector instance."""
    return PageStateDetector(detector_config, mock_cloudflare_handler)


# ──────────────────────────────────────────────────────────────
# Test PageStateResult properties
# ──────────────────────────────────────────────────────────────


def test_page_state_result_actionable():
    """Test is_actionable property."""
    result = PageStateResult(
        state=PageState.LOGIN_PAGE,
        confidence=0.95,
        url="https://test.com",
    )
    assert result.is_actionable is True

    result_error = PageStateResult(
        state=PageState.SESSION_EXPIRED,
        confidence=0.90,
        url="https://test.com",
    )
    assert result_error.is_actionable is False


def test_page_state_result_needs_recovery():
    """Test needs_recovery property."""
    result = PageStateResult(
        state=PageState.SESSION_EXPIRED,
        confidence=0.90,
        url="https://test.com",
    )
    assert result.needs_recovery is True

    result_normal = PageStateResult(
        state=PageState.LOGIN_PAGE,
        confidence=0.95,
        url="https://test.com",
    )
    assert result_normal.needs_recovery is False


def test_page_state_result_is_on_appointment_page():
    """Test is_on_appointment_page property."""
    result = PageStateResult(
        state=PageState.APPOINTMENT_PAGE,
        confidence=0.80,
        url="https://test.com",
    )
    assert result.is_on_appointment_page is True

    result_other = PageStateResult(
        state=PageState.LOGIN_PAGE,
        confidence=0.95,
        url="https://test.com",
    )
    assert result_other.is_on_appointment_page is False


def test_page_state_result_is_waiting_for_otp():
    """Test is_waiting_for_otp property."""
    result_login_otp = PageStateResult(
        state=PageState.OTP_LOGIN,
        confidence=0.85,
        url="https://test.com",
    )
    assert result_login_otp.is_waiting_for_otp is True

    result_3d_secure = PageStateResult(
        state=PageState.OTP_3D_SECURE,
        confidence=0.85,
        url="https://test.com",
    )
    assert result_3d_secure.is_waiting_for_otp is True

    result_other = PageStateResult(
        state=PageState.LOGIN_PAGE,
        confidence=0.95,
        url="https://test.com",
    )
    assert result_other.is_waiting_for_otp is False


def test_page_state_result_is_loading():
    """Test is_loading property."""
    result = PageStateResult(
        state=PageState.APPOINTMENT_LOADING,
        confidence=0.80,
        url="https://test.com",
    )
    assert result.is_loading is True

    result_other = PageStateResult(
        state=PageState.APPOINTMENT_PAGE,
        confidence=0.80,
        url="https://test.com",
    )
    assert result_other.is_loading is False


# ──────────────────────────────────────────────────────────────
# Test state groups
# ──────────────────────────────────────────────────────────────


def test_actionable_states_group():
    """Test ACTIONABLE_STATES contains expected states."""
    assert PageState.LOGIN_PAGE in _ACTIONABLE_STATES
    assert PageState.DASHBOARD in _ACTIONABLE_STATES
    assert PageState.APPOINTMENT_PAGE in _ACTIONABLE_STATES
    assert PageState.OTP_LOGIN in _ACTIONABLE_STATES
    assert PageState.SESSION_EXPIRED not in _ACTIONABLE_STATES
    assert PageState.UNKNOWN not in _ACTIONABLE_STATES


def test_recovery_states_group():
    """Test RECOVERY_STATES contains expected states."""
    assert PageState.SESSION_EXPIRED in _RECOVERY_STATES
    assert PageState.CLOUDFLARE_CHALLENGE in _RECOVERY_STATES
    assert PageState.MAINTENANCE in _RECOVERY_STATES
    assert PageState.LOGIN_PAGE not in _RECOVERY_STATES


def test_priority_states_group():
    """Test PRIORITY_STATES contains expected states."""
    assert PageState.SESSION_EXPIRED in _PRIORITY_STATES
    assert PageState.CLOUDFLARE_CHALLENGE in _PRIORITY_STATES
    assert PageState.OTP_LOGIN in _PRIORITY_STATES
    assert PageState.LOGIN_PAGE not in _PRIORITY_STATES


# ──────────────────────────────────────────────────────────────
# Test detector initialization
# ──────────────────────────────────────────────────────────────


def test_detector_initialization(detector_config):
    """Test PageStateDetector initialization."""
    detector = PageStateDetector(detector_config)
    assert detector.config == detector_config
    assert detector.cloudflare_handler is None
    assert detector.last_state is None


def test_detector_initialization_with_cloudflare(detector_config, mock_cloudflare_handler):
    """Test PageStateDetector initialization with CloudflareHandler."""
    detector = PageStateDetector(detector_config, mock_cloudflare_handler)
    assert detector.cloudflare_handler == mock_cloudflare_handler


# ──────────────────────────────────────────────────────────────
# Test Cloudflare detection (fast path)
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detect_cloudflare_challenge(detector, mock_page, mock_cloudflare_handler):
    """Test Cloudflare challenge detection as fast path."""
    mock_cloudflare_handler.detect_cloudflare_challenge = AsyncMock(return_value="turnstile")

    result = await detector.detect(mock_page)

    assert result.state == PageState.CLOUDFLARE_CHALLENGE
    assert result.confidence == 0.95
    assert result.details["challenge_type"] == "turnstile"
    mock_cloudflare_handler.detect_cloudflare_challenge.assert_called_once_with(mock_page)


# ──────────────────────────────────────────────────────────────
# Test element checking — visibility-aware
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_element_requires_visible_true_and_visible(detector, mock_page):
    """Test element check when requires_visible=True and element is visible."""
    mock_locator = MagicMock()
    mock_first = AsyncMock()
    mock_first.is_visible = AsyncMock(return_value=True)
    mock_locator.first = mock_first
    mock_page.locator.return_value = mock_locator

    result = await detector._check_element(
        mock_page,
        "text=/session.*expired/i",
        PageState.SESSION_EXPIRED,
        0.95,
        requires_visible=True,
    )

    assert result is not None
    assert result[0] == PageState.SESSION_EXPIRED
    assert result[1] == 0.95
    mock_first.is_visible.assert_called_once()


@pytest.mark.asyncio
async def test_check_element_requires_visible_true_but_hidden(detector, mock_page):
    """Test element check when requires_visible=True but element is hidden."""
    mock_locator = MagicMock()
    mock_first = AsyncMock()
    mock_first.is_visible = AsyncMock(return_value=False)
    mock_locator.first = mock_first
    mock_page.locator.return_value = mock_locator

    result = await detector._check_element(
        mock_page, ".session-expired-modal", PageState.SESSION_EXPIRED, 0.90, requires_visible=True
    )

    assert result is None
    mock_first.is_visible.assert_called_once()


@pytest.mark.asyncio
async def test_check_element_requires_visible_false_and_exists(detector, mock_page):
    """Test element check when requires_visible=False and element exists."""
    mock_locator = AsyncMock()
    mock_locator.count = AsyncMock(return_value=1)
    mock_page.locator.return_value = mock_locator

    result = await detector._check_element(
        mock_page, 'input[name="email"]', PageState.LOGIN_PAGE, 0.40, requires_visible=False
    )

    assert result is not None
    assert result[0] == PageState.LOGIN_PAGE
    assert result[1] == 0.40
    mock_locator.count.assert_called_once()


@pytest.mark.asyncio
async def test_check_element_requires_visible_false_and_not_exists(detector, mock_page):
    """Test element check when requires_visible=False and element doesn't exist."""
    mock_locator = AsyncMock()
    mock_locator.count = AsyncMock(return_value=0)
    mock_page.locator.return_value = mock_locator

    result = await detector._check_element(
        mock_page, 'input[name="email"]', PageState.LOGIN_PAGE, 0.40, requires_visible=False
    )

    assert result is None
    mock_locator.count.assert_called_once()


@pytest.mark.asyncio
async def test_check_element_exception_handling(detector, mock_page):
    """Test element check handles exceptions gracefully."""
    mock_page.locator.side_effect = Exception("Page navigated away")

    result = await detector._check_element(
        mock_page, 'input[name="email"]', PageState.LOGIN_PAGE, 0.40, requires_visible=False
    )

    assert result is None


# ──────────────────────────────────────────────────────────────
# Test detection with multiple elements
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detect_login_page(detector, mock_page):
    """Test detection of login page with email and password fields."""

    def mock_locator_func(selector):
        mock_loc = AsyncMock()
        if "email" in selector:
            mock_loc.count = AsyncMock(return_value=1)
        elif "password" in selector:
            mock_loc.count = AsyncMock(return_value=1)
        else:
            mock_loc.count = AsyncMock(return_value=0)
            mock_first = AsyncMock()
            mock_first.is_visible = AsyncMock(return_value=False)
            mock_loc.first = mock_first
        return mock_loc

    mock_page.locator = MagicMock(side_effect=mock_locator_func)

    result = await detector.detect(mock_page)

    assert result.state == PageState.LOGIN_PAGE
    # Should have both email (0.40) + password (0.40) = 0.80
    assert result.confidence >= 0.70


@pytest.mark.asyncio
async def test_detect_appointment_page(detector, mock_page):
    """Test detection of appointment page with centre selector."""

    def mock_locator_func(selector):
        mock_loc = AsyncMock()
        if "centres" in selector or "centre" in selector or "center" in selector:
            mock_loc.count = AsyncMock(return_value=1)
        else:
            mock_loc.count = AsyncMock(return_value=0)
            mock_first = AsyncMock()
            mock_first.is_visible = AsyncMock(return_value=False)
            mock_loc.first = mock_first
        return mock_loc

    mock_page.locator = MagicMock(side_effect=mock_locator_func)

    result = await detector.detect(mock_page)

    assert result.state == PageState.APPOINTMENT_PAGE
    assert result.confidence >= 0.70


@pytest.mark.asyncio
async def test_detect_session_expired(detector, mock_page):
    """Test detection of session expired modal (visible)."""

    def mock_locator_func(selector):
        mock_loc = MagicMock()
        if "session" in selector.lower() and "expired" in selector.lower():
            mock_first = AsyncMock()
            mock_first.is_visible = AsyncMock(return_value=True)
            mock_loc.first = mock_first
        else:
            mock_loc.count = AsyncMock(return_value=0)
            mock_first = AsyncMock()
            mock_first.is_visible = AsyncMock(return_value=False)
            mock_loc.first = mock_first
        return mock_loc

    mock_page.locator = MagicMock(side_effect=mock_locator_func)

    result = await detector.detect(mock_page)

    assert result.state == PageState.SESSION_EXPIRED
    assert result.confidence >= 0.90


# ──────────────────────────────────────────────────────────────
# Test ambiguity resolution
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_otp_login_vs_3d_secure_login_context(detector, mock_page):
    """Test OTP resolution in VFS login context."""
    mock_page.url = "https://visa.vfsglobal.com/tur/en/deu/login"
    mock_locator = AsyncMock()
    mock_locator.count = AsyncMock(return_value=0)
    mock_page.locator.return_value = mock_locator

    scores = {PageState.OTP_LOGIN: 0.85}
    details = {}

    resolved = await detector._resolve_ambiguities(mock_page, scores, details)

    assert PageState.OTP_LOGIN in resolved
    assert details["otp_resolution"] == "login_otp"


@pytest.mark.asyncio
async def test_resolve_otp_login_vs_3d_secure_payment_context(detector, mock_page):
    """Test OTP resolution in payment/bank context."""
    mock_page.url = "https://payment.bank.com/3dsecure"
    mock_locator = AsyncMock()
    mock_locator.count = AsyncMock(return_value=1)
    mock_page.locator.return_value = mock_locator

    scores = {PageState.OTP_LOGIN: 0.85}
    details = {}

    resolved = await detector._resolve_ambiguities(mock_page, scores, details)

    assert PageState.OTP_3D_SECURE in resolved
    assert PageState.OTP_LOGIN not in resolved
    assert details["otp_resolution"] == "3d_secure"


@pytest.mark.asyncio
async def test_resolve_appointment_vs_loading(detector, mock_page):
    """Test APPOINTMENT_PAGE vs APPOINTMENT_LOADING resolution."""
    scores = {
        PageState.APPOINTMENT_PAGE: 0.80,
        PageState.APPOINTMENT_LOADING: 0.80,
    }
    details = {}

    resolved = await detector._resolve_ambiguities(mock_page, scores, details)

    assert PageState.APPOINTMENT_LOADING in resolved
    assert PageState.APPOINTMENT_PAGE not in resolved
    assert details["loading_resolution"] == "spinner visible, not ready"


@pytest.mark.asyncio
async def test_resolve_login_page_low_confidence_gate(detector, mock_page):
    """Test LOGIN_PAGE confidence gate for partial matches."""
    scores = {PageState.LOGIN_PAGE: 0.40}  # Only email field, not password
    details = {}

    await detector._resolve_ambiguities(mock_page, scores, details)

    assert details["login_note"] == "partial match — only one of email/password"


@pytest.mark.asyncio
async def test_resolve_priority_state_boost(detector, mock_page):
    """Test error states get priority boost."""
    scores = {
        PageState.SESSION_EXPIRED: 0.85,
        PageState.LOGIN_PAGE: 0.80,
    }
    details = {}

    resolved = await detector._resolve_ambiguities(mock_page, scores, details)

    # SESSION_EXPIRED should get +0.10 boost (0.85 + 0.10 = 0.95)
    assert resolved[PageState.SESSION_EXPIRED] >= 0.90
    assert resolved[PageState.SESSION_EXPIRED] > resolved[PageState.LOGIN_PAGE]


# ──────────────────────────────────────────────────────────────
# Test fallback detection
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fallback_detection_login_title(detector, mock_page):
    """Test fallback detection using page title for login."""
    mock_page.title = AsyncMock(return_value="VFS Global - Login")

    state = await detector._fallback_detection(mock_page)

    assert state == PageState.LOGIN_PAGE


@pytest.mark.asyncio
async def test_fallback_detection_appointment_title(detector, mock_page):
    """Test fallback detection using page title for appointment."""
    mock_page.title = AsyncMock(return_value="Book Appointment - VFS")

    state = await detector._fallback_detection(mock_page)

    assert state == PageState.APPOINTMENT_PAGE


@pytest.mark.asyncio
async def test_fallback_detection_turkish_login_title(detector, mock_page):
    """Test fallback detection using Turkish page title."""
    mock_page.title = AsyncMock(return_value="VFS Global - Giriş")

    state = await detector._fallback_detection(mock_page)

    assert state == PageState.LOGIN_PAGE


@pytest.mark.asyncio
async def test_fallback_detection_unknown(detector, mock_page):
    """Test fallback detection returns UNKNOWN for unrecognized title."""
    mock_page.title = AsyncMock(return_value="Some Random Page")

    state = await detector._fallback_detection(mock_page)

    assert state == PageState.UNKNOWN


@pytest.mark.asyncio
async def test_fallback_detection_exception_handling(detector, mock_page):
    """Test fallback detection handles exceptions gracefully."""
    mock_page.title = AsyncMock(side_effect=Exception("Page error"))

    state = await detector._fallback_detection(mock_page)

    assert state == PageState.UNKNOWN


# ──────────────────────────────────────────────────────────────
# Test wait_for_stable_state
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wait_for_stable_state_immediate_stable(detector, mock_page):
    """Test wait_for_stable_state with immediately stable state."""

    # Mock detect to return LOGIN_PAGE consistently
    async def mock_detect(page, timeout=3000):
        return PageStateResult(
            state=PageState.LOGIN_PAGE,
            confidence=0.85,
            url=mock_page.url,
        )

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.wait_for_stable_state(
            mock_page, max_wait=5.0, poll_interval=0.1, consecutive_required=2
        )

    assert result.state == PageState.LOGIN_PAGE
    assert result.confidence >= 0.60


@pytest.mark.asyncio
async def test_wait_for_stable_state_with_expected_states(detector, mock_page):
    """Test wait_for_stable_state with expected states filter."""

    # Mock detect to return DASHBOARD consistently
    async def mock_detect(page, timeout=3000):
        return PageStateResult(
            state=PageState.DASHBOARD,
            confidence=0.80,
            url=mock_page.url,
        )

    expected = frozenset({PageState.DASHBOARD, PageState.APPOINTMENT_PAGE})

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.wait_for_stable_state(
            mock_page,
            max_wait=5.0,
            poll_interval=0.1,
            expected_states=expected,
            consecutive_required=2,
        )

    assert result.state == PageState.DASHBOARD


@pytest.mark.asyncio
async def test_wait_for_stable_state_early_exit_on_error(detector, mock_page):
    """Test wait_for_stable_state early exits on high-confidence error."""

    # Mock detect to return SESSION_EXPIRED
    async def mock_detect(page, timeout=3000):
        return PageStateResult(
            state=PageState.SESSION_EXPIRED,
            confidence=0.95,
            url=mock_page.url,
        )

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.wait_for_stable_state(
            mock_page,
            max_wait=10.0,
            poll_interval=0.1,
        )

    # Should exit immediately, not wait full 10 seconds
    assert result.state == PageState.SESSION_EXPIRED
    assert result.confidence >= 0.85


@pytest.mark.asyncio
async def test_wait_for_stable_state_timeout_returns_best(detector, mock_page):
    """Test wait_for_stable_state returns best result on timeout."""
    call_count = 0

    async def mock_detect(page, timeout=3000):
        nonlocal call_count
        call_count += 1
        # Return UNKNOWN initially, then LOGIN_PAGE once
        if call_count == 3:
            return PageStateResult(
                state=PageState.LOGIN_PAGE,
                confidence=0.50,  # Low confidence, won't meet criteria
                url=mock_page.url,
            )
        return PageStateResult(
            state=PageState.UNKNOWN,
            confidence=0.30,
            url=mock_page.url,
        )

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.wait_for_stable_state(
            mock_page,
            max_wait=1.0,  # Short timeout
            poll_interval=0.2,
            min_confidence=0.70,
            consecutive_required=2,
        )

    # Should return best result seen (LOGIN_PAGE with 0.50)
    assert result.state == PageState.LOGIN_PAGE
    assert result.confidence == 0.50


@pytest.mark.asyncio
async def test_wait_for_stable_state_requires_consecutive(detector, mock_page):
    """Test wait_for_stable_state requires consecutive detections."""
    states_sequence = [
        PageState.APPOINTMENT_LOADING,
        PageState.APPOINTMENT_PAGE,
        PageState.APPOINTMENT_LOADING,
        PageState.APPOINTMENT_PAGE,
        PageState.APPOINTMENT_PAGE,  # This one and next are consecutive
        PageState.APPOINTMENT_PAGE,
    ]
    call_count = 0

    async def mock_detect(page, timeout=3000):
        nonlocal call_count
        state = states_sequence[min(call_count, len(states_sequence) - 1)]
        call_count += 1
        return PageStateResult(
            state=state,
            confidence=0.80,
            url=mock_page.url,
        )

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.wait_for_stable_state(
            mock_page, max_wait=5.0, poll_interval=0.1, consecutive_required=2
        )

    assert result.state == PageState.APPOINTMENT_PAGE


# ──────────────────────────────────────────────────────────────
# Test convenience methods
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_is_on_appointment_page_true(detector, mock_page):
    """Test is_on_appointment_page returns True for appointment page."""

    async def mock_detect(page, timeout=3000):
        return PageStateResult(
            state=PageState.APPOINTMENT_PAGE,
            confidence=0.80,
            url=mock_page.url,
        )

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.is_on_appointment_page(mock_page)

    assert result is True


@pytest.mark.asyncio
async def test_is_on_appointment_page_false_low_confidence(detector, mock_page):
    """Test is_on_appointment_page returns False for low confidence."""

    async def mock_detect(page, timeout=3000):
        return PageStateResult(
            state=PageState.APPOINTMENT_PAGE,
            confidence=0.50,  # Below 0.70 threshold
            url=mock_page.url,
        )

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.is_on_appointment_page(mock_page)

    assert result is False


@pytest.mark.asyncio
async def test_needs_login_true_on_login_page(detector, mock_page):
    """Test needs_login returns True on LOGIN_PAGE."""

    async def mock_detect(page, timeout=3000):
        return PageStateResult(
            state=PageState.LOGIN_PAGE,
            confidence=0.85,
            url=mock_page.url,
        )

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.needs_login(mock_page)

    assert result is True


@pytest.mark.asyncio
async def test_needs_login_true_on_session_expired(detector, mock_page):
    """Test needs_login returns True on SESSION_EXPIRED."""

    async def mock_detect(page, timeout=3000):
        return PageStateResult(
            state=PageState.SESSION_EXPIRED,
            confidence=0.90,
            url=mock_page.url,
        )

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.needs_login(mock_page)

    assert result is True


@pytest.mark.asyncio
async def test_needs_login_false_on_dashboard(detector, mock_page):
    """Test needs_login returns False on DASHBOARD."""

    async def mock_detect(page, timeout=3000):
        return PageStateResult(
            state=PageState.DASHBOARD,
            confidence=0.80,
            url=mock_page.url,
        )

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.needs_login(mock_page)

    assert result is False


@pytest.mark.asyncio
async def test_is_blocked_true_on_cloudflare(detector, mock_page):
    """Test is_blocked returns True on CLOUDFLARE_CHALLENGE."""

    async def mock_detect(page, timeout=3000):
        return PageStateResult(
            state=PageState.CLOUDFLARE_CHALLENGE,
            confidence=0.95,
            url=mock_page.url,
        )

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.is_blocked(mock_page)

    assert result is True


@pytest.mark.asyncio
async def test_is_blocked_false_on_normal_page(detector, mock_page):
    """Test is_blocked returns False on normal pages."""

    async def mock_detect(page, timeout=3000):
        return PageStateResult(
            state=PageState.LOGIN_PAGE,
            confidence=0.85,
            url=mock_page.url,
        )

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.is_blocked(mock_page)

    assert result is False


@pytest.mark.asyncio
async def test_is_waiting_for_otp_true(detector, mock_page):
    """Test is_waiting_for_otp returns True for OTP states."""

    async def mock_detect(page, timeout=3000):
        return PageStateResult(
            state=PageState.OTP_LOGIN,
            confidence=0.85,
            url=mock_page.url,
        )

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.is_waiting_for_otp(mock_page)

    assert result is True


@pytest.mark.asyncio
async def test_get_otp_type_login(detector, mock_page):
    """Test get_otp_type returns OTP_LOGIN."""

    async def mock_detect(page, timeout=3000):
        return PageStateResult(
            state=PageState.OTP_LOGIN,
            confidence=0.85,
            url=mock_page.url,
        )

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.get_otp_type(mock_page)

    assert result == PageState.OTP_LOGIN


@pytest.mark.asyncio
async def test_get_otp_type_3d_secure(detector, mock_page):
    """Test get_otp_type returns OTP_3D_SECURE."""

    async def mock_detect(page, timeout=3000):
        return PageStateResult(
            state=PageState.OTP_3D_SECURE,
            confidence=0.85,
            url=mock_page.url,
        )

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.get_otp_type(mock_page)

    assert result == PageState.OTP_3D_SECURE


@pytest.mark.asyncio
async def test_get_otp_type_none(detector, mock_page):
    """Test get_otp_type returns None for non-OTP states."""

    async def mock_detect(page, timeout=3000):
        return PageStateResult(
            state=PageState.LOGIN_PAGE,
            confidence=0.85,
            url=mock_page.url,
        )

    with patch.object(detector, "detect", side_effect=mock_detect):
        result = await detector.get_otp_type(mock_page)

    assert result is None


# ──────────────────────────────────────────────────────────────
# Test last_state tracking
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_last_state_tracking(detector, mock_page):
    """Test that last_state is updated after detection."""

    def mock_locator_func(selector):
        mock_loc = AsyncMock()
        if "email" in selector:
            mock_loc.count = AsyncMock(return_value=1)
        else:
            mock_loc.count = AsyncMock(return_value=0)
            mock_first = AsyncMock()
            mock_first.is_visible = AsyncMock(return_value=False)
            mock_loc.first = mock_first
        return mock_loc

    mock_page.locator = MagicMock(side_effect=mock_locator_func)

    assert detector.last_state is None

    result = await detector.detect(mock_page)

    assert detector.last_state is not None
    assert detector.last_state.state == result.state
    assert detector.last_state.confidence == result.confidence


# ──────────────────────────────────────────────────────────────
# Test edge cases
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detect_returns_unknown_when_no_matches(detector, mock_page):
    """Test detect returns UNKNOWN when no elements match."""

    def mock_locator_func(selector):
        mock_loc = AsyncMock()
        mock_loc.count = AsyncMock(return_value=0)
        mock_first = AsyncMock()
        mock_first.is_visible = AsyncMock(return_value=False)
        mock_loc.first = mock_first
        return mock_loc

    mock_page.locator = MagicMock(side_effect=mock_locator_func)
    mock_page.title = AsyncMock(return_value="Some Unknown Page")

    result = await detector.detect(mock_page)

    assert result.state == PageState.UNKNOWN
    assert result.confidence <= 0.30


@pytest.mark.asyncio
async def test_detect_accumulates_confidence_scores(detector, mock_page):
    """Test that multiple matching elements accumulate confidence."""

    def mock_locator_func(selector):
        mock_loc = AsyncMock()
        # Match both email and password
        if "email" in selector or "password" in selector:
            mock_loc.count = AsyncMock(return_value=1)
        else:
            mock_loc.count = AsyncMock(return_value=0)
            mock_first = AsyncMock()
            mock_first.is_visible = AsyncMock(return_value=False)
            mock_loc.first = mock_first
        return mock_loc

    mock_page.locator = MagicMock(side_effect=mock_locator_func)

    result = await detector.detect(mock_page)

    assert result.state == PageState.LOGIN_PAGE
    # Should accumulate: email (0.40) + password (0.40) = 0.80
    assert result.confidence >= 0.70
    # Check matched rules in details
    assert len(result.details["matched_rules"]) >= 2


@pytest.mark.asyncio
async def test_confidence_capped_at_one(detector, mock_page):
    """Test that confidence scores are capped at 1.0."""

    # Create a scenario where scores would exceed 1.0
    def mock_locator_func(selector):
        mock_loc = AsyncMock()
        # Match many selectors for the same state
        if "session" in selector.lower() or "expired" in selector.lower():
            mock_first = AsyncMock()
            mock_first.is_visible = AsyncMock(return_value=True)
            mock_loc.first = mock_first
        else:
            mock_loc.count = AsyncMock(return_value=0)
            mock_first = AsyncMock()
            mock_first.is_visible = AsyncMock(return_value=False)
            mock_loc.first = mock_first
        return mock_loc

    mock_page.locator = MagicMock(side_effect=mock_locator_func)

    result = await detector.detect(mock_page)

    # Confidence should never exceed 1.0
    assert result.confidence <= 1.0
