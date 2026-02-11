"""Tests for BookingWorkflow ErrorCapture integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import VFSBotError
from src.services.bot.booking_workflow import BookingWorkflow
from src.utils.error_capture import ErrorCapture

# Add parent directory to path for imports


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
        """Test that process_user exception handler calls error_capture.capture and re-raises."""
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

        # Call process_user - it should raise VFSBotError after max retries
        with pytest.raises(VFSBotError):
            await workflow.process_user(mock_page, mock_user)

        # Verify error_capture.capture was called (3 times due to retries)
        assert mock_error_capture.capture.call_count == 3
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
        """Test that error capture respects screenshot_on_error config and re-raises."""
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

        # Call process_user - it should raise VFSBotError after max retries
        with pytest.raises(VFSBotError):
            await workflow.process_user(mock_page, mock_user)

        # Verify error_capture.capture was NOT called (screenshot_on_error is False)
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

        # Setup mocks for the new form filling calls
        workflow.db.get_personal_details = AsyncMock(
            return_value={
                "first_name": "John",
                "last_name": "Doe",
                "email": "waitlist@example.com",
            }
        )
        workflow.booking_service.fill_all_applicants = AsyncMock()

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
    async def test_process_waitlist_flow_calls_form_filling(self, mock_dependencies):
        """Test that process_waitlist_flow calls the form filling methods."""
        workflow = BookingWorkflow(**mock_dependencies)

        mock_page = AsyncMock()
        mock_user = {
            "id": 123,
            "email": "test@example.com",
            "country": "bel",
        }

        mock_personal_details = {
            "first_name": "John",
            "last_name": "Doe",
            "gender": "male",
            "date_of_birth": "1990-01-01",
            "passport_number": "AB123456",
            "passport_expiry": "2030-01-01",
            "mobile_code": "32",
            "mobile_number": "1234567890",
            "email": "test@example.com",
        }

        # Setup all mocks for successful flow
        workflow.waitlist_handler.join_waitlist = AsyncMock(return_value=True)
        workflow.db.get_personal_details = AsyncMock(return_value=mock_personal_details)
        workflow.booking_service.fill_all_applicants = AsyncMock()
        workflow.waitlist_handler.accept_review_checkboxes = AsyncMock(return_value=True)
        workflow.waitlist_handler.click_confirm_button = AsyncMock(return_value=True)
        workflow.waitlist_handler.handle_waitlist_success = AsyncMock(
            return_value={
                "login_email": "test@example.com",
                "reference_number": "REF123",
                "screenshot_path": "/tmp/screenshot.png",
            }
        )
        workflow.notifier.notify_waitlist_success = AsyncMock()

        # Call process_waitlist_flow
        await workflow.process_waitlist_flow(mock_page, mock_user)

        # Verify that form filling methods were called
        workflow.db.get_personal_details.assert_called_once_with(123)
        workflow.booking_service.fill_all_applicants.assert_called_once()

        # Verify the reservation structure passed to fill_all_applicants
        call_args = workflow.booking_service.fill_all_applicants.call_args
        assert call_args[0][0] == mock_page  # page argument
        reservation = call_args[0][1]  # reservation argument

        # Check reservation structure
        assert "preferred_dates" in reservation
        assert reservation["preferred_dates"] == [""]  # Empty date for waitlist
        assert "person_count" in reservation
        assert "persons" in reservation
        assert len(reservation["persons"]) == 1
        assert reservation["persons"][0]["first_name"] == "John"
        assert reservation["persons"][0]["last_name"] == "Doe"

    @pytest.mark.asyncio
    async def test_process_waitlist_flow_no_personal_details(self, mock_dependencies):
        """Test that process_waitlist_flow returns early if no personal details found."""
        workflow = BookingWorkflow(**mock_dependencies)

        mock_page = AsyncMock()
        mock_user = {
            "id": 456,
            "email": "nodetails@example.com",
            "country": "bel",
        }

        # Setup mocks
        workflow.waitlist_handler.join_waitlist = AsyncMock(return_value=True)
        workflow.db.get_personal_details = AsyncMock(return_value=None)  # No personal details
        workflow.booking_service.fill_all_applicants = AsyncMock()
        workflow.waitlist_handler.accept_review_checkboxes = AsyncMock(return_value=True)

        # Call process_waitlist_flow
        await workflow.process_waitlist_flow(mock_page, mock_user)

        # Verify form filling was NOT called
        workflow.booking_service.fill_all_applicants.assert_not_called()

        # Verify that we returned early (checkboxes were NOT accepted)
        workflow.waitlist_handler.accept_review_checkboxes.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_capture_exception_is_caught(self, mock_dependencies):
        """Test that exceptions during error capture are caught and logged, but main exception is still raised."""
        mock_error_capture = MagicMock()
        mock_error_capture.capture = AsyncMock(side_effect=Exception("Error capture failed"))

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

        # Call process_user - should raise VFSBotError even if error capture fails
        with pytest.raises(VFSBotError):
            await workflow.process_user(mock_page, mock_user)

        # Verify error_capture.capture was called (and failed) - 3 times due to retries
        assert mock_error_capture.capture.call_count == 3
