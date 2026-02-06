"""Tests for BookingWorkflow ErrorCapture integration."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.bot.booking_workflow import BookingWorkflow
from src.utils.error_capture import ErrorCapture


class TestBookingWorkflowErrorCapture:
    """Test ErrorCapture integration in BookingWorkflow."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for BookingWorkflow."""
        config = {
            "bot": {
                "screenshot_on_error": True,
                "max_retries": 3,
            }
        }
        db = MagicMock()
        notifier = MagicMock()
        auth_service = MagicMock()
        slot_checker = MagicMock()
        booking_service = MagicMock()
        waitlist_handler = MagicMock()
        error_handler = MagicMock()
        slot_analyzer = MagicMock()
        session_recovery = MagicMock()
        
        return {
            "config": config,
            "db": db,
            "notifier": notifier,
            "auth_service": auth_service,
            "slot_checker": slot_checker,
            "booking_service": booking_service,
            "waitlist_handler": waitlist_handler,
            "error_handler": error_handler,
            "slot_analyzer": slot_analyzer,
            "session_recovery": session_recovery,
        }

    def test_init_with_error_capture(self, mock_dependencies):
        """Test BookingWorkflow initialization with ErrorCapture."""
        error_capture = ErrorCapture()
        
        workflow = BookingWorkflow(
            **mock_dependencies,
            error_capture=error_capture,
        )
        
        assert workflow.error_capture is error_capture

    def test_init_without_error_capture(self, mock_dependencies):
        """Test BookingWorkflow initialization without ErrorCapture creates default instance."""
        workflow = BookingWorkflow(**mock_dependencies)
        
        assert workflow.error_capture is not None
        assert isinstance(workflow.error_capture, ErrorCapture)

    def test_init_with_none_error_capture(self, mock_dependencies):
        """Test BookingWorkflow initialization with None creates default instance."""
        workflow = BookingWorkflow(
            **mock_dependencies,
            error_capture=None,
        )
        
        assert workflow.error_capture is not None
        assert isinstance(workflow.error_capture, ErrorCapture)

    @pytest.mark.asyncio
    async def test_process_user_error_calls_error_capture(self, mock_dependencies):
        """Test that process_user exception handler calls error_capture.capture."""
        mock_error_capture = MagicMock()
        mock_error_capture.capture = AsyncMock()
        
        workflow = BookingWorkflow(
            **mock_dependencies,
            error_capture=mock_error_capture,
        )
        
        mock_page = AsyncMock()
        mock_user = {
            "id": 123,
            "email": "test@example.com",
            "password": "test_password",  # Add password to avoid KeyError
            "country": "fra",
            "active": True,
        }
        
        # Make auth_service.login raise an exception to trigger error handler
        workflow.auth_service.login = AsyncMock(side_effect=Exception("Test login error"))
        
        # Call process_user - it should catch the exception
        await workflow.process_user(mock_page, mock_user)
        
        # Verify error_capture.capture was called
        mock_error_capture.capture.assert_called_once()
        call_args = mock_error_capture.capture.call_args
        
        # Check that page was passed
        assert call_args[0][0] == mock_page
        
        # Check that exception was passed
        assert isinstance(call_args[0][1], Exception)
        assert str(call_args[0][1]) == "Test login error"
        
        # Check context
        context = call_args[1]["context"]
        assert context["step"] == "process_user"
        assert context["user_id"] == "user_123"
        # Email is masked, so check for masked format
        assert "@" in context["email"]
        assert "***" in context["email"]

    @pytest.mark.asyncio
    async def test_process_user_respects_screenshot_on_error_config(self, mock_dependencies):
        """Test that error capture respects screenshot_on_error config."""
        mock_error_capture = MagicMock()
        mock_error_capture.capture = AsyncMock()
        
        # Disable screenshot_on_error
        mock_dependencies["config"]["bot"]["screenshot_on_error"] = False
        
        workflow = BookingWorkflow(
            **mock_dependencies,
            error_capture=mock_error_capture,
        )
        
        mock_page = AsyncMock()
        mock_user = {
            "id": 456,
            "email": "test2@example.com",
            "password": "test_password",  # Add password to avoid KeyError
            "country": "nld",
            "active": True,
        }
        
        # Make auth_service.login raise an exception
        workflow.auth_service.login = AsyncMock(side_effect=Exception("Test error"))
        
        # Call process_user
        await workflow.process_user(mock_page, mock_user)
        
        # Verify error_capture.capture was NOT called
        mock_error_capture.capture.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_waitlist_flow_error_calls_error_capture(self, mock_dependencies):
        """Test that process_waitlist_flow exception handler calls error_capture.capture."""
        mock_error_capture = MagicMock()
        mock_error_capture.capture = AsyncMock()
        
        workflow = BookingWorkflow(
            **mock_dependencies,
            error_capture=mock_error_capture,
        )
        
        mock_page = AsyncMock()
        mock_user = {
            "id": 789,
            "email": "waitlist@example.com",
            "country": "bel",
        }
        
        # Make waitlist_handler.join_waitlist raise an exception
        workflow.waitlist_handler.join_waitlist = AsyncMock(
            side_effect=Exception("Test waitlist error")
        )
        
        # Call process_waitlist_flow - it should catch the exception
        await workflow.process_waitlist_flow(mock_page, mock_user)
        
        # Verify error_capture.capture was called
        mock_error_capture.capture.assert_called_once()
        call_args = mock_error_capture.capture.call_args
        
        # Check that page was passed
        assert call_args[0][0] == mock_page
        
        # Check that exception was passed
        assert isinstance(call_args[0][1], Exception)
        assert str(call_args[0][1]) == "Test waitlist error"
        
        # Check context
        context = call_args[1]["context"]
        assert context["step"] == "waitlist_flow"
        assert context["user_id"] == "user_789"
        # Email is masked, so check for masked format
        assert "@" in context["email"]
        assert "***" in context["email"]

    @pytest.mark.asyncio
    async def test_error_capture_exception_is_caught(self, mock_dependencies):
        """Test that exceptions during error capture are caught and logged."""
        mock_error_capture = MagicMock()
        mock_error_capture.capture = AsyncMock(
            side_effect=Exception("Error capture failed")
        )
        
        workflow = BookingWorkflow(
            **mock_dependencies,
            error_capture=mock_error_capture,
        )
        
        mock_page = AsyncMock()
        mock_user = {
            "id": 999,
            "email": "error@example.com",
            "password": "test_password",  # Add password to avoid KeyError
            "country": "deu",
            "active": True,
        }
        
        # Make auth_service.login raise an exception
        workflow.auth_service.login = AsyncMock(side_effect=Exception("Login error"))
        
        # Call process_user - should not raise even if error capture fails
        try:
            await workflow.process_user(mock_page, mock_user)
        except Exception as e:
            pytest.fail(f"process_user should not raise even if error capture fails: {e}")
        
        # Verify error_capture.capture was called (and failed)
        mock_error_capture.capture.assert_called_once()
