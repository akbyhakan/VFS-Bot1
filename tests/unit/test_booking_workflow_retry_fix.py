"""Tests for BookingWorkflow retry mechanism fixes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tenacity import RetryError

from src.core.exceptions import LoginError, VFSBotError
from src.services.bot.booking_workflow import BookingWorkflow

# Add parent directory to path for imports


class TestBookingWorkflowRetryFix:
    """Test that retry mechanism works correctly after fixes."""

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

    @pytest.mark.asyncio
    async def test_login_failure_raises_exception(self, mock_dependencies):
        """Test that login failure raises LoginError instead of returning."""
        workflow = BookingWorkflow(**mock_dependencies)

        mock_page = AsyncMock()
        mock_user = {
            "id": 123,
            "email": "test@example.com",
            "password": "test_password",
            "country": "fra",
            "active": True,
        }

        # Make auth_service.login return False
        workflow.auth_service.login = AsyncMock(return_value=False)

        # Should raise LoginError
        with pytest.raises(LoginError) as exc_info:
            await workflow.process_user(mock_page, mock_user)

        assert "Login failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_login_error_triggers_retry(self, mock_dependencies):
        """Test that LoginError triggers retry mechanism."""
        workflow = BookingWorkflow(**mock_dependencies)

        mock_page = AsyncMock()
        mock_user = {
            "id": 123,
            "email": "test@example.com",
            "password": "test_password",
            "country": "fra",
            "centre": "Paris",
            "category": "visa",
            "subcategory": "tourism",
            "active": True,
        }

        call_count = [0]

        async def login_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                return False  # Fail first 2 times
            return True  # Succeed on 3rd attempt

        workflow.auth_service.login = AsyncMock(side_effect=login_side_effect)
        workflow.waitlist_handler.detect_waitlist_mode = AsyncMock(return_value=False)
        workflow.slot_checker.check_slots = AsyncMock(return_value=None)

        # Should succeed after retries
        await workflow.process_user(mock_page, mock_user)

        # Verify login was called 3 times
        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_exception_wrapped_in_vfserror_and_reraised(self, mock_dependencies):
        """Test that unexpected exceptions are wrapped in VFSBotError and re-raised."""
        workflow = BookingWorkflow(**mock_dependencies)

        mock_page = AsyncMock()
        mock_user = {
            "id": 123,
            "email": "test@example.com",
            "password": "test_password",
            "country": "fra",
            "active": True,
        }

        # Make auth_service.login raise an unexpected exception
        workflow.auth_service.login = AsyncMock(side_effect=ValueError("Unexpected error"))

        # Should raise VFSBotError wrapping the ValueError
        with pytest.raises(VFSBotError) as exc_info:
            await workflow.process_user(mock_page, mock_user)

        assert "Unexpected error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_vfserror_triggers_retry_and_eventually_propagates(self, mock_dependencies):
        """Test that VFSBotError triggers retry and eventually propagates."""
        workflow = BookingWorkflow(**mock_dependencies)

        mock_page = AsyncMock()
        mock_user = {
            "id": 123,
            "email": "test@example.com",
            "password": "test_password",
            "country": "fra",
            "active": True,
        }

        call_count = [0]

        async def login_side_effect(*args, **kwargs):
            call_count[0] += 1
            raise ValueError("Test error")

        workflow.auth_service.login = AsyncMock(side_effect=login_side_effect)

        # Should raise VFSBotError after max retries
        with pytest.raises(VFSBotError):
            await workflow.process_user(mock_page, mock_user)

        # Verify login was called 3 times (max retries)
        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_checkpoint_does_not_store_plaintext_email(self, mock_dependencies):
        """Test that checkpoint stores only masked_email, not plaintext email."""
        workflow = BookingWorkflow(**mock_dependencies)

        mock_page = AsyncMock()
        mock_user = {
            "id": 123,
            "email": "test@example.com",
            "password": "test_password",
            "country": "fra",
            "centre": "Paris",
            "category": "visa",
            "subcategory": "tourism",
            "active": True,
        }

        workflow.auth_service.login = AsyncMock(return_value=True)
        workflow.waitlist_handler.detect_waitlist_mode = AsyncMock(return_value=False)
        workflow.slot_checker.check_slots = AsyncMock(return_value=None)

        await workflow.process_user(mock_page, mock_user)

        # Verify checkpoint was saved
        workflow.session_recovery.save_checkpoint.assert_called_once()
        call_args = workflow.session_recovery.save_checkpoint.call_args

        # Check that checkpoint data contains masked_email but not email
        checkpoint_data = call_args[0][2]
        assert "masked_email" in checkpoint_data
        assert "email" not in checkpoint_data

    @pytest.mark.asyncio
    async def test_error_capture_called_on_exception(self, mock_dependencies):
        """Test that error capture is called when exception occurs."""
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
            "password": "test_password",
            "country": "fra",
            "active": True,
        }

        workflow.auth_service.login = AsyncMock(side_effect=ValueError("Test error"))

        # Should raise VFSBotError after max retries
        with pytest.raises(VFSBotError):
            await workflow.process_user(mock_page, mock_user)

        # Verify error_capture.capture was called (3 times due to retries)
        assert mock_error_capture.capture.call_count == 3


class TestBookingWorkflowHelperMethods:
    """Test the new helper methods."""

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

    @pytest.mark.asyncio
    async def test_capture_error_safe(self, mock_dependencies):
        """Test _capture_error_safe helper method."""
        mock_error_capture = MagicMock()
        mock_error_capture.capture = AsyncMock()

        workflow = BookingWorkflow(
            **mock_dependencies,
            error_capture=mock_error_capture,
        )

        mock_page = AsyncMock()
        test_error = ValueError("Test error")

        await workflow._capture_error_safe(
            mock_page, test_error, "test_step", 123, "t***@example.com"
        )

        mock_error_capture.capture.assert_called_once()
        call_args = mock_error_capture.capture.call_args
        assert call_args[0][0] == mock_page
        assert call_args[0][1] == test_error
        assert call_args[1]["context"]["step"] == "test_step"
        assert call_args[1]["context"]["user_id"] == "user_123"
        assert call_args[1]["context"]["email"] == "t***@example.com"

    @pytest.mark.asyncio
    async def test_build_reservation_for_user_multi_person(self, mock_dependencies):
        """Test _build_reservation_for_user with multi-person data."""
        workflow = BookingWorkflow(**mock_dependencies)

        mock_user = {"id": 123}
        mock_slot = {"date": "2024-01-15", "time": "10:00"}
        mock_request = {
            "person_count": 2,
            "persons": [
                {"first_name": "John", "last_name": "Doe"},
                {"first_name": "Jane", "last_name": "Doe"},
            ],
        }

        workflow.db.get_pending_appointment_request_for_user = AsyncMock(return_value=mock_request)

        reservation = await workflow._build_reservation_for_user(mock_user, mock_slot)

        assert reservation is not None
        assert reservation["person_count"] == 2
        assert len(reservation["persons"]) == 2

    @pytest.mark.asyncio
    async def test_build_reservation_for_user_single_person_fallback(self, mock_dependencies):
        """Test _build_reservation_for_user falls back to single-person flow."""
        workflow = BookingWorkflow(**mock_dependencies)

        mock_user = {"id": 123}
        mock_slot = {"date": "2024-01-15", "time": "10:00"}
        mock_details = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
        }

        workflow.db.get_pending_appointment_request_for_user = AsyncMock(return_value=None)
        workflow.db.get_personal_details = AsyncMock(return_value=mock_details)

        reservation = await workflow._build_reservation_for_user(mock_user, mock_slot)

        assert reservation is not None
        assert reservation["person_count"] == 1
        assert len(reservation["persons"]) == 1

    @pytest.mark.asyncio
    async def test_build_reservation_for_user_no_data(self, mock_dependencies):
        """Test _build_reservation_for_user returns None when no data available."""
        workflow = BookingWorkflow(**mock_dependencies)

        mock_user = {"id": 123}
        mock_slot = {"date": "2024-01-15", "time": "10:00"}

        workflow.db.get_pending_appointment_request_for_user = AsyncMock(return_value=None)
        workflow.db.get_personal_details = AsyncMock(return_value=None)

        reservation = await workflow._build_reservation_for_user(mock_user, mock_slot)

        assert reservation is None
