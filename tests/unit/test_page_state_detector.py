"""Tests for PageStateDetector - page state detection and recovery system."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from playwright.async_api import Page

from src.core.exceptions import VFSBotError
from src.resilience import PageState, PageStateDetector, StateHandlerResult


class TestPageStateDetectorInitialization:
    """Tests for PageStateDetector initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        detector = PageStateDetector()

        assert detector.states_config_path == "config/page_states.yaml"
        assert detector.forensic_logger is None
        assert detector.notifier is None
        assert detector.auth_service is None
        assert detector.cloudflare_handler is None
        assert detector.captcha_solver is None
        assert detector.waitlist_handler is None
        assert detector.indicators is not None
        assert detector.transition_history == []

    def test_init_with_services(self):
        """Test initialization with service dependencies."""
        forensic_logger = Mock()
        notifier = Mock()
        auth_service = Mock()
        cloudflare_handler = Mock()

        detector = PageStateDetector(
            forensic_logger=forensic_logger,
            notifier=notifier,
            auth_service=auth_service,
            cloudflare_handler=cloudflare_handler,
        )

        assert detector.forensic_logger == forensic_logger
        assert detector.notifier == notifier
        assert detector.auth_service == auth_service
        assert detector.cloudflare_handler == cloudflare_handler

    def test_default_indicators_loaded(self):
        """Test that default indicators are loaded when config missing."""
        detector = PageStateDetector(states_config_path="nonexistent.yaml")

        # Should have default indicators
        assert "login_page" in detector.indicators
        assert "dashboard" in detector.indicators
        assert "captcha_page" in detector.indicators
        assert "cloudflare_challenge" in detector.indicators


class TestPageStateDetection:
    """Tests for page state detection."""

    @pytest.mark.asyncio
    async def test_detect_login_page(self):
        """Test detection of login page."""
        page = AsyncMock(spec=Page)
        page.url = "https://example.com/login"
        page.title = AsyncMock(return_value="Login - VFS")

        detector = PageStateDetector()
        state = await detector.detect(page)

        assert state == PageState.LOGIN_PAGE

    @pytest.mark.asyncio
    async def test_detect_dashboard(self):
        """Test detection of dashboard page."""
        page = AsyncMock(spec=Page)
        page.url = "https://example.com/dashboard"
        page.title = AsyncMock(return_value="Dashboard")

        detector = PageStateDetector()
        state = await detector.detect(page)

        assert state == PageState.DASHBOARD

    @pytest.mark.asyncio
    async def test_detect_cloudflare_challenge(self):
        """Test detection of Cloudflare challenge."""
        page = AsyncMock(spec=Page)
        page.url = "https://example.com/"
        page.title = AsyncMock(return_value="Just a moment...")

        detector = PageStateDetector()
        state = await detector.detect(page)

        assert state == PageState.CLOUDFLARE_CHALLENGE

    @pytest.mark.asyncio
    async def test_detect_session_expired(self):
        """Test detection of session expired state."""
        page = AsyncMock(spec=Page)
        page.url = "https://example.com/login"
        page.title = AsyncMock(return_value="Login")
        
        # Mock text locator for "session expired"
        locator_mock = AsyncMock()
        locator_mock.count = AsyncMock(return_value=1)
        page.locator = Mock(return_value=locator_mock)

        detector = PageStateDetector()
        state = await detector.detect(page)

        # Should detect session expired (higher priority than login)
        assert state == PageState.SESSION_EXPIRED

    @pytest.mark.asyncio
    async def test_detect_waitlist_mode(self):
        """Test detection of waitlist mode."""
        page = AsyncMock(spec=Page)
        page.url = "https://example.com/application"
        page.title = AsyncMock(return_value="Application")
        
        # Mock text locator for waitlist
        locator_mock = AsyncMock()
        locator_mock.count = AsyncMock(side_effect=lambda: 1 if "Waitlist" in str(page.locator.call_args) else 0)
        page.locator = Mock(return_value=locator_mock)

        detector = PageStateDetector()
        state = await detector.detect(page)

        assert state == PageState.WAITLIST_MODE

    @pytest.mark.asyncio
    async def test_detect_captcha_page(self):
        """Test detection of CAPTCHA page."""
        page = AsyncMock(spec=Page)
        page.url = "https://example.com/login"
        page.title = AsyncMock(return_value="Login")
        
        # Mock CSS selector for .g-recaptcha
        locator_mock = AsyncMock()
        locator_mock.count = AsyncMock(side_effect=lambda: 1 if "recaptcha" in str(page.locator.call_args) else 0)
        page.locator = Mock(return_value=locator_mock)

        detector = PageStateDetector()
        state = await detector.detect(page)

        assert state == PageState.CAPTCHA_PAGE

    @pytest.mark.asyncio
    async def test_detect_maintenance_page(self):
        """Test detection of maintenance page."""
        page = AsyncMock(spec=Page)
        page.url = "https://example.com/"
        page.title = AsyncMock(return_value="Maintenance")

        detector = PageStateDetector()
        state = await detector.detect(page)

        assert state == PageState.MAINTENANCE_PAGE

    @pytest.mark.asyncio
    async def test_detect_unknown_state(self):
        """Test detection of unknown state."""
        page = AsyncMock(spec=Page)
        page.url = "https://example.com/weird-page"
        page.title = AsyncMock(return_value="Unknown Page")
        
        # No indicators match
        locator_mock = AsyncMock()
        locator_mock.count = AsyncMock(return_value=0)
        page.locator = Mock(return_value=locator_mock)

        detector = PageStateDetector()
        state = await detector.detect(page)

        assert state == PageState.UNKNOWN

    @pytest.mark.asyncio
    async def test_detect_priority_order(self):
        """Test that detection follows correct priority order."""
        page = AsyncMock(spec=Page)
        page.url = "https://example.com/login"
        page.title = AsyncMock(return_value="Just a moment...")
        
        # Both Cloudflare and login indicators present
        # Cloudflare should win due to higher priority
        detector = PageStateDetector()
        state = await detector.detect(page)

        assert state == PageState.CLOUDFLARE_CHALLENGE


class TestStateAssertion:
    """Tests for state assertion."""

    @pytest.mark.asyncio
    async def test_assert_state_success(self):
        """Test successful state assertion."""
        page = AsyncMock(spec=Page)
        page.url = "https://example.com/dashboard"
        page.title = AsyncMock(return_value="Dashboard")

        detector = PageStateDetector()
        result = await detector.assert_state(page, PageState.DASHBOARD, timeout=1000)

        assert result is True

    @pytest.mark.asyncio
    async def test_assert_state_failure(self):
        """Test failed state assertion."""
        page = AsyncMock(spec=Page)
        page.url = "https://example.com/login"
        page.title = AsyncMock(return_value="Login")

        detector = PageStateDetector()
        result = await detector.assert_state(page, PageState.DASHBOARD, timeout=1000)

        assert result is False

    @pytest.mark.asyncio
    async def test_assert_state_with_timeout(self):
        """Test state assertion waits for expected state."""
        page = AsyncMock(spec=Page)
        # Start with login, change to dashboard after short delay
        page.url = "https://example.com/login"
        page.title = AsyncMock(return_value="Login")

        async def change_to_dashboard():
            await asyncio.sleep(0.2)
            page.url = "https://example.com/dashboard"
            page.title = AsyncMock(return_value="Dashboard")

        asyncio.create_task(change_to_dashboard())

        detector = PageStateDetector()
        result = await detector.assert_state(page, PageState.DASHBOARD, timeout=2000)

        assert result is True


class TestStateHandling:
    """Tests for state handling and recovery."""

    @pytest.mark.asyncio
    async def test_handle_normal_state(self):
        """Test handling of normal states (no action needed)."""
        page = AsyncMock(spec=Page)
        detector = PageStateDetector()

        result = await detector.handle_state(page, PageState.DASHBOARD)

        assert result.success is True
        assert result.state == PageState.DASHBOARD
        assert "no action needed" in result.action_taken.lower()

    @pytest.mark.asyncio
    async def test_handle_session_expired_success(self):
        """Test successful session expired recovery."""
        page = AsyncMock(spec=Page)
        auth_service = AsyncMock()
        auth_service.login = AsyncMock(return_value=True)

        detector = PageStateDetector(auth_service=auth_service)
        context = {"email": "test@example.com", "password": "password"}
        
        result = await detector.handle_state(page, PageState.SESSION_EXPIRED, context)

        assert result.success is True
        assert result.state == PageState.SESSION_EXPIRED
        assert result.should_retry is True
        assert result.next_state == PageState.DASHBOARD
        auth_service.login.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_session_expired_no_auth_service(self):
        """Test session expired handling without auth service."""
        page = AsyncMock(spec=Page)
        detector = PageStateDetector()  # No auth_service
        context = {"email": "test@example.com", "password": "password"}
        
        result = await detector.handle_state(page, PageState.SESSION_EXPIRED, context)

        assert result.success is False
        assert result.should_abort is True

    @pytest.mark.asyncio
    async def test_handle_session_expired_missing_credentials(self):
        """Test session expired handling with missing credentials."""
        page = AsyncMock(spec=Page)
        auth_service = AsyncMock()
        
        detector = PageStateDetector(auth_service=auth_service)
        context = {}  # Missing email and password
        
        result = await detector.handle_state(page, PageState.SESSION_EXPIRED, context)

        assert result.success is False
        assert result.should_abort is True

    @pytest.mark.asyncio
    async def test_handle_cloudflare_challenge_success(self):
        """Test successful Cloudflare challenge handling."""
        page = AsyncMock(spec=Page)
        cloudflare_handler = AsyncMock()
        cloudflare_handler.detect_cloudflare_challenge = AsyncMock(return_value="turnstile")
        cloudflare_handler.handle_challenge = AsyncMock(return_value=True)

        detector = PageStateDetector(cloudflare_handler=cloudflare_handler)
        
        result = await detector.handle_state(page, PageState.CLOUDFLARE_CHALLENGE)

        assert result.success is True
        assert result.should_retry is True
        cloudflare_handler.handle_challenge.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_cloudflare_challenge_no_handler(self):
        """Test Cloudflare handling without handler."""
        page = AsyncMock(spec=Page)
        detector = PageStateDetector()  # No cloudflare_handler
        
        result = await detector.handle_state(page, PageState.CLOUDFLARE_CHALLENGE)

        assert result.success is False
        assert result.should_abort is True

    @pytest.mark.asyncio
    async def test_handle_captcha_with_solver(self):
        """Test CAPTCHA handling with solver."""
        page = AsyncMock(spec=Page)
        captcha_solver = AsyncMock()
        captcha_solver.solve = AsyncMock(return_value=True)

        detector = PageStateDetector(captcha_solver=captcha_solver)
        
        result = await detector.handle_state(page, PageState.CAPTCHA_PAGE)

        assert result.success is True
        assert result.should_retry is True
        captcha_solver.solve.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_captcha_without_solver(self):
        """Test CAPTCHA handling without solver."""
        page = AsyncMock(spec=Page)
        notifier = AsyncMock()
        notifier.send_alert = AsyncMock()

        detector = PageStateDetector(notifier=notifier)
        
        result = await detector.handle_state(page, PageState.CAPTCHA_PAGE)

        assert result.success is False
        assert result.should_abort is True
        # Should send notification
        assert notifier.send_alert.called

    @pytest.mark.asyncio
    async def test_handle_maintenance_page(self):
        """Test maintenance page handling."""
        page = AsyncMock(spec=Page)
        notifier = AsyncMock()
        notifier.send_alert = AsyncMock()

        detector = PageStateDetector(notifier=notifier)
        context = {"maintenance_wait_time": 1}  # Short wait for test
        
        result = await detector.handle_state(page, PageState.MAINTENANCE_PAGE, context)

        assert result.success is True
        assert result.should_retry is True
        assert "waited" in result.action_taken.lower()

    @pytest.mark.asyncio
    async def test_handle_rate_limited(self):
        """Test rate limiting handling."""
        page = AsyncMock(spec=Page)
        detector = PageStateDetector()
        context = {"rate_limit_retry_count": 0}
        
        result = await detector.handle_state(page, PageState.RATE_LIMITED, context)

        assert result.success is True
        assert result.should_retry is True
        assert result.metadata["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_handle_unknown_state(self):
        """Test unknown state handling."""
        page = AsyncMock(spec=Page)
        page.url = "https://example.com/unknown"
        
        forensic_logger = AsyncMock()
        forensic_logger.capture_incident = AsyncMock()
        notifier = AsyncMock()
        notifier.send_alert = AsyncMock()

        detector = PageStateDetector(
            forensic_logger=forensic_logger,
            notifier=notifier,
        )
        
        result = await detector.handle_state(page, PageState.UNKNOWN)

        assert result.success is False
        assert result.should_abort is True
        assert "forensic" in result.action_taken.lower()
        
        # Should capture forensic evidence and notify
        assert forensic_logger.capture_incident.called
        assert notifier.send_alert.called


class TestUnexpectedStateHandling:
    """Tests for unexpected state transitions."""

    @pytest.mark.asyncio
    async def test_handle_unexpected_state(self):
        """Test handling of unexpected state transition."""
        page = AsyncMock(spec=Page)
        page.url = "https://example.com/maintenance"
        page.title = AsyncMock(return_value="Maintenance")
        
        notifier = AsyncMock()
        notifier.send_alert = AsyncMock()

        detector = PageStateDetector(notifier=notifier)
        context = {"maintenance_wait_time": 1}
        
        # Expected dashboard, but got maintenance page
        result = await detector.handle_unexpected_state(
            page, PageState.MAINTENANCE_PAGE, PageState.DASHBOARD
        )

        assert result.state == PageState.MAINTENANCE_PAGE
        # Should delegate to handle_state
        assert result.should_retry is True


class TestTransitionHistory:
    """Tests for transition history tracking."""

    @pytest.mark.asyncio
    async def test_transition_history_recorded(self):
        """Test that state transitions are recorded."""
        page = AsyncMock(spec=Page)
        detector = PageStateDetector()

        # Handle multiple states
        await detector.handle_state(page, PageState.LOGIN_PAGE)
        await detector.handle_state(page, PageState.DASHBOARD)
        await detector.handle_state(page, PageState.WAITLIST_MODE)

        assert len(detector.transition_history) == 3
        assert detector.transition_history[0]["state"] == "login_page"
        assert detector.transition_history[1]["state"] == "dashboard"
        assert detector.transition_history[2]["state"] == "waitlist_mode"


class TestUnknownStateWithAI:
    """Tests for unknown state handling with AI integration."""

    @pytest.mark.asyncio
    async def test_handle_unknown_state_with_learned_action(self):
        """Test unknown state handling when learned action is available."""
        from src.resilience.learned_state_store import LearnedAction

        page = AsyncMock(spec=Page)
        page.url = "https://example.com/verify"
        page.content = AsyncMock(return_value="<div>Enter code</div>")

        learned_store = Mock()
        learned_action = LearnedAction(
            state_name="code_verification",
            action_type="fill",
            target_selector="#code",
            fill_value="",
            indicators={},
            match_score=0.85,
        )
        learned_store.get_learned_action = Mock(return_value=learned_action)

        # Mock locator for the action
        locator = AsyncMock()
        page.locator = Mock(return_value=locator)

        detector = PageStateDetector(learned_store=learned_store)
        result = await detector.handle_state(page, PageState.UNKNOWN)

        # Should apply learned action
        assert result.success is True
        assert result.should_retry is True
        assert "learned action" in result.action_taken.lower()
        assert learned_store.get_learned_action.called

    @pytest.mark.asyncio
    async def test_handle_unknown_state_with_ai_success(self):
        """Test unknown state handling when AI suggests successful action."""
        from src.resilience.ai_page_analyzer import PageAction, PageAnalysisResult

        page = AsyncMock(spec=Page)
        page.url = "https://example.com/unknown"
        page.content = AsyncMock(return_value="<div>Click continue</div>")

        # Mock AI analyzer
        ai_analyzer = Mock()
        analysis_result = PageAnalysisResult(
            page_purpose="Confirmation page",
            suggested_action=PageAction.CLICK,
            target_selector="#continue-btn",
            fill_value="",
            confidence=0.9,
            reasoning="Found continue button",
            suggested_indicators={
                "url_patterns": [".*unknown.*"],
                "text_indicators": ["Click continue"],
                "css_selectors": ["#continue-btn"],
            },
            suggested_state_name="confirmation_page",
        )
        ai_analyzer.analyze_page = AsyncMock(return_value=analysis_result)

        # Mock learned store
        learned_store = Mock()
        learned_store.get_learned_action = Mock(return_value=None)
        learned_store.save_learned_state = Mock(return_value=True)

        # Mock locator for clicking
        locator = AsyncMock()
        page.locator = Mock(return_value=locator)
        page.wait_for_load_state = AsyncMock()

        # Mock detect to return a known state after action
        detector = PageStateDetector(
            ai_analyzer=ai_analyzer,
            learned_store=learned_store,
        )

        # Patch detect to return known state after action
        with patch.object(detector, "detect", return_value=PageState.DASHBOARD):
            result = await detector.handle_state(page, PageState.UNKNOWN)

        # Should apply AI action and save learned state
        assert result.success is True
        assert result.should_retry is True
        assert "ai solved" in result.action_taken.lower()
        assert ai_analyzer.analyze_page.called
        assert learned_store.save_learned_state.called

    @pytest.mark.asyncio
    async def test_handle_unknown_state_ai_action_fails(self):
        """Test unknown state handling when AI action fails."""
        from src.resilience.ai_page_analyzer import PageAction, PageAnalysisResult

        page = AsyncMock(spec=Page)
        page.url = "https://example.com/unknown"
        page.content = AsyncMock(return_value="<div>Error</div>")

        # Mock AI analyzer
        ai_analyzer = Mock()
        analysis_result = PageAnalysisResult(
            page_purpose="Error page",
            suggested_action=PageAction.CLICK,
            target_selector="#nonexistent",
            fill_value="",
            confidence=0.8,
            reasoning="Try clicking",
            suggested_indicators={},
            suggested_state_name="error_page",
        )
        ai_analyzer.analyze_page = AsyncMock(return_value=analysis_result)

        # Mock learned store
        learned_store = Mock()
        learned_store.get_learned_action = Mock(return_value=None)

        # Mock locator that throws error
        locator = AsyncMock()
        locator.click = AsyncMock(side_effect=Exception("Element not found"))
        page.locator = Mock(return_value=locator)

        forensic_logger = AsyncMock()
        forensic_logger.capture_incident = AsyncMock()

        detector = PageStateDetector(
            ai_analyzer=ai_analyzer,
            learned_store=learned_store,
            forensic_logger=forensic_logger,
        )

        result = await detector.handle_state(page, PageState.UNKNOWN)

        # Should fall back to abort
        assert result.success is False
        assert result.should_abort is True

    @pytest.mark.asyncio
    async def test_handle_unknown_state_ai_suggests_abort(self):
        """Test unknown state handling when AI suggests abort."""
        from src.resilience.ai_page_analyzer import PageAction, PageAnalysisResult

        page = AsyncMock(spec=Page)
        page.url = "https://example.com/unknown"
        page.content = AsyncMock(return_value="<div>Complex page</div>")

        # Mock AI analyzer that suggests abort
        ai_analyzer = Mock()
        analysis_result = PageAnalysisResult(
            page_purpose="Unknown complex page",
            suggested_action=PageAction.ABORT,
            target_selector="",
            fill_value="",
            confidence=0.5,
            reasoning="Too complex to handle automatically",
            suggested_indicators={},
            suggested_state_name="unknown",
        )
        ai_analyzer.analyze_page = AsyncMock(return_value=analysis_result)

        # Mock learned store
        learned_store = Mock()
        learned_store.get_learned_action = Mock(return_value=None)

        forensic_logger = AsyncMock()
        forensic_logger.capture_incident = AsyncMock()

        detector = PageStateDetector(
            ai_analyzer=ai_analyzer,
            learned_store=learned_store,
            forensic_logger=forensic_logger,
        )

        result = await detector.handle_state(page, PageState.UNKNOWN)

        # Should abort
        assert result.success is False
        assert result.should_abort is True

    @pytest.mark.asyncio
    async def test_handle_unknown_state_no_ai_available(self):
        """Test unknown state handling when AI is not available (legacy behavior)."""
        page = AsyncMock(spec=Page)
        page.url = "https://example.com/unknown"

        forensic_logger = AsyncMock()
        forensic_logger.capture_incident = AsyncMock()
        notifier = AsyncMock()
        notifier.send_alert = AsyncMock()

        # No AI analyzer or learned store
        detector = PageStateDetector(
            forensic_logger=forensic_logger,
            notifier=notifier,
        )

        result = await detector.handle_state(page, PageState.UNKNOWN)

        # Should fall back to legacy abort behavior
        assert result.success is False
        assert result.should_abort is True
        assert forensic_logger.capture_incident.called
        assert notifier.send_alert.called


class TestApplyAction:
    """Tests for _apply_action helper method."""

    @pytest.mark.asyncio
    async def test_apply_click_action(self):
        """Test applying a click action."""
        page = AsyncMock(spec=Page)
        locator = AsyncMock()
        page.locator = Mock(return_value=locator)
        page.wait_for_load_state = AsyncMock()

        detector = PageStateDetector()
        success = await detector._apply_action(page, "click", "#button")

        assert success is True
        locator.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_wait_action(self):
        """Test applying a wait action."""
        page = AsyncMock(spec=Page)
        detector = PageStateDetector()

        success = await detector._apply_action(page, "wait")

        assert success is True

    @pytest.mark.asyncio
    async def test_apply_fill_action(self):
        """Test applying a fill action."""
        page = AsyncMock(spec=Page)
        locator = AsyncMock()
        page.locator = Mock(return_value=locator)

        detector = PageStateDetector()
        success = await detector._apply_action(page, "fill", "#input", "test_value")

        assert success is True
        locator.fill.assert_called_once_with("test_value", timeout=10000)

    @pytest.mark.asyncio
    async def test_apply_dismiss_action_with_selector(self):
        """Test applying a dismiss action with specific selector."""
        page = AsyncMock(spec=Page)
        locator = AsyncMock()
        page.locator = Mock(return_value=locator)

        detector = PageStateDetector()
        success = await detector._apply_action(page, "dismiss", "#close-btn")

        assert success is True
        locator.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_navigate_back_action(self):
        """Test applying a navigate back action."""
        page = AsyncMock(spec=Page)
        page.go_back = AsyncMock()

        detector = PageStateDetector()
        success = await detector._apply_action(page, "navigate_back")

        assert success is True
        page.go_back.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_refresh_action(self):
        """Test applying a refresh action."""
        page = AsyncMock(spec=Page)
        page.reload = AsyncMock()

        detector = PageStateDetector()
        success = await detector._apply_action(page, "refresh")

        assert success is True
        page.reload.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_invalid_action(self):
        """Test applying an invalid action."""
        page = AsyncMock(spec=Page)
        detector = PageStateDetector()

        success = await detector._apply_action(page, "invalid_action")

        assert success is False

    @pytest.mark.asyncio
    async def test_apply_action_handles_exception(self):
        """Test that _apply_action handles exceptions gracefully."""
        page = AsyncMock(spec=Page)
        locator = AsyncMock()
        locator.click = AsyncMock(side_effect=Exception("Click failed"))
        page.locator = Mock(return_value=locator)

        detector = PageStateDetector()
        success = await detector._apply_action(page, "click", "#button")

        assert success is False


    @pytest.mark.asyncio
    async def test_transition_context_captured(self):
        """Test that transition context is captured."""
        page = AsyncMock(spec=Page)
        detector = PageStateDetector()

        context = {"user_id": 123, "email": "test@example.com"}
        await detector.handle_state(page, PageState.DASHBOARD, context)

        assert len(detector.transition_history) == 1
        assert detector.transition_history[0]["context"] == context


class TestPageStateEnum:
    """Tests for PageState enum."""

    def test_all_states_defined(self):
        """Test that all expected states are defined."""
        expected_states = [
            "LOGIN_PAGE",
            "DASHBOARD",
            "CAPTCHA_PAGE",
            "OTP_VERIFICATION",
            "CLOUDFLARE_CHALLENGE",
            "SESSION_EXPIRED",
            "MAINTENANCE_PAGE",
            "RATE_LIMITED",
            "WAITLIST_MODE",
            "WAITLIST_SUCCESS",
            "UNKNOWN",
        ]

        for state_name in expected_states:
            assert hasattr(PageState, state_name)

    def test_state_values(self):
        """Test that state values are lowercase with underscores."""
        for state in PageState:
            assert state.value.islower()
            assert " " not in state.value


class TestStateHandlerResult:
    """Tests for StateHandlerResult dataclass."""

    def test_result_creation(self):
        """Test creating StateHandlerResult."""
        result = StateHandlerResult(
            success=True,
            state=PageState.DASHBOARD,
            action_taken="Navigated to dashboard",
        )

        assert result.success is True
        assert result.state == PageState.DASHBOARD
        assert result.action_taken == "Navigated to dashboard"
        assert result.next_state is None
        assert result.should_retry is False
        assert result.should_abort is False

    def test_result_with_all_fields(self):
        """Test creating StateHandlerResult with all fields."""
        result = StateHandlerResult(
            success=False,
            state=PageState.SESSION_EXPIRED,
            next_state=PageState.LOGIN_PAGE,
            action_taken="Re-login required",
            should_retry=True,
            should_abort=False,
            metadata={"retry_count": 1},
        )

        assert result.success is False
        assert result.state == PageState.SESSION_EXPIRED
        assert result.next_state == PageState.LOGIN_PAGE
        assert result.should_retry is True
        assert result.metadata["retry_count"] == 1
