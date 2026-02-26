"""Booking execution service for appointment bookings."""

from typing import TYPE_CHECKING, Any, Optional

from loguru import logger
from playwright.async_api import Page

from ...utils.masking import mask_email
from .types import ReservationDict

if TYPE_CHECKING:
    from ...repositories import AppointmentRepository, AppointmentRequestRepository
    from ...types.user import VFSAccountDict
    from ..notification.notification import NotificationService
    from .booking_dependencies import BookingDependencies
    from .slot_checker import SlotInfo


class BookingExecutor:
    """Executes booking flows and confirms appointments."""

    def __init__(
        self,
        notifier: "NotificationService",
        deps: "BookingDependencies",
        appointment_repo: "AppointmentRepository",
        appointment_request_repo: "AppointmentRequestRepository",
    ):
        """
        Initialize booking executor.

        Args:
            notifier: Notification service instance
            deps: BookingDependencies container with all required services
            appointment_repo: Appointment repository instance
            appointment_request_repo: Appointment request repository instance
        """
        self.notifier = notifier
        self.deps = deps
        self.appointment_repo = appointment_repo
        self.appointment_request_repo = appointment_request_repo

    async def execute_and_confirm_booking(
        self,
        page: Page,
        reservation: ReservationDict,
        user: "VFSAccountDict",
        centre: str,
        slot: "SlotInfo",
        dedup_service: Any,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
    ) -> None:
        """
        Execute booking flow and confirm booking (common confirmation pipeline).

        Handles: run_booking_flow → verify_confirmation → add_appointment →
        notify_booking_success → mark_booked → clear_checkpoint

        This method propagates exceptions to the caller for handling.

        Args:
            page: Playwright page object
            reservation: Reservation dict
            user: User dictionary from database
            centre: Centre name
            slot: SlotInfo with date and time
            dedup_service: Deduplication service instance
            category: Visa category (from AppointmentRequest, fallback to user table)
            subcategory: Visa subcategory (from AppointmentRequest, fallback to user table)

        Raises:
            Exception: Any exception from booking flow is propagated to caller
        """
        # Use provided category/subcategory or fallback to user dict
        final_category = category or user.get("category", "")
        final_subcategory = subcategory or user.get("subcategory", "")

        success = await self.deps.workflow.booking_service.run_booking_flow(page, dict(reservation))

        if success:
            # Verify booking confirmation and extract reference number
            # BookingValidator.verify_booking_confirmation reads the actual
            # reference from the page (e.g. ABC123456) using multiple selectors.
            # It is accessed via BookingOrchestrator.validator attribute.
            reference = "CONFIRMED"
            try:
                confirmation = (
                    await self.deps.workflow.booking_service.validator.verify_booking_confirmation(
                        page
                    )
                )
                if confirmation.get("success"):
                    reference = confirmation.get("reference") or "CONFIRMED"
                    logger.info(f"Booking confirmation verified, reference: {reference}")
                else:
                    logger.warning(
                        f"Booking confirmation verification returned unsuccessful: "
                        f"{confirmation.get('error', 'unknown')}. "
                        f"Using fallback reference: {reference}"
                    )
            except Exception as verify_error:
                logger.warning(
                    f"Could not verify booking confirmation: {verify_error}. "
                    f"Using fallback reference: {reference}"
                )

            await self.appointment_repo.create(
                {
                    "user_id": user["id"],
                    "centre": centre,
                    "category": final_category,
                    "subcategory": final_subcategory,
                    "appointment_date": slot["date"],
                    "appointment_time": slot.get("time", "UNKNOWN"),
                    "reference_number": reference,
                }
            )

            # Check for duplicate before notifying/marking
            is_duplicate = await dedup_service.is_duplicate_booking(
                user_id=user["id"],
                centre=centre,
                category=final_category,
                subcategory=final_subcategory,
                appointment_date=slot["date"],
            )

            if not is_duplicate:
                logger.success(
                    f"✅ Booking confirmed for {mask_email(user['email'])}: "
                    f"{slot['date']} at {centre} (Ref: {reference})"
                )
                await self.notifier.notify_booking_success(
                    centre,
                    slot["date"],
                    slot.get("time", "UNKNOWN"),
                    reference,
                )
            else:
                logger.warning(
                    f"Duplicate booking detected for {mask_email(user['email'])}, "
                    f"skipping notification"
                )

            # Mark appointment request as booked if exists
            appointment_request = await self.appointment_request_repo.get_pending_for_user(
                user["id"]
            )
            if appointment_request:
                await self.appointment_request_repo.update_status(appointment_request.id, "booked", booked_date=slot["date"])

            # Clear recovery checkpoint after successful booking
            self.deps.workflow.session_recovery.clear_checkpoint()

    async def process_single_request(
        self,
        page: Page,
        user: "VFSAccountDict",
        centre: str,
        category: str,
        subcategory: str,
        slot: "SlotInfo",
        reservation: ReservationDict,
        dedup_service: Any,
    ) -> bool:
        """
        Process a single appointment booking request.

        This method returns a boolean indicating success/failure and propagates
        exceptions to the caller for error handling.

        Args:
            page: Playwright page object
            user: User dictionary
            centre: Centre name
            category: Visa category
            subcategory: Visa subcategory
            slot: Available slot info
            reservation: Reservation data
            dedup_service: Deduplication service

        Returns:
            True if booking succeeded, False otherwise

        Raises:
            Exception: Any exception from booking flow is propagated to caller
        """
        masked_email = mask_email(user["email"])
        logger.info(
            f"Processing booking for {masked_email}: "
            f"{slot['date']} at {centre} ({category}/{subcategory})"
        )

        try:
            await self.execute_and_confirm_booking(
                page=page,
                reservation=reservation,
                user=user,
                centre=centre,
                slot=slot,
                dedup_service=dedup_service,
                category=category,
                subcategory=subcategory,
            )
            return True

        except Exception as e:
            logger.error(
                f"Booking failed for {masked_email} at {centre} "
                f"({category}/{subcategory}): {str(e)}"
            )
            # Propagate exception to caller for proper error handling
            raise
