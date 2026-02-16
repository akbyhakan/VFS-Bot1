"""Reservation builder for appointment bookings."""

from typing import TYPE_CHECKING, Any, Dict, Optional

from loguru import logger

from ...core.sensitive import SensitiveDict
from .types import PersonDict, ReservationDict

if TYPE_CHECKING:
    from ...core.infra.runners import BotConfigDict
    from ...repositories.appointment_request_repository import AppointmentRequestRepository
    from ...repositories.user_repository import UserRepository
    from ...types.user import UserDict
    from .slot_checker import SlotInfo


class ReservationBuilder:
    """Builds reservation data structures for appointment bookings."""

    def __init__(
        self,
        config: "BotConfigDict",
        user_repo: "UserRepository",
        appointment_request_repo: "AppointmentRequestRepository",
    ):
        """
        Initialize reservation builder.

        Args:
            config: Bot configuration dictionary
            user_repo: User repository instance
            appointment_request_repo: Appointment request repository instance
        """
        self.config = config
        self.user_repo = user_repo
        self.appointment_request_repo = appointment_request_repo

    async def build_reservation_for_user(
        self, user: "UserDict", slot: "SlotInfo"
    ) -> Optional[ReservationDict]:
        """
        Build reservation for user using appropriate strategy.

        Tries get_pending_appointment_request_for_user first (multi-person support),
        falls back to get_personal_details (legacy single-person).

        Args:
            user: User dictionary from database
            slot: SlotInfo with date and time

        Returns:
            Reservation dict or None if no data available
        """
        # Try multi-person flow first
        appointment_request = await self.appointment_request_repo.get_pending_for_user(user["id"])
        if appointment_request:
            return self.build_reservation_from_request(appointment_request.to_dict(), slot)

        # Fallback: legacy single-person flow
        details = await self.user_repo.get_personal_details(user["id"])
        if details:
            return self.build_reservation(user, slot, details)

        logger.error(f"No personal details or appointment request found for user {user['id']}")
        return None

    def build_reservation_from_request(
        self, request: Dict[str, Any], slot: "SlotInfo"
    ) -> ReservationDict:
        """
        Build reservation from appointment request (multi-person support).

        Args:
            request: Appointment request dict from DB (includes persons list)
            slot: SlotInfo with date and time

        Returns:
            Reservation dict compatible with BookingOrchestrator
        """
        persons: list[PersonDict] = []
        for person_data in request["persons"]:
            person: PersonDict = {
                "first_name": person_data.get("first_name", ""),
                "last_name": person_data.get("last_name", ""),
                "gender": person_data.get("gender", "male"),
                "birth_date": person_data.get("birth_date", ""),
                "passport_number": person_data.get("passport_number", ""),
                "passport_expiry_date": person_data.get("passport_expiry_date", ""),
                "phone_code": person_data.get("phone_code", "90"),
                "phone_number": person_data.get("phone_number", ""),
                "email": person_data.get("email", ""),
                "is_child_with_parent": person_data.get("is_child_with_parent", False),
            }
            persons.append(person)

        reservation: ReservationDict = {
            "person_count": request.get("person_count", len(persons)),
            "preferred_dates": request.get("preferred_dates", [slot["date"]]),
            "persons": persons,
        }

        # Add payment card from config (wrapped in SensitiveDict)
        if "payment" in self.config and "card" in self.config["payment"]:
            reservation["payment_card"] = SensitiveDict(self.config["payment"]["card"])

        return reservation

    def build_reservation(
        self, user: "UserDict", slot: "SlotInfo", details: Dict[str, Any]
    ) -> ReservationDict:
        """
        Build reservation data structure from user, slot, and personal details.

        Args:
            user: User dictionary from database
            slot: SlotInfo with date and time fields
            details: Personal details dictionary from database

        Returns:
            Reservation dictionary compatible with BookingOrchestrator
        """
        # Build person data structure
        person: PersonDict = {
            "first_name": details.get("first_name", ""),
            "last_name": details.get("last_name", ""),
            "gender": details.get("gender", "male"),
            "birth_date": details.get("date_of_birth", ""),
            "passport_number": details.get("passport_number", ""),
            "passport_expiry_date": details.get("passport_expiry", ""),
            "phone_code": details.get("mobile_code", "90"),
            "phone_number": details.get("mobile_number", ""),
            "email": details.get("email", ""),
            "is_child_with_parent": False,
        }

        # Build reservation structure
        # NOTE: Currently handles single person bookings only.
        # For multi-person support, person_count should be len(persons)
        # and persons list should contain all applicants' details.
        reservation: ReservationDict = {
            "person_count": 1,
            "preferred_dates": [slot["date"]],
            "persons": [person],
        }

        # Add payment card info if available in config (wrapped in SensitiveDict)
        if "payment" in self.config and "card" in self.config["payment"]:
            reservation["payment_card"] = SensitiveDict(self.config["payment"]["card"])

        return reservation
