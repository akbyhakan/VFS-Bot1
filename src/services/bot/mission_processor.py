"""Mission processor for handling multi-country appointment requests."""

from typing import TYPE_CHECKING, Any

from loguru import logger
from playwright.async_api import Page

if TYPE_CHECKING:
    from ...core.infra.runners import BotConfigDict
    from ...repositories import AppointmentRequestRepository
    from ...types.user import UserDict
    from ..notification import NotificationService
    from .booking_dependencies import BookingDependencies
    from .booking_executor import BookingExecutor
    from .reservation_builder import ReservationBuilder


class MissionProcessor:
    """Processes mission (country) appointment requests."""

    def __init__(
        self,
        config: "BotConfigDict",
        notifier: "NotificationService",
        deps: "BookingDependencies",
        appointment_request_repo: "AppointmentRequestRepository",
        reservation_builder: "ReservationBuilder",
        booking_executor: "BookingExecutor",
    ):
        """
        Initialize mission processor.

        Args:
            config: Bot configuration dictionary
            notifier: Notification service instance
            deps: BookingDependencies container with all required services
            appointment_request_repo: Appointment request repository instance
            reservation_builder: ReservationBuilder instance for building reservations
            booking_executor: BookingExecutor instance for executing bookings
        """
        self.config = config
        self.notifier = notifier
        self.deps = deps
        self.appointment_request_repo = appointment_request_repo
        self.reservation_builder = reservation_builder
        self.booking_executor = booking_executor



    async def process_single_request(
        self, page: Page, user: "UserDict", appointment_request: Any, dedup_service: Any
    ) -> bool:
        """
        Process a single appointment request (slot checking and booking).

        This method returns a boolean indicating success/failure and propagates
        exceptions to the caller for error handling.

        Args:
            page: Playwright page object
            user: User dictionary from database
            appointment_request: AppointmentRequest entity
            dedup_service: Deduplication service instance

        Returns:
            True if slot was found and booking executed, False otherwise

        Raises:
            Exception: Any exception from booking flow is propagated to caller
        """
        # Extract criteria from AppointmentRequest
        person_count = appointment_request.person_count or len(appointment_request.persons or [])
        preferred_dates = appointment_request.preferred_dates or []
        centres = appointment_request.centres
        category = appointment_request.visa_category or user["category"]
        subcategory = appointment_request.visa_subcategory or user["subcategory"]

        logger.info(
            f"Processing AppointmentRequest #{appointment_request.id}: "
            f"country={appointment_request.country_code}, centres={centres}, "
            f"preferred_dates={preferred_dates}, person_count={person_count}, "
            f"category={category}/{subcategory}"
        )

        # Check centres sequentially (same page, SPA-safe)
        for centre in centres:
            centre = centre.strip()

            slot = await self.deps.workflow.slot_checker.check_slots(
                page,
                centre,
                category,
                subcategory,
                required_capacity=person_count,
                preferred_dates=preferred_dates,
            )

            if slot:
                await self.notifier.notify_slot_found(centre, slot["date"], slot["time"])
                logger.info(
                    f"Slot found for {person_count} person(s): "
                    f"{centre} - {slot['date']} {slot['time']}"
                )

                # Record slot pattern with country from AppointmentRequest
                await self.deps.workflow.slot_analyzer.record_slot_found_async(
                    country=appointment_request.country_code,
                    centre=centre,
                    category=category,
                    date=slot["date"],
                    time=slot["time"],
                )

                # Check for duplicate booking attempt
                is_duplicate = await dedup_service.is_duplicate(
                    user["id"], centre, category, slot["date"]
                )

                if is_duplicate:
                    logger.warning(
                        f"Skipping duplicate booking for user {user['id']}: "
                        f"{centre}/{category}/{slot['date']}"
                    )
                    continue

                # Build reservation directly from AppointmentRequest
                reservation = self.reservation_builder.build_reservation_from_request(
                    appointment_request.to_dict(), slot
                )

                if reservation:
                    await self.booking_executor.execute_and_confirm_booking(
                        page,
                        reservation,
                        user,
                        centre,
                        slot,
                        dedup_service,
                        category=category,
                        subcategory=subcategory,
                    )
                    return True

                logger.warning(
                    f"Failed to build reservation for centre {centre}, trying next centre"
                )
                continue

        return False
