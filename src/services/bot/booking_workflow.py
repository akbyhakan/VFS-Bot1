"""Booking workflow orchestration - handles user booking flows."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

from playwright.async_api import Page
from tenacity import retry, stop_after_attempt, wait_random_exponential

from ...constants import Retries, Timeouts
from ...models.database import Database
from ...utils.anti_detection.human_simulator import HumanSimulator
from ...utils.helpers import smart_click, smart_fill, wait_for_selector_smart
from ...utils.masking import mask_email
from ..appointment_booking_service import get_selector
from ..notification import NotificationService
from ..session_recovery import SessionRecovery
from ..slot_analyzer import SlotPatternAnalyzer

if TYPE_CHECKING:
    from ..appointment_booking_service import AppointmentBookingService
    from .auth_service import AuthService
    from .error_handler import ErrorHandler
    from .slot_checker import SlotChecker
    from .waitlist_handler import WaitlistHandler

logger = logging.getLogger(__name__)


class BookingWorkflow:
    """Handles booking workflow operations for users."""

    def __init__(
        self,
        config: Dict[str, Any],
        db: Database,
        notifier: NotificationService,
        auth_service: "AuthService",
        slot_checker: "SlotChecker",
        booking_service: "AppointmentBookingService",
        waitlist_handler: "WaitlistHandler",
        error_handler: "ErrorHandler",
        slot_analyzer: SlotPatternAnalyzer,
        session_recovery: SessionRecovery,
        human_sim: Optional[HumanSimulator] = None,
    ):
        """
        Initialize booking workflow with dependencies.

        Args:
            config: Bot configuration dictionary
            db: Database instance
            notifier: Notification service instance
            auth_service: Authentication service instance
            slot_checker: Slot checker instance
            booking_service: Appointment booking service instance
            waitlist_handler: Waitlist handler instance
            error_handler: Error handler instance
            slot_analyzer: Slot pattern analyzer instance
            session_recovery: Session recovery instance
            human_sim: Optional human simulator for anti-detection
        """
        self.config = config
        self.db = db
        self.notifier = notifier
        self.auth_service = auth_service
        self.slot_checker = slot_checker
        self.booking_service = booking_service
        self.waitlist_handler = waitlist_handler
        self.error_handler = error_handler
        self.slot_analyzer = slot_analyzer
        self.session_recovery = session_recovery
        self.human_sim = human_sim

    @retry(
        stop=stop_after_attempt(Retries.MAX_PROCESS_USER_ATTEMPTS),
        wait=wait_random_exponential(
            multiplier=Retries.EXPONENTIAL_MULTIPLIER,
            min=Retries.EXPONENTIAL_MIN,
            max=Retries.EXPONENTIAL_MAX,
        ),
    )
    async def process_user(self, page: Page, user: Dict[str, Any]) -> None:
        """
        Process a single user's appointment booking.

        Args:
            page: Playwright page object
            user: User dictionary from database
        """
        masked_email = mask_email(user["email"])
        logger.info(f"Processing user: {masked_email}")

        try:
            # Login
            if not await self.auth_service.login(page, user["email"], user["password"]):
                logger.error(f"Login failed for {masked_email}")
                return

            # Save checkpoint after successful login
            self.session_recovery.save_checkpoint(
                "logged_in", user["id"], {"email": user["email"], "masked_email": masked_email}
            )

            # Check for waitlist mode first
            is_waitlist = await self.waitlist_handler.detect_waitlist_mode(page)

            if is_waitlist:
                logger.info(f"Waitlist mode detected for {masked_email}")
                # Handle waitlist flow
                await self.process_waitlist_flow(page, user)
            else:
                # Normal appointment flow
                # Check slots
                centres = user["centre"].split(",")
                for centre in centres:
                    centre = centre.strip()
                    slot = await self.slot_checker.check_slots(
                        page, centre, user["category"], user["subcategory"]
                    )

                    if slot:
                        await self.notifier.notify_slot_found(centre, slot["date"], slot["time"])

                        # Record slot pattern for analysis
                        self.slot_analyzer.record_slot_found(
                            country=user.get("country", "unknown"),
                            centre=centre,
                            category=user["category"],
                            date=slot["date"],
                            time=slot["time"],
                        )

                        # Get personal details
                        details = await self.db.get_personal_details(user["id"])
                        if details:
                            # Fill details and book
                            if await self.fill_personal_details(page, details):
                                reference = await self.book_appointment(
                                    page, slot["date"], slot["time"]
                                )
                                if reference:
                                    await self.db.add_appointment(
                                        user["id"],
                                        centre,
                                        user["category"],
                                        user["subcategory"],
                                        slot["date"],
                                        slot["time"],
                                        reference,
                                    )
                                    await self.notifier.notify_booking_success(
                                        centre, slot["date"], slot["time"], reference
                                    )

                                    # Clear checkpoint after successful booking
                                    self.session_recovery.clear_checkpoint()
                                    logger.info("Booking completed - checkpoint cleared")
                        break
        except Exception as e:
            logger.error(f"Error processing user {masked_email}: {e}")
            if self.config["bot"].get("screenshot_on_error", True):
                try:
                    await self.error_handler.take_screenshot(
                        page, f"error_{user['id']}_{datetime.now(timezone.utc).timestamp()}"
                    )
                except Exception as screenshot_error:
                    logger.error(f"Failed to take screenshot: {screenshot_error}")

    async def process_waitlist_flow(self, page: Page, user: Dict[str, Any]) -> None:
        """
        Process waitlist flow for a user.

        Args:
            page: Playwright page object
            user: User dictionary from database
        """
        try:
            masked_email = mask_email(user["email"])
            logger.info(f"Starting waitlist flow for {masked_email}")

            # Step 1: Join waitlist (check waitlist checkbox on Application Details)
            if not await self.waitlist_handler.join_waitlist(page):
                logger.error("Failed to join waitlist")
                return

            # Click Continue button to proceed to next step
            await smart_click(page, get_selector("continue_button"), self.human_sim)
            await asyncio.sleep(2)

            # TODO: Personal details form filling step would go here if needed
            # The waitlist flow may or may not require filling forms depending on:
            # - Whether forms are pre-filled from previous interactions
            # - Whether the user has saved applicant data
            # Currently assuming forms are already filled or handled by VFS system

            # Step 2: Accept all checkboxes on Review and Pay screen
            if not await self.waitlist_handler.accept_review_checkboxes(page):
                logger.error("Failed to accept review checkboxes")
                return

            # Step 3: Click Confirm button
            if not await self.waitlist_handler.click_confirm_button(page):
                logger.error("Failed to click confirm button")
                return

            # Step 4: Handle success screen
            waitlist_details = await self.waitlist_handler.handle_waitlist_success(
                page, user["email"]
            )

            if waitlist_details:
                # Send notification with screenshot
                screenshot_path: Optional[str] = waitlist_details.get("screenshot_path")
                await self.notifier.notify_waitlist_success(waitlist_details, screenshot_path)
                logger.info(f"Waitlist registration successful for {masked_email}")
            else:
                logger.error("Failed to handle waitlist success screen")

        except Exception as e:
            logger.error(f"Error in waitlist flow: {e}", exc_info=True)

    async def fill_personal_details(self, page: Page, details: Dict[str, Any]) -> bool:
        """
        Fill personal details form.

        Args:
            page: Playwright page object
            details: Personal details dictionary

        Returns:
            True if successful
        """
        try:
            # Wait for form to load
            await wait_for_selector_smart(page, "input#first_name", timeout=Timeouts.SELECTOR_WAIT)

            # Fill form fields with human simulation
            await smart_fill(
                page, "input#first_name", details.get("first_name", ""), self.human_sim
            )
            await smart_fill(page, "input#last_name", details.get("last_name", ""), self.human_sim)
            await smart_fill(
                page, "input#passport_number", details.get("passport_number", ""), self.human_sim
            )
            await smart_fill(page, "input#email", details.get("email", ""), self.human_sim)

            if details.get("mobile_number"):
                await smart_fill(
                    page, "input#mobile", details.get("mobile_number", ""), self.human_sim
                )

            if details.get("date_of_birth"):
                await smart_fill(
                    page, "input#dob", details.get("date_of_birth", ""), self.human_sim
                )

            logger.info("Personal details filled successfully")
            return True

        except Exception as e:
            logger.error(f"Error filling personal details: {e}")
            return False

    async def book_appointment(self, page: Page, date: str, time: str) -> Optional[str]:
        """
        Complete appointment booking.

        Args:
            page: Playwright page object
            date: Appointment date
            time: Appointment time

        Returns:
            Reference number if successful
        """
        try:
            # Click continue/book button with human simulation
            await smart_click(page, "button#book-appointment", self.human_sim)
            await page.wait_for_load_state("networkidle", timeout=Timeouts.NETWORK_IDLE)

            # Wait for confirmation page
            await wait_for_selector_smart(page, ".confirmation", timeout=Timeouts.SELECTOR_WAIT)

            # Extract reference number
            reference_text = await page.locator(".reference-number").text_content()
            reference: str = reference_text.strip() if reference_text else ""

            logger.info(f"Appointment booked! Reference: {reference}")
            return reference if reference else None

        except Exception as e:
            logger.error(f"Error booking appointment: {e}")
            return None
