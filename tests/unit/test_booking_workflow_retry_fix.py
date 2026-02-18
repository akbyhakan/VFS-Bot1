"""Tests for BookingWorkflow retry mechanism fixes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tenacity import RetryError

from src.core.exceptions import LoginError, VFSBotError
from src.services.bot.booking_dependencies import (
    BookingDependencies,
    InfraServices,
    WorkflowServices,
)
from src.services.bot.booking_workflow import BookingWorkflow

# Add parent directory to path for imports


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
        page_state_detector = MagicMock()

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
            "page_state_detector": page_state_detector,
        }

    @pytest.fixture(autouse=True)
    def mock_repositories(self):
        """Automatically patch repository classes for all tests."""
        with (
            patch("src.services.bot.booking_workflow.AppointmentRepository"),
            patch("src.services.bot.booking_workflow.UserRepository"),
            patch("src.services.bot.booking_workflow.AppointmentRequestRepository"),
        ):
            yield

    @pytest.mark.asyncio
    async def test_capture_error_safe(self, mock_dependencies):
        """Test _capture_error_safe helper method."""
        mock_error_capture = MagicMock()
        mock_error_capture.capture = AsyncMock()

        workflow_services = WorkflowServices(
            auth_service=mock_dependencies["auth_service"],
            slot_checker=mock_dependencies["slot_checker"],
            booking_service=mock_dependencies["booking_service"],
            waitlist_handler=mock_dependencies["waitlist_handler"],
            error_handler=mock_dependencies["error_handler"],
            page_state_detector=mock_dependencies["page_state_detector"],
            slot_analyzer=mock_dependencies["slot_analyzer"],
            session_recovery=mock_dependencies["session_recovery"],
            alert_service=None,
        )

        infra_services = InfraServices(
            browser_manager=None,
            header_manager=None,
            proxy_manager=None,
            human_sim=None,
            error_capture=mock_error_capture,
        )

        deps = BookingDependencies(
            workflow=workflow_services,
            infra=infra_services,
        )

        workflow = BookingWorkflow(
            config=mock_dependencies["config"],
            db=mock_dependencies["db"],
            notifier=mock_dependencies["notifier"],
            deps=deps,
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
        workflow_services = WorkflowServices(
            auth_service=mock_dependencies["auth_service"],
            slot_checker=mock_dependencies["slot_checker"],
            booking_service=mock_dependencies["booking_service"],
            waitlist_handler=mock_dependencies["waitlist_handler"],
            error_handler=mock_dependencies["error_handler"],
            page_state_detector=mock_dependencies["page_state_detector"],
            slot_analyzer=mock_dependencies["slot_analyzer"],
            session_recovery=mock_dependencies["session_recovery"],
            alert_service=None,
        )

        infra_services = InfraServices(
            browser_manager=None,
            header_manager=None,
            proxy_manager=None,
            human_sim=None,
            error_capture=None,
        )

        deps = BookingDependencies(
            workflow=workflow_services,
            infra=infra_services,
        )

        workflow = BookingWorkflow(
            config=mock_dependencies["config"],
            db=mock_dependencies["db"],
            notifier=mock_dependencies["notifier"],
            deps=deps,
        )

        mock_user = {"id": 123}
        mock_slot = {"date": "2024-01-15", "time": "10:00"}
        mock_request = {
            "person_count": 2,
            "persons": [
                {"first_name": "John", "last_name": "Doe"},
                {"first_name": "Jane", "last_name": "Doe"},
            ],
        }

        # Create a mock AppointmentRequest with to_dict() method
        mock_appointment_request = MagicMock()
        mock_appointment_request.to_dict.return_value = mock_request
        workflow.appointment_request_repo.get_pending_for_user = AsyncMock(
            return_value=mock_appointment_request
        )

        reservation = await workflow.reservation_builder.build_reservation_for_user(
            mock_user, mock_slot
        )

        assert reservation is not None
        assert reservation["person_count"] == 2
        assert len(reservation["persons"]) == 2

    @pytest.mark.asyncio
    async def test_build_reservation_for_user_single_person_fallback(self, mock_dependencies):
        """Test _build_reservation_for_user falls back to single-person flow."""
        workflow_services = WorkflowServices(
            auth_service=mock_dependencies["auth_service"],
            slot_checker=mock_dependencies["slot_checker"],
            booking_service=mock_dependencies["booking_service"],
            waitlist_handler=mock_dependencies["waitlist_handler"],
            error_handler=mock_dependencies["error_handler"],
            page_state_detector=mock_dependencies["page_state_detector"],
            slot_analyzer=mock_dependencies["slot_analyzer"],
            session_recovery=mock_dependencies["session_recovery"],
            alert_service=None,
        )

        infra_services = InfraServices(
            browser_manager=None,
            header_manager=None,
            proxy_manager=None,
            human_sim=None,
            error_capture=None,
        )

        deps = BookingDependencies(
            workflow=workflow_services,
            infra=infra_services,
        )

        workflow = BookingWorkflow(
            config=mock_dependencies["config"],
            db=mock_dependencies["db"],
            notifier=mock_dependencies["notifier"],
            deps=deps,
        )

        mock_user = {"id": 123}
        mock_slot = {"date": "2024-01-15", "time": "10:00"}
        mock_details = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
        }

        workflow.appointment_request_repo.get_pending_for_user = AsyncMock(return_value=None)
        workflow.user_repo.get_personal_details = AsyncMock(return_value=mock_details)

        reservation = await workflow.reservation_builder.build_reservation_for_user(
            mock_user, mock_slot
        )

        assert reservation is not None
        assert reservation["person_count"] == 1
        assert len(reservation["persons"]) == 1

    @pytest.mark.asyncio
    async def test_build_reservation_for_user_no_data(self, mock_dependencies):
        """Test _build_reservation_for_user returns None when no data available."""
        workflow_services = WorkflowServices(
            auth_service=mock_dependencies["auth_service"],
            slot_checker=mock_dependencies["slot_checker"],
            booking_service=mock_dependencies["booking_service"],
            waitlist_handler=mock_dependencies["waitlist_handler"],
            error_handler=mock_dependencies["error_handler"],
            page_state_detector=mock_dependencies["page_state_detector"],
            slot_analyzer=mock_dependencies["slot_analyzer"],
            session_recovery=mock_dependencies["session_recovery"],
            alert_service=None,
        )

        infra_services = InfraServices(
            browser_manager=None,
            header_manager=None,
            proxy_manager=None,
            human_sim=None,
            error_capture=None,
        )

        deps = BookingDependencies(
            workflow=workflow_services,
            infra=infra_services,
        )

        workflow = BookingWorkflow(
            config=mock_dependencies["config"],
            db=mock_dependencies["db"],
            notifier=mock_dependencies["notifier"],
            deps=deps,
        )

        mock_user = {"id": 123}
        mock_slot = {"date": "2024-01-15", "time": "10:00"}

        workflow.appointment_request_repo.get_pending_for_user = AsyncMock(return_value=None)
        workflow.user_repo.get_personal_details = AsyncMock(return_value=None)

        reservation = await workflow.reservation_builder.build_reservation_for_user(
            mock_user, mock_slot
        )

        assert reservation is None
