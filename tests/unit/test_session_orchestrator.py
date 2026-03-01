"""Tests for SessionOrchestrator browser isolation."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.session.session_orchestrator import SessionOrchestrator


class MockBrowserManager:
    """
    Concrete mock browser manager whose constructor returns a fresh mock instance.

    Since _create_mission_browser uses type(self.browser_manager)(...) to create
    new browser instances, the test orchestrator must be initialised with an
    instance of this class.  Each call to MockBrowserManager(...) produces a new
    object with its own async start/close/new_page stubs.
    """

    def __init__(self, config=None, header_manager=None, proxy_manager=None):
        self.config = config or {}
        self.header_manager = header_manager
        self.proxy_manager = proxy_manager
        self.start = AsyncMock()
        self.close = AsyncMock()
        self._mock_page = AsyncMock()
        self._mock_page.close = AsyncMock()
        self.new_page = AsyncMock(return_value=self._mock_page)


@pytest.mark.asyncio
async def test_process_mission_creates_isolated_browser():
    """Test that _process_mission creates an isolated BrowserManager per mission."""
    # Mock dependencies
    db = MagicMock()
    account_pool = MagicMock()
    booking_workflow = MagicMock()

    # browser_manager is a MockBrowserManager instance; _create_mission_browser
    # will call type(browser_manager)(...) == MockBrowserManager(...).
    browser_manager = MockBrowserManager(
        config={"bot": {"headless": True}},
        header_manager=MagicMock(),
        proxy_manager=MagicMock(),
    )

    # Mock the repositories that are instantiated in __init__
    from unittest.mock import patch

    with (
        patch("src.services.session.session_orchestrator.AppointmentRequestRepository"),
        patch("src.services.session.session_orchestrator.AccountPoolRepository"),
    ):
        # Create orchestrator
        orchestrator = SessionOrchestrator(
            db=db,
            account_pool=account_pool,
            booking_workflow=booking_workflow,
            browser_manager=browser_manager,
        )

        # Mock account pool to return an account
        mock_account = MagicMock()
        mock_account.id = 1
        mock_account.email = "test@example.com"
        account_pool.acquire_account = AsyncMock(return_value=mock_account)
        account_pool.release_account = AsyncMock()

        # Mock appointment requests
        mock_requests = [
            MagicMock(id=1, country_code="fra"),
            MagicMock(id=2, country_code="fra"),
        ]

        # Mock booking workflow
        booking_workflow.process_mission = AsyncMock(return_value="success")

        # Mock account pool repository
        orchestrator.account_pool_repo.log_usage = AsyncMock()

        # Run _process_mission
        result = await orchestrator._process_mission("fra", mock_requests)

    # Verify booking workflow was called with the page created by MockBrowserManager
    booking_workflow.process_mission.assert_called_once()
    call_kwargs = booking_workflow.process_mission.call_args[1]
    assert call_kwargs["account"] == mock_account
    assert call_kwargs["appointment_requests"] == mock_requests

    # The page used must be the one from the mission browser instance
    mission_page = call_kwargs["page"]
    mission_page.close.assert_called_once()

    # Verify account was released
    account_pool.release_account.assert_called_once()

    # Verify result
    assert result["status"] == "completed"
    assert result["mission_code"] == "fra"
    assert result["result"] == "success"


@pytest.mark.asyncio
async def test_process_mission_multiple_missions_isolated():
    """Test that multiple missions create separate BrowserManager instances."""
    # Mock dependencies
    db = MagicMock()
    account_pool = MagicMock()
    booking_workflow = MagicMock()

    # Track all MockBrowserManager instances created during the test
    created_browsers: list = []
    original_init = MockBrowserManager.__init__

    def tracking_init(self, config=None, header_manager=None, proxy_manager=None):
        original_init(self, config, header_manager, proxy_manager)
        created_browsers.append(self)

    MockBrowserManager.__init__ = tracking_init  # type: ignore[method-assign]

    shared_config = {"bot": {"headless": True}}
    shared_header_manager = MagicMock()
    shared_proxy_manager = MagicMock()

    browser_manager = MockBrowserManager(
        config=shared_config,
        header_manager=shared_header_manager,
        proxy_manager=shared_proxy_manager,
    )
    # The injected browser_manager itself is the first entry; clear it so we only
    # count browsers created by the orchestrator.
    created_browsers.clear()

    from unittest.mock import patch

    with (
        patch("src.services.session.session_orchestrator.AppointmentRequestRepository"),
        patch("src.services.session.session_orchestrator.AccountPoolRepository"),
    ):
        orchestrator = SessionOrchestrator(
            db=db,
            account_pool=account_pool,
            booking_workflow=booking_workflow,
            browser_manager=browser_manager,
        )

        mock_account = MagicMock()
        mock_account.id = 1
        mock_account.email = "test@example.com"
        account_pool.acquire_account = AsyncMock(return_value=mock_account)
        account_pool.release_account = AsyncMock()
        booking_workflow.process_mission = AsyncMock(return_value="success")
        orchestrator.account_pool_repo.log_usage = AsyncMock()

        mock_requests_fra = [MagicMock(id=1, country_code="fra")]
        mock_requests_de = [MagicMock(id=2, country_code="de")]

        result1 = await orchestrator._process_mission("fra", mock_requests_fra)
        result2 = await orchestrator._process_mission("de", mock_requests_de)

    # Restore original __init__
    MockBrowserManager.__init__ = original_init  # type: ignore[method-assign]

    # Two isolated browser instances must have been created (one per mission)
    assert len(created_browsers) == 2
    assert created_browsers[0] is not created_browsers[1]

    # Verify both instances used the shared config
    for browser in created_browsers:
        assert browser.config == shared_config
        assert browser.header_manager == shared_header_manager
        assert browser.proxy_manager == shared_proxy_manager

    assert result1["status"] == "completed"
    assert result1["mission_code"] == "fra"
    assert result2["status"] == "completed"
    assert result2["mission_code"] == "de"


@pytest.mark.asyncio
async def test_process_mission_browser_cleanup_on_error():
    """Test that browser resources are cleaned up even when processing fails."""
    db = MagicMock()
    account_pool = MagicMock()
    booking_workflow = MagicMock()

    browser_manager = MockBrowserManager(
        config={"bot": {"headless": True}},
        header_manager=MagicMock(),
        proxy_manager=MagicMock(),
    )

    from unittest.mock import patch

    with (
        patch("src.services.session.session_orchestrator.AppointmentRequestRepository"),
        patch("src.services.session.session_orchestrator.AccountPoolRepository"),
    ):
        orchestrator = SessionOrchestrator(
            db=db,
            account_pool=account_pool,
            booking_workflow=booking_workflow,
            browser_manager=browser_manager,
        )

        mock_account = MagicMock()
        mock_account.id = 1
        mock_account.email = "test@example.com"
        account_pool.acquire_account = AsyncMock(return_value=mock_account)
        account_pool.release_account = AsyncMock()

        mock_requests = [MagicMock(id=1, country_code="fra")]
        booking_workflow.process_mission = AsyncMock(side_effect=Exception("Test error"))
        orchestrator.account_pool_repo.log_usage = AsyncMock()

        result = await orchestrator._process_mission("fra", mock_requests)

    # Verify result indicates error
    assert result["status"] == "error"
    assert "Test error" in result["error"]

    # Account must still be released despite the error
    account_pool.release_account.assert_called_once()
