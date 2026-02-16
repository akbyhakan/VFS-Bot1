"""Tests for BookingWorkflow retry mechanism fixes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tenacity import RetryError

from src.core.exceptions import LoginError, VFSBotError
from src.services.bot.booking_workflow import BookingWorkflow
from src.services.bot.booking_dependencies import BookingDependencies, WorkflowServices, InfraServices

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
        page_state_detector = MagicMock()
        page_state_detector.wait_for_stable_state = AsyncMock(return_value=MagicMock(
            needs_recovery=False,
            is_on_appointment_page=True,
            state=MagicMock(name="DASHBOARD"),
        ))
        page_state_detector.detect = AsyncMock(return_value=MagicMock(
            needs_recovery=False,
            is_on_appointment_page=True,
            confidence=0.85,
            state=MagicMock(name="APPOINTMENT_PAGE"),
        ))

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
        with patch("src.services.bot.booking_workflow.AppointmentRepository") as mock_appt_repo, \
             patch("src.services.bot.booking_workflow.UserRepository") as mock_user_repo, \
             patch("src.services.bot.booking_workflow.AppointmentRequestRepository") as mock_req_repo:
            # Setup default async return values for repository methods
            # Create a mock pending request to allow tests to proceed past the pending check
            mock_pending_request = MagicMock()
            mock_pending_request.person_count = 1
            mock_pending_request.preferred_dates = []
            
            mock_req_instance = MagicMock()
            mock_req_instance.get_pending_for_user = AsyncMock(return_value=mock_pending_request)
            mock_req_repo.return_value = mock_req_instance
            
            yield

    @pytest.mark.asyncio
    async def test_login_failure_raises_exception(self, mock_dependencies):
        """Test that login failure raises LoginError instead of returning."""
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
        with patch("src.services.bot.booking_workflow.AppointmentRepository"), \
             patch("src.services.bot.booking_workflow.UserRepository"), \
             patch("src.services.bot.booking_workflow.AppointmentRequestRepository"):
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
    async def test_build_reservation_for_user_multi_person(
        self, mock_dependencies
    ):
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

        reservation = await workflow.reservation_builder.build_reservation_for_user(mock_user, mock_slot)

        assert reservation is not None
        assert reservation["person_count"] == 2
        assert len(reservation["persons"]) == 2

    @pytest.mark.asyncio
    async def test_build_reservation_for_user_single_person_fallback(
        self, mock_dependencies
    ):
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

        reservation = await workflow.reservation_builder.build_reservation_for_user(mock_user, mock_slot)

        assert reservation is not None
        assert reservation["person_count"] == 1
        assert len(reservation["persons"]) == 1

    @pytest.mark.asyncio
    async def test_build_reservation_for_user_no_data(
        self, mock_dependencies
    ):
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

        reservation = await workflow.reservation_builder.build_reservation_for_user(mock_user, mock_slot)

        assert reservation is None
