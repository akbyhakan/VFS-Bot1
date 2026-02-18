"""Tests for BookingWorkflow multi-person booking support."""

from unittest.mock import MagicMock

import pytest

from src.services.bot.booking_dependencies import (
    BookingDependencies,
    InfraServices,
    WorkflowServices,
)
from src.services.bot.booking_workflow import BookingWorkflow

# Add parent directory to path for imports


class TestBookingWorkflowMultiPerson:
    """Test multi-person booking functionality in BookingWorkflow."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for BookingWorkflow."""
        config = {
            "bot": {
                "screenshot_on_error": True,
                "max_retries": 3,
            },
            "payment": {
                "card": {
                    "number": "1234567812345678",
                    "expiry": "12/25",
                    "cvv": "123",
                }
            },
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

    def test_build_reservation_from_request_single_person(self, mock_dependencies):
        """Test building reservation from appointment request with single person."""
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

        appointment_request = {
            "id": 1,
            "person_count": 1,
            "preferred_dates": ["15/02/2026"],
            "persons": [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "gender": "male",
                    "birth_date": "15/01/1990",
                    "passport_number": "U12345678",
                    "passport_expiry_date": "01/01/2030",
                    "phone_code": "90",
                    "phone_number": "5551234567",
                    "email": "john@example.com",
                    "is_child_with_parent": False,
                }
            ],
        }

        slot = {"date": "15/02/2026", "time": "10:00"}

        reservation = workflow.reservation_builder.build_reservation_from_request(
            appointment_request, slot
        )

        assert reservation["person_count"] == 1
        assert len(reservation["persons"]) == 1
        assert reservation["persons"][0]["first_name"] == "John"
        assert reservation["persons"][0]["email"] == "john@example.com"
        assert "payment_card" in reservation
        # Card details are now wrapped in SensitiveDict
        assert reservation["payment_card"]["number"] == "1234567812345678"

    def test_build_reservation_from_request_multi_person(self, mock_dependencies):
        """Test building reservation from appointment request with multiple persons."""
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

        appointment_request = {
            "id": 2,
            "person_count": 3,
            "preferred_dates": ["15/02/2026", "16/02/2026"],
            "persons": [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "gender": "male",
                    "birth_date": "15/01/1990",
                    "passport_number": "U12345678",
                    "passport_expiry_date": "01/01/2030",
                    "phone_code": "90",
                    "phone_number": "5551234567",
                    "email": "john@example.com",
                    "is_child_with_parent": False,
                },
                {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "gender": "female",
                    "birth_date": "20/05/1992",
                    "passport_number": "U87654321",
                    "passport_expiry_date": "01/01/2031",
                    "phone_code": "90",
                    "phone_number": "5559876543",
                    "email": "jane@example.com",
                    "is_child_with_parent": False,
                },
                {
                    "first_name": "Jimmy",
                    "last_name": "Doe",
                    "gender": "male",
                    "birth_date": "10/03/2015",
                    "passport_number": "U11111111",
                    "passport_expiry_date": "01/01/2025",
                    "phone_code": "90",
                    "phone_number": "5551111111",
                    "email": "jimmy@example.com",
                    "is_child_with_parent": True,
                },
            ],
        }

        slot = {"date": "15/02/2026", "time": "14:00"}

        reservation = workflow.reservation_builder.build_reservation_from_request(
            appointment_request, slot
        )

        assert reservation["person_count"] == 3
        assert len(reservation["persons"]) == 3
        assert reservation["persons"][0]["first_name"] == "John"
        assert reservation["persons"][1]["first_name"] == "Jane"
        assert reservation["persons"][2]["first_name"] == "Jimmy"
        assert reservation["persons"][2]["is_child_with_parent"] is True
        assert reservation["preferred_dates"] == ["15/02/2026", "16/02/2026"]

    def test_build_reservation_from_request_no_payment_card(self, mock_dependencies):
        """Test building reservation when no payment card is configured."""
        # Remove payment card from config
        mock_dependencies["config"] = {"bot": {"screenshot_on_error": True}}

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

        appointment_request = {
            "id": 1,
            "person_count": 1,
            "preferred_dates": ["15/02/2026"],
            "persons": [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "gender": "male",
                    "birth_date": "15/01/1990",
                    "passport_number": "U12345678",
                    "passport_expiry_date": "01/01/2030",
                    "phone_code": "90",
                    "phone_number": "5551234567",
                    "email": "john@example.com",
                    "is_child_with_parent": False,
                }
            ],
        }

        slot = {"date": "15/02/2026", "time": "10:00"}

        reservation = workflow.reservation_builder.build_reservation_from_request(
            appointment_request, slot
        )

        assert reservation["person_count"] == 1
        assert "payment_card" not in reservation

    def test_build_reservation_legacy_single_person(self, mock_dependencies):
        """Test legacy _build_reservation method still works (backward compatibility)."""
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

        user = {"id": 1, "email": "test@example.com"}

        details = {
            "first_name": "Test",
            "last_name": "User",
            "gender": "female",
            "date_of_birth": "01/01/1985",
            "passport_number": "P12345678",
            "passport_expiry": "01/01/2028",
            "mobile_code": "44",
            "mobile_number": "7700900123",
            "email": "test@example.com",
        }

        slot = {"date": "20/03/2026", "time": "09:00"}

        reservation = workflow._build_reservation(user, slot, details)

        # Should always be single person
        assert reservation["person_count"] == 1
        assert len(reservation["persons"]) == 1
        assert reservation["persons"][0]["first_name"] == "Test"
        assert reservation["persons"][0]["phone_code"] == "44"
        assert reservation["preferred_dates"] == ["20/03/2026"]

    def test_build_reservation_from_request_field_mapping(self, mock_dependencies):
        """Test that field mapping is correct for appointment_persons."""
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

        # Note: appointment_persons uses different field names than personal_details
        appointment_request = {
            "id": 1,
            "person_count": 1,
            "preferred_dates": ["15/02/2026"],
            "persons": [
                {
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "gender": "female",
                    "birth_date": "25/12/1988",  # Not date_of_birth
                    "passport_number": "A99999999",
                    "passport_expiry_date": "25/12/2028",  # Not passport_expiry
                    "phone_code": "1",
                    "phone_number": "5551234567",
                    "email": "alice@example.com",
                    "is_child_with_parent": False,
                }
            ],
        }

        slot = {"date": "15/02/2026", "time": "11:30"}

        reservation = workflow.reservation_builder.build_reservation_from_request(
            appointment_request, slot
        )

        # Verify field mapping
        person = reservation["persons"][0]
        assert person["birth_date"] == "25/12/1988"
        assert person["passport_expiry_date"] == "25/12/2028"
        assert person["phone_code"] == "1"
        assert person["is_child_with_parent"] is False

    def test_payment_card_is_sensitive_dict(self, mock_dependencies):
        """Test that payment card is wrapped in SensitiveDict."""
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

        appointment_request = {
            "id": 1,
            "person_count": 1,
            "preferred_dates": ["15/02/2026"],
            "persons": [
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "gender": "male",
                    "birth_date": "15/01/1990",
                    "passport_number": "U12345678",
                    "passport_expiry_date": "01/01/2030",
                    "phone_code": "90",
                    "phone_number": "5551234567",
                    "email": "john@example.com",
                    "is_child_with_parent": False,
                }
            ],
        }

        slot = {"date": "15/02/2026", "time": "10:00"}

        reservation = workflow.reservation_builder.build_reservation_from_request(
            appointment_request, slot
        )

        # Verify repr and str don't contain actual card number
        repr_str = repr(reservation["payment_card"])
        str_str = str(reservation["payment_card"])

        assert "1234567812345678" not in repr_str
        assert "1234567812345678" not in str_str
        assert "MASKED" in repr_str
        assert "MASKED" in str_str

        # But direct access still works
        assert reservation["payment_card"]["number"] == "1234567812345678"
        assert reservation["payment_card"]["cvv"] == "123"
        assert reservation["payment_card"]["expiry"] == "12/25"
