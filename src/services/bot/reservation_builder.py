"""Reservation builder for appointment bookings."""

from typing import TYPE_CHECKING, Any, Dict, Optional

from loguru import logger

from ...core.sensitive import SensitiveDict
from .types import PersonDict, ReservationDict

if TYPE_CHECKING:
    from ...core.infra.runners import BotConfigDict
    from ...repositories.appointment_request_repository import AppointmentRequestRepository
    from ...repositories.payment_repository import PaymentRepository
    from ...types.user import VFSAccountDict
    from .slot_checker import SlotInfo


class ReservationBuilder:
    """Builds reservation data structures for appointment bookings."""

    def __init__(
        self,
        config: "BotConfigDict",
        appointment_request_repo: "AppointmentRequestRepository",
        payment_repo: Optional["PaymentRepository"] = None,
    ):
        """
        Initialize reservation builder.

        Args:
            config: Bot configuration dictionary
            appointment_request_repo: Appointment request repository instance
            payment_repo: Optional PaymentRepository for loading card from DB
        """
        self.config = config
        self.appointment_request_repo = appointment_request_repo
        self.payment_repo = payment_repo

    async def _get_payment_card(self) -> Optional[SensitiveDict]:
        """
        Get payment card data — DB first, config fallback.

        Returns:
            SensitiveDict with card data or None if not available
        """
        if self.payment_repo is not None:
            try:
                card_entity = await self.payment_repo.get()
                if card_entity is not None:
                    card_data: Dict[str, Any] = {}
                    if card_entity.card_number:
                        card_data["card_number"] = card_entity.card_number
                    if card_entity.expiry_month:
                        card_data["expiry_month"] = card_entity.expiry_month
                    if card_entity.expiry_year:
                        card_data["expiry_year"] = card_entity.expiry_year
                    if card_entity.cvv:
                        card_data["cvv"] = card_entity.cvv
                    if card_data:
                        return SensitiveDict(card_data)
            except Exception as e:
                logger.warning(f"Failed to load payment card from DB, falling back to config: {e}")

        # Fallback to config
        if "payment" in self.config and "card" in self.config["payment"]:
            return SensitiveDict(self.config["payment"]["card"])

        return None

    async def build_reservation_for_user(
        self, user: "VFSAccountDict", slot: "SlotInfo"
    ) -> Optional[ReservationDict]:
        """
        Build reservation for user using appointment request data.

        Args:
            user: User/account dictionary
            slot: SlotInfo with date and time

        Returns:
            Reservation dict or None if no appointment request available
        """
        appointment_request = await self.appointment_request_repo.get_pending_for_user(user["id"])
        if appointment_request:
            return await self.build_reservation_from_request(appointment_request.to_dict(), slot)

        logger.error(f"No appointment request found for user {user['id']}")
        return None

    async def build_reservation_from_request(
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

        # Add payment card (DB first, config fallback)
        payment_card = await self._get_payment_card()
        if payment_card is not None:
            reservation["payment_card"] = payment_card

        return reservation

    async def build_reservation(
        self, user: "VFSAccountDict", slot: "SlotInfo", details: Dict[str, Any]
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

        # Add payment card (DB first, config fallback)
        payment_card = await self._get_payment_card()
        if payment_card is not None:
            reservation["payment_card"] = payment_card

        return reservation
