"""Tests for skipping users without pending appointment requests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.bot.booking_workflow import BookingWorkflow


class TestSkipUsersWithoutPendingRequest:
    """Test that users without pending requests are skipped."""

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
    async def test_process_user_skips_when_no_pending_request(self, mock_dependencies):
        """Test that process_user returns early when user has no pending request."""
        workflow = BookingWorkflow(**mock_dependencies)

        mock_page = AsyncMock()
        mock_user = {
            "id": 123,
            "email": "test@example.com",
            "password": "test_password",
            "country": "fra",
            "active": True,
        }

        # Mock no pending request
        workflow.appointment_request_repo.get_pending_for_user = AsyncMock(return_value=None)

        # Call process_user
        await workflow.process_user(mock_page, mock_user)

        # Verify login was NOT called
        workflow.auth_service.login.assert_not_called()

        # Verify slot checker was NOT called
        workflow.slot_checker.check_slots.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_user_continues_when_pending_request_exists(self, mock_dependencies):
        """Test that process_user continues when user has pending request."""
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

        # Mock pending request exists
        mock_pending_request = MagicMock()
        mock_pending_request.person_count = 1
        mock_pending_request.preferred_dates = []
        mock_pending_request.centres = ["Paris"]
        mock_pending_request.visa_category = "visa"
        mock_pending_request.visa_subcategory = "tourism"
        mock_pending_request.country_code = "fra"
        workflow.appointment_request_repo.get_pending_for_user = AsyncMock(
            return_value=mock_pending_request
        )

        # Mock successful login and no waitlist
        workflow.auth_service.login = AsyncMock(return_value=True)
        workflow.page_state_detector.wait_for_stable_state = AsyncMock(
            return_value=MagicMock(
                needs_recovery=False,
                is_on_appointment_page=True,
                state=MagicMock(name="DASHBOARD"),
            )
        )
        workflow.waitlist_handler.detect_waitlist_mode = AsyncMock(return_value=False)
        workflow.slot_checker.check_slots = AsyncMock(return_value=None)

        # Call process_user
        await workflow.process_user(mock_page, mock_user)

        # Verify login WAS called
        workflow.auth_service.login.assert_called_once()

        # Verify slot checker WAS called
        workflow.slot_checker.check_slots.assert_called()

    @pytest.mark.asyncio
    async def test_process_user_logs_skip_message(self, mock_dependencies):
        """Test that process_user logs a message when skipping user."""
        workflow = BookingWorkflow(**mock_dependencies)

        mock_page = AsyncMock()
        mock_user = {
            "id": 123,
            "email": "test@example.com",
            "password": "test_password",
            "country": "fra",
            "active": True,
        }

        # Mock no pending request
        workflow.appointment_request_repo.get_pending_for_user = AsyncMock(return_value=None)

        # Capture logs using loguru's context
        with patch("src.services.bot.booking_workflow.logger") as mock_logger:
            await workflow.process_user(mock_page, mock_user)

            # Verify info log was called with skip message
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "Skipping user" in call_args
            assert "no pending appointment request" in call_args


class TestBulkQueryMethod:
    """Test the bulk query method for efficiency."""

    @pytest.mark.asyncio
    async def test_get_user_ids_with_pending_requests(self):
        """Test get_user_ids_with_pending_requests returns correct user IDs."""
        from src.repositories.appointment_request_repository import AppointmentRequestRepository

        # Mock database connection
        mock_db = MagicMock()
        mock_conn = AsyncMock()
        mock_db.get_connection.return_value.__aenter__.return_value = mock_conn

        # Mock fetch result
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"id": 1},
                {"id": 2},
                {"id": 5},
            ]
        )

        repo = AppointmentRequestRepository(mock_db)
        result = await repo.get_user_ids_with_pending_requests()

        # Verify the result is a set of user IDs
        assert result == {1, 2, 5}
        assert isinstance(result, set)

    @pytest.mark.asyncio
    async def test_get_user_ids_with_pending_requests_empty(self):
        """Test get_user_ids_with_pending_requests returns empty set when no pending requests."""
        from src.repositories.appointment_request_repository import AppointmentRequestRepository

        # Mock database connection
        mock_db = MagicMock()
        mock_conn = AsyncMock()
        mock_db.get_connection.return_value.__aenter__.return_value = mock_conn

        # Mock fetch result - no pending requests
        mock_conn.fetch = AsyncMock(return_value=[])

        repo = AppointmentRequestRepository(mock_db)
        result = await repo.get_user_ids_with_pending_requests()

        # Verify the result is an empty set
        assert result == set()
        assert isinstance(result, set)
