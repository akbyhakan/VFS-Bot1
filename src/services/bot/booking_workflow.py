"""Booking workflow orchestration - handles user booking flows."""

import asyncio
import random
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger
from playwright.async_api import Page
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_random_exponential

from ...constants import Delays, Retries
from ...core.exceptions import LoginError, VFSBotError
from ...core.sensitive import SensitiveDict
from ...models.database import Database
from ...repositories import AppointmentRepository, AppointmentRequestRepository, UserRepository
from ...types.user import UserDict
from ...utils.anti_detection.human_simulator import HumanSimulator
from ...utils.error_capture import ErrorCapture
from ...utils.helpers import smart_click
from ...utils.masking import mask_email
from ..alert_service import AlertSeverity
from ..appointment_deduplication import get_deduplication_service
from ..booking import get_selector
from ..notification import NotificationService
from ..session_recovery import SessionRecovery
from ..slot_analyzer import SlotPatternAnalyzer
from .page_state_detector import PageState

if TYPE_CHECKING:
    from ...core.infra.runners import BotConfigDict
    from ..booking import BookingOrchestrator
    from .auth_service import AuthService
    from .error_handler import ErrorHandler
    from .page_state_detector import PageStateDetector
    from .slot_checker import SlotChecker, SlotInfo
    from .waitlist_handler import WaitlistHandler


def _is_recoverable_vfs_error(exception: BaseException) -> bool:
    """Only retry VFSBotError subclasses that are recoverable."""
    return isinstance(exception, VFSBotError) and getattr(exception, "recoverable", False)


class BookingWorkflow:
    """Handles booking workflow operations for users."""

    def __init__(
        self,
        config: "BotConfigDict",
        db: Database,
        notifier: NotificationService,
        auth_service: "AuthService",
        slot_checker: "SlotChecker",
        booking_service: "BookingOrchestrator",
        waitlist_handler: "WaitlistHandler",
        error_handler: "ErrorHandler",
        slot_analyzer: SlotPatternAnalyzer,
        session_recovery: SessionRecovery,
        page_state_detector: "PageStateDetector",
        human_sim: Optional[HumanSimulator] = None,
        error_capture: Optional[ErrorCapture] = None,
        alert_service: Optional[Any] = None,
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
            page_state_detector: Page state detector instance
            human_sim: Optional human simulator for anti-detection
            error_capture: Optional error capture instance for detailed error diagnostics
            alert_service: Optional AlertService for critical notifications
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
        self.page_state_detector = page_state_detector
        self.human_sim = human_sim
        self.error_capture = error_capture or ErrorCapture()
        self.alert_service = alert_service

        # Initialize repositories
        self.appointment_repo = AppointmentRepository(db)
        self.user_repo = UserRepository(db)
        self.appointment_request_repo = AppointmentRequestRepository(db)

    @retry(
        stop=stop_after_attempt(Retries.MAX_PROCESS_USER),
        wait=wait_random_exponential(
            multiplier=Retries.BACKOFF_MULTIPLIER,
            min=Retries.BACKOFF_MIN_SECONDS,
            max=Retries.BACKOFF_MAX_SECONDS,
        ),
        retry=retry_if_exception(_is_recoverable_vfs_error),
        reraise=True,
    )
    async def process_user(self, page: Page, user: UserDict) -> None:
        """
        Process a single user's appointment booking.

        Args:
            page: Playwright page object
            user: User dictionary from database
        """
        masked_email = mask_email(user["email"])
        
        # Check if user has a pending appointment request BEFORE login
        # This is a defensive check - users should already be filtered in run_bot_loop(),
        # but we verify here to prevent login attempts if status changed or if process_user 
        # is called directly from other code paths
        has_pending = await self.appointment_request_repo.get_pending_for_user(user["id"])
        if not has_pending:
            logger.info(
                f"Skipping user {masked_email}: no pending appointment request"
            )
            return
        
        logger.info(f"Processing user: {masked_email}")

        try:
            # Login
            if not await self.auth_service.login(page, user["email"], user["password"]):
                logger.error(f"Login failed for {masked_email}")
                raise LoginError(f"Login failed for {masked_email}")

            # Wait for page to stabilize after login
            state = await self.page_state_detector.wait_for_stable_state(
                page,
                expected_states=frozenset(
                    {
                        PageState.DASHBOARD,
                        PageState.APPOINTMENT_PAGE,
                        PageState.OTP_LOGIN,
                        PageState.SESSION_EXPIRED,
                        PageState.CLOUDFLARE_CHALLENGE,
                    }
                ),
            )

            if state.needs_recovery:
                raise VFSBotError(f"Post-login error: {state.state.name}", recoverable=True)

            # Save checkpoint after successful login
            self.session_recovery.save_checkpoint(
                "logged_in", user["id"], {"masked_email": masked_email}
            )

            # Check for waitlist mode first
            is_waitlist = await self.waitlist_handler.detect_waitlist_mode(page)

            if is_waitlist:
                logger.info(f"Waitlist mode detected for {masked_email}")
                # Handle waitlist flow
                await self.process_waitlist_flow(page, user)
            else:
                # Normal appointment flow
                dedup_service = await get_deduplication_service()
                await self._process_normal_flow(page, user, dedup_service)

        except VFSBotError as e:
            # Capture error
            await self._capture_error_safe(page, e, "process_user", user["id"], masked_email)

            # Log and handle based on recoverability
            if not getattr(e, "recoverable", False):
                logger.error(
                    f"Non-recoverable error for {masked_email}: {e.__class__.__name__}: {e}"
                )

            # Only retry if recoverable
            raise
        except Exception as e:
            # Wrap unexpected exceptions in VFSBotError and re-raise for retry
            logger.error(f"Error processing user {masked_email}: {e}")
            await self._capture_error_safe(page, e, "process_user", user["id"], masked_email)
            raise VFSBotError(f"Error processing user {masked_email}: {e}", recoverable=True) from e

    async def process_waitlist_flow(self, page: Page, user: UserDict) -> None:
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
            await asyncio.sleep(Delays.AFTER_CONTINUE_CLICK)

            # Step 1.5: Fill applicant forms (reuses existing booking flow logic)
            details = await self.user_repo.get_personal_details(user["id"])
            if not details:
                logger.error(f"No personal details found for user {user['id']}")
                return

            # Use empty slot for waitlist since no specific date/time is selected
            reservation = self._build_reservation(user, {"date": "", "time": ""}, details)
            await self.booking_service.fill_all_applicants(page, reservation)
            logger.info(f"Applicant forms filled for waitlist flow ({masked_email})")

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

                # Send alert for waitlist success (INFO severity)
                await self._send_alert_safe(
                    message=f"✅ Waitlist registration successful for {masked_email}",
                    severity=AlertSeverity.INFO,
                    metadata={"user_email": masked_email, "details": waitlist_details},
                )
            else:
                logger.error("Failed to handle waitlist success screen")

                # Send alert for waitlist failure (ERROR severity)
                await self._send_alert_safe(
                    message=f"❌ Failed to handle waitlist success for {masked_email}",
                    severity=AlertSeverity.ERROR,
                    metadata={"user_email": masked_email},
                )

        except Exception as e:
            logger.error(f"Error in waitlist flow: {e}", exc_info=True)
            await self._capture_error_safe(
                page, e, "waitlist_flow", user["id"], mask_email(user["email"])
            )

    async def _send_alert_safe(
        self,
        message: str,
        severity: AlertSeverity = AlertSeverity.ERROR,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send alert through alert service, silently failing on errors.

        Args:
            message: Alert message to send
            severity: Alert severity level
            metadata: Optional metadata dictionary
        """
        if not self.alert_service:
            return
        try:
            await self.alert_service.send_alert(
                message=message,
                severity=severity,
                metadata=metadata or {},
            )
        except Exception as e:
            logger.debug(f"Alert delivery failed: {e}")

    async def _capture_error_safe(
        self, page: Page, error: Exception, step: str, user_id: int, masked_email: str
    ) -> None:
        """
        Safely capture error with screenshot (handles capture failures gracefully).

        Args:
            page: Playwright page object
            error: Exception that occurred
            step: Step name where error occurred
            user_id: User ID
            masked_email: Masked email for logging
        """
        if self.config["bot"].get("screenshot_on_error", True):
            try:
                await self.error_capture.capture(
                    page,
                    error,
                    context={
                        "step": step,
                        "user_id": f"user_{user_id}",
                        "email": masked_email,
                    },
                )
            except Exception as capture_error:
                logger.error(f"Failed to capture error: {capture_error}")

    async def _build_reservation_for_user(
        self, user: UserDict, slot: "SlotInfo"
    ) -> Optional[Dict[str, Any]]:
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
            return self._build_reservation_from_request(appointment_request.to_dict(), slot)

        # Fallback: legacy single-person flow
        details = await self.user_repo.get_personal_details(user["id"])
        if details:
            return self._build_reservation(user, slot, details)

        logger.error(f"No personal details or appointment request found for user {user['id']}")
        return None

    async def _execute_and_confirm_booking(
        self,
        page: Page,
        reservation: Dict[str, Any],
        user: UserDict,
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

        Args:
            page: Playwright page object
            reservation: Reservation dict
            user: User dictionary from database
            centre: Centre name
            slot: SlotInfo with date and time
            dedup_service: Deduplication service instance
            category: Visa category (from AppointmentRequest, fallback to user table)
            subcategory: Visa subcategory (from AppointmentRequest, fallback to user table)
        """
        # Use provided category/subcategory or fallback to user table
        final_category = category or user["category"]
        final_subcategory = subcategory or user["subcategory"]
        
        success = await self.booking_service.run_booking_flow(page, reservation)

        if success:
            # Verify booking confirmation and extract reference
            confirmation = await self.booking_service.verify_booking_confirmation(page)
            if confirmation.get("success"):
                reference = confirmation.get("reference", "UNKNOWN")
                await self.appointment_repo.create(
                    {
                        "user_id": user["id"],
                        "centre": centre,
                        "category": final_category,
                        "subcategory": final_subcategory,
                        "appointment_date": slot["date"],
                        "appointment_time": slot["time"],
                        "reference_number": reference,
                    }
                )
                await self.notifier.notify_booking_success(
                    centre, slot["date"], slot["time"], reference
                )

                # Send alert for booking success (INFO severity)
                await self._send_alert_safe(
                    message=f"✅ Booking successful: {centre} - {slot['date']} {slot['time']} (Ref: {reference})",
                    severity=AlertSeverity.INFO,
                    metadata={
                        "user_id": user["id"],
                        "centre": centre,
                        "date": slot["date"],
                        "time": slot["time"],
                        "reference": reference,
                    },
                )

                # Mark booking in deduplication service
                await dedup_service.mark_booked(user["id"], centre, final_category, slot["date"])

                # Clear checkpoint after successful booking
                self.session_recovery.clear_checkpoint()
                logger.info("Booking completed - checkpoint cleared")
            else:
                logger.error(f"Booking verification failed: {confirmation.get('error')}")

                # Send alert for booking verification failure (ERROR severity)
                await self._send_alert_safe(
                    message=f"❌ Booking verification failed: {confirmation.get('error')}",
                    severity=AlertSeverity.ERROR,
                    metadata={
                        "user_id": user["id"],
                        "centre": centre,
                        "error": confirmation.get("error"),
                    },
                )
        else:
            logger.error("Booking flow failed")

            # Send alert for booking flow failure (ERROR severity)
            await self._send_alert_safe(
                message=f"❌ Booking flow failed for {centre}",
                severity=AlertSeverity.ERROR,
                metadata={
                    "user_id": user["id"],
                    "centre": centre,
                },
            )

    async def _process_normal_flow(self, page: Page, user: UserDict, dedup_service: Any) -> None:
        """
        Process normal appointment flow (slot checking and booking) for ALL pending requests.
        
        This method handles multiple appointment requests across different countries and visa categories.
        Requests are grouped by country_code and processed with randomized order for anti-detection.

        Args:
            page: Playwright page object
            user: User dictionary from database
            dedup_service: Deduplication service instance
        """
        # Step 1: Get ALL pending appointment requests
        appointment_requests = await self.appointment_request_repo.get_all_pending_for_user(user["id"])
        
        if not appointment_requests:
            logger.info(f"No pending appointment requests for user {user['id']}")
            return
        
        logger.info(f"Found {len(appointment_requests)} pending request(s) for user {user['id']}")
        
        # Step 2: Group requests by country_code
        country_groups: Dict[str, List[Any]] = {}
        for request in appointment_requests:
            country_code = request.country_code
            if country_code not in country_groups:
                country_groups[country_code] = []
            country_groups[country_code].append(request)
        
        # Step 3: Shuffle country order for anti-detection
        country_codes = list(country_groups.keys())
        random.shuffle(country_codes)
        
        logger.info(
            f"Processing {len(country_codes)} country group(s) in shuffled order: {country_codes}"
        )
        
        # Step 4: Process each country group
        for country_code in country_codes:
            requests = country_groups[country_code]
            
            # Shuffle requests within each country group for anti-detection
            random.shuffle(requests)
            
            logger.info(
                f"Processing country {country_code}: {len(requests)} request(s) in shuffled order"
            )
            
            # Process each request in the shuffled country group
            for request in requests:
                try:
                    await self._process_single_request(page, user, request, dedup_service)
                except Exception as e:
                    # Log error but continue with next request (error isolation)
                    logger.error(
                        f"Error processing request #{request.id} for user {user['id']}: {e}"
                    )
                    continue

    async def _process_single_request(
        self, page: Page, user: UserDict, appointment_request: Any, dedup_service: Any
    ) -> None:
        """
        Process a single appointment request (slot checking and booking).

        Args:
            page: Playwright page object
            user: User dictionary from database
            appointment_request: AppointmentRequest entity
            dedup_service: Deduplication service instance
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
            
            slot = await self.slot_checker.check_slots(
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
                await self.slot_analyzer.record_slot_found_async(
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
                reservation = self._build_reservation_from_request(
                    appointment_request.to_dict(), slot
                )
                
                if reservation:
                    await self._execute_and_confirm_booking(
                        page, reservation, user, centre, slot, dedup_service,
                        category=category, subcategory=subcategory
                    )

                break

    def _build_reservation_from_request(
        self, request: Dict[str, Any], slot: "SlotInfo"
    ) -> Dict[str, Any]:
        """
        Build reservation from appointment request (multi-person support).

        Args:
            request: Appointment request dict from DB (includes persons list)
            slot: SlotInfo with date and time

        Returns:
            Reservation dict compatible with BookingOrchestrator
        """
        persons = []
        for person_data in request["persons"]:
            person = {
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

        reservation = {
            "person_count": request.get("person_count", len(persons)),
            "preferred_dates": request.get("preferred_dates", [slot["date"]]),
            "persons": persons,
        }

        # Add payment card from config (wrapped in SensitiveDict)
        if "payment" in self.config and "card" in self.config["payment"]:
            reservation["payment_card"] = SensitiveDict(self.config["payment"]["card"])

        return reservation

    def _build_reservation(
        self, user: UserDict, slot: "SlotInfo", details: Dict[str, Any]
    ) -> Dict[str, Any]:
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
        person = {
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
        reservation = {
            "person_count": 1,
            "preferred_dates": [slot["date"]],
            "persons": [person],
        }

        # Add payment card info if available in config (wrapped in SensitiveDict)
        if "payment" in self.config and "card" in self.config["payment"]:
            reservation["payment_card"] = SensitiveDict(self.config["payment"]["card"])

        return reservation
