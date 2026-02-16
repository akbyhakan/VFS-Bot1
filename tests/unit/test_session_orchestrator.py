"""Tests for SessionOrchestrator browser isolation."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.services.session.session_orchestrator import SessionOrchestrator


@pytest.mark.asyncio
async def test_process_mission_creates_isolated_browser():
    """Test that _process_mission creates an isolated BrowserManager per mission."""
    # Mock dependencies
    db = MagicMock()
    account_pool = MagicMock()
    booking_workflow = MagicMock()
    browser_manager = MagicMock()
    
    # Configure browser_manager attributes
    browser_manager.config = {"bot": {"headless": True}}
    browser_manager.header_manager = MagicMock()
    browser_manager.proxy_manager = MagicMock()
    
    # Mock the repositories that are instantiated in __init__
    with patch("src.services.session.session_orchestrator.AppointmentRequestRepository"), \
         patch("src.services.session.session_orchestrator.AccountPoolRepository"):
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
    
    # Mock BrowserManager creation
    with patch("src.services.bot.browser_manager.BrowserManager") as MockBrowserManager:
        mock_mission_browser = MagicMock()
        mock_mission_browser.start = AsyncMock()
        mock_mission_browser.close = AsyncMock()
        mock_page = AsyncMock()
        mock_page.close = AsyncMock()
        mock_mission_browser.new_page = AsyncMock(return_value=mock_page)
        
        MockBrowserManager.return_value = mock_mission_browser
        
        # Run _process_mission
        result = await orchestrator._process_mission("fra", mock_requests)
        
        # Verify BrowserManager was instantiated with correct parameters
        MockBrowserManager.assert_called_once_with(
            config=browser_manager.config,
            header_manager=browser_manager.header_manager,
            proxy_manager=browser_manager.proxy_manager,
        )
        
        # Verify browser lifecycle
        mock_mission_browser.start.assert_called_once()
        mock_mission_browser.new_page.assert_called_once()
        
        # Verify page was closed
        mock_page.close.assert_called_once()
        
        # Verify browser was closed (cleanup)
        mock_mission_browser.close.assert_called_once()
        
        # Verify booking workflow was called
        booking_workflow.process_mission.assert_called_once_with(
            page=mock_page,
            account=mock_account,
            appointment_requests=mock_requests,
        )
        
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
    browser_manager = MagicMock()
    
    # Configure browser_manager attributes
    browser_manager.config = {"bot": {"headless": True}}
    browser_manager.header_manager = MagicMock()
    browser_manager.proxy_manager = MagicMock()
    
    # Mock the repositories that are instantiated in __init__
    with patch("src.services.session.session_orchestrator.AppointmentRequestRepository"), \
         patch("src.services.session.session_orchestrator.AccountPoolRepository"):
        # Create orchestrator
        orchestrator = SessionOrchestrator(
            db=db,
            account_pool=account_pool,
            booking_workflow=booking_workflow,
            browser_manager=browser_manager,
        )
        
        # Mock account pool to return an account each time
        mock_account = MagicMock()
        mock_account.id = 1
        mock_account.email = "test@example.com"
        account_pool.acquire_account = AsyncMock(return_value=mock_account)
        account_pool.release_account = AsyncMock()
        
        # Mock booking workflow
        booking_workflow.process_mission = AsyncMock(return_value="success")
        
        # Mock account pool repository
        orchestrator.account_pool_repo.log_usage = AsyncMock()
    
    # Mock BrowserManager creation
    with patch("src.services.bot.browser_manager.BrowserManager") as MockBrowserManager:
        def create_browser_instance(*args, **kwargs):
            mock_browser = MagicMock()
            mock_browser.start = AsyncMock()
            mock_browser.close = AsyncMock()
            mock_page = AsyncMock()
            mock_page.close = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            return mock_browser
        
        MockBrowserManager.side_effect = create_browser_instance
        
        # Process two different missions
        mock_requests_fra = [MagicMock(id=1, country_code="fra")]
        mock_requests_de = [MagicMock(id=2, country_code="de")]
        
        result1 = await orchestrator._process_mission("fra", mock_requests_fra)
        result2 = await orchestrator._process_mission("de", mock_requests_de)
        
        # Verify BrowserManager was instantiated twice (once per mission)
        assert MockBrowserManager.call_count == 2
        
        # Verify both calls used the same config
        for call_args in MockBrowserManager.call_args_list:
            assert call_args[1]["config"] == browser_manager.config
            assert call_args[1]["header_manager"] == browser_manager.header_manager
            assert call_args[1]["proxy_manager"] == browser_manager.proxy_manager
        
        # Verify both missions completed successfully
        assert result1["status"] == "completed"
        assert result1["mission_code"] == "fra"
        assert result2["status"] == "completed"
        assert result2["mission_code"] == "de"


@pytest.mark.asyncio
async def test_process_mission_browser_cleanup_on_error():
    """Test that browser resources are cleaned up even when processing fails."""
    # Mock dependencies
    db = MagicMock()
    account_pool = MagicMock()
    booking_workflow = MagicMock()
    browser_manager = MagicMock()
    
    # Configure browser_manager attributes
    browser_manager.config = {"bot": {"headless": True}}
    browser_manager.header_manager = MagicMock()
    browser_manager.proxy_manager = MagicMock()
    
    # Mock the repositories that are instantiated in __init__
    with patch("src.services.session.session_orchestrator.AppointmentRequestRepository"), \
         patch("src.services.session.session_orchestrator.AccountPoolRepository"):
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
        mock_requests = [MagicMock(id=1, country_code="fra")]
        
        # Mock booking workflow to raise an error
        booking_workflow.process_mission = AsyncMock(side_effect=Exception("Test error"))
        
        # Mock account pool repository
        orchestrator.account_pool_repo.log_usage = AsyncMock()
    
    # Mock BrowserManager creation
    with patch("src.services.bot.browser_manager.BrowserManager") as MockBrowserManager:
        mock_mission_browser = MagicMock()
        mock_mission_browser.start = AsyncMock()
        mock_mission_browser.close = AsyncMock()
        mock_page = AsyncMock()
        mock_page.close = AsyncMock()
        mock_mission_browser.new_page = AsyncMock(return_value=mock_page)
        
        MockBrowserManager.return_value = mock_mission_browser
        
        # Run _process_mission (should handle the error)
        result = await orchestrator._process_mission("fra", mock_requests)
        
        # Verify browser was still closed despite the error
        mock_page.close.assert_called_once()
        mock_mission_browser.close.assert_called_once()
        
        # Verify account was still released
        account_pool.release_account.assert_called_once()
        
        # Verify result indicates error
        assert result["status"] == "error"
        assert "Test error" in result["error"]
