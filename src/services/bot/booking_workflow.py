"""Booking workflow orchestration - handles user booking flows."""

import asyncio
from typing import TYPE_CHECKING, List, Optional

from loguru import logger
from playwright.async_api import Page
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from ...constants import Delays, Retries
from ...core.exceptions import BannedError, LoginError, VFSBotError
from ...models.database import Database
from ...repositories import (
    AppointmentRepository,
    AppointmentRequestRepository,
    UserRepository,
)
from ...types.user import UserDict
from ...utils.helpers import smart_click
from ...utils.masking import mask_email
from ..alert_service import AlertSeverity, send_alert_safe
from ..appointment_deduplication import get_deduplication_service
from ..booking import get_selector
from ..notification import NotificationService
from .booking_dependencies import BookingDependencies
from .booking_executor import BookingExecutor
from .mission_processor import MissionProcessor
from .page_state_detector import PageState
from .reservation_builder import ReservationBuilder

if TYPE_CHECKING:
    from ...core.infra.runners import BotConfigDict
    from ...repositories.appointment_request_repository import AppointmentRequest
    from ..account_pool import PooledAccount


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
        deps: BookingDependencies,
    ):
        """
        Initialize booking workflow with dependencies.

        Args:
            config: Bot configuration dictionary
            db: Database instance
            notifier: Notification service instance
            deps: BookingDependencies container with all required services
        """
        self.config = config
        self.db = db
        self.notifier = notifier
        self.deps = deps

        # Initialize repositories
        self.appointment_repo = AppointmentRepository(db)
        self.user_repo = UserRepository(db)
        self.appointment_request_repo = AppointmentRequestRepository(db)

        # Initialize extracted service components
        self.reservation_builder = ReservationBuilder(
            config=config,
            user_repo=self.user_repo,
            appointment_request_repo=self.appointment_request_repo,
        )

        self.booking_executor = BookingExecutor(
            db=db,
            notifier=notifier,
            deps=deps,
            appointment_repo=self.appointment_repo,
            appointment_request_repo=self.appointment_request_repo,
        )

        self.mission_processor = MissionProcessor(
            config=config,
            notifier=notifier,
            deps=deps,
            appointment_request_repo=self.appointment_request_repo,
            reservation_builder=self.reservation_builder,
            booking_executor=self.booking_executor,
        )

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
            logger.info(f"Skipping user {masked_email}: no pending appointment request")
            return

        logger.info(f"Processing user: {masked_email}")

        try:
            # Use centralized login and stabilization flow
            success, issue = await self._login_and_stabilize(page, user["email"], user["password"])
            if not success:
                if issue == "login_fail":
                    logger.error(f"Login failed for {masked_email}")
                    raise LoginError(f"Login failed for {masked_email}")
                elif issue == "needs_recovery":
                    logger.error(f"Post-login error for {masked_email}")
                    raise VFSBotError(f"Post-login error for {masked_email}", recoverable=True)
                elif issue == "waitlist":
                    logger.info(f"Waitlist mode detected for {masked_email}")
                    # Handle waitlist flow
                    await self.process_waitlist_flow(page, user)
                    return

            # Save checkpoint after successful login
            self.deps.workflow.session_recovery.save_checkpoint(
                "logged_in", user["id"], {"masked_email": masked_email}
            )

            # Normal appointment flow
            dedup_service = await get_deduplication_service()
            await self.mission_processor.process_normal_flow(page, user, dedup_service)

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

    async def _login_and_stabilize(
        self, page: Page, email: str, password: str
    ) -> tuple[bool, Optional[str]]:
        """
        Login, detect page state, check waitlist.

        This is the single source of truth for login + stabilization flow.
        Used by both process_user and process_mission to avoid code duplication.

        Args:
            page: Playwright page object
            email: User/account email
            password: User/account password

        Returns:
            (success: bool, issue: Optional[str])
            issue can be: 'login_fail', 'needs_recovery', 'waitlist', None (success)
        """
        # Login
        login_success = await self.deps.workflow.auth_service.login(page, email, password)
        if not login_success:
            return (False, "login_fail")

        # Wait for page to stabilize after login
        state = await self.deps.workflow.page_state_detector.wait_for_stable_state(
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
            return (False, "needs_recovery")

        # Check for waitlist mode
        is_waitlist = await self.deps.workflow.waitlist_handler.detect_waitlist_mode(page)
        if is_waitlist:
            return (False, "waitlist")

        return (True, None)

    async def process_mission(
        self,
        page: Page,
        account: "PooledAccount",
        appointment_requests: List["AppointmentRequest"],
    ) -> str:
        """
        Process a mission (country) using a pooled account.

        This method is called by SessionOrchestrator with an account from the pool
        and a list of appointment requests for a specific country/mission.

        Args:
            page: Playwright page object
            account: PooledAccount from the pool
            appointment_requests: List of AppointmentRequest entities for this mission

        Returns:
            Result string: 'success', 'no_slot', 'login_fail', 'error', 'banned'
        """
        masked_email = mask_email(account.email)
        logger.info(
            f"Processing mission with account {account.id} ({masked_email}), "
            f"{len(appointment_requests)} request(s)"
        )

        try:
            # Use centralized login and stabilization flow
            success, issue = await self._login_and_stabilize(page, account.email, account.password)
            if not success:
                if issue == "login_fail":
                    logger.error(f"Login failed for account {masked_email}")
                    return "login_fail"
                elif issue == "needs_recovery":
                    logger.error(f"Post-login error for account {masked_email}")
                    return "error"
                elif issue == "waitlist":
                    logger.info(f"Waitlist mode detected for account {masked_email} - skipping")
                    return "no_slot"

            # Process appointment requests
            dedup_service = await get_deduplication_service()

            # Process each request
            slot_found = False
            for request in appointment_requests:
                try:
                    # Note: process_single_request expects user dict with:
                    # - id: for deduplication checking (using request.id for unique dedup key)
                    # - category/subcategory: fallback if not in request (should be in request)
                    # - email: for logging only
                    # In pool mode, we provide minimal dict since requests have all needed fields
                    minimal_user = {
                        "id": request.id,  # Use appointment request ID for unique dedup key
                        "email": account.email,  # For logging
                        "category": request.visa_category,  # From request
                        "subcategory": request.visa_subcategory,  # From request
                    }
                    result = await self.mission_processor.process_single_request(
                        page,
                        minimal_user,
                        request,
                        dedup_service,
                    )
                    if result:
                        slot_found = True
                        # Mark request as completed
                        await self.appointment_request_repo.update_status(
                            request.id,
                            "completed",
                        )
                except Exception as e:
                    logger.error(f"Error processing request {request.id}: {e}")
                    continue

            if slot_found:
                return "success"
            else:
                return "no_slot"

        except BannedError:
            logger.error(f"Account {masked_email} has been banned")
            return "banned"
        except VFSBotError as e:
            logger.error(f"VFS error for account {masked_email}: {e}")
            # Fallback string check for backward compatibility
            if "banned" in str(e).lower():
                return "banned"
            return "error"
        except Exception as e:
            logger.error(f"Unexpected error for account {masked_email}: {e}", exc_info=True)
            return "error"

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
            if not await self.deps.workflow.waitlist_handler.join_waitlist(page):
                logger.error("Failed to join waitlist")
                return

            # Click Continue button to proceed to next step
            await smart_click(page, get_selector("continue_button"), self.deps.infra.human_sim)
            await asyncio.sleep(Delays.AFTER_CONTINUE_CLICK)

            # Step 1.5: Fill applicant forms (reuses existing booking flow logic)
            details = await self.user_repo.get_personal_details(user["id"])
            if not details:
                logger.error(f"No personal details found for user {user['id']}")
                return

            # Use empty slot for waitlist since no specific date/time is selected
            reservation = self.reservation_builder.build_reservation(
                user, {"date": "", "time": ""}, details
            )
            await self.deps.workflow.booking_service.fill_all_applicants(page, reservation)
            logger.info(f"Applicant forms filled for waitlist flow ({masked_email})")

            # Step 2: Accept all checkboxes on Review and Pay screen
            if not await self.deps.workflow.waitlist_handler.accept_review_checkboxes(page):
                logger.error("Failed to accept review checkboxes")
                return

            # Step 3: Click Confirm button
            if not await self.deps.workflow.waitlist_handler.click_confirm_button(page):
                logger.error("Failed to click confirm button")
                return

            # Step 4: Handle success screen
            waitlist_details = await self.deps.workflow.waitlist_handler.handle_waitlist_success(
                page, user["email"]
            )

            if waitlist_details:
                # Send notification with screenshot
                screenshot_path: Optional[str] = waitlist_details.get("screenshot_path")
                await self.notifier.notify_waitlist_success(waitlist_details, screenshot_path)
                logger.info(f"Waitlist registration successful for {masked_email}")

                # Send alert for waitlist success (INFO severity)
                await send_alert_safe(
                    self.deps.workflow.alert_service,
                    message=f"✅ Waitlist registration successful for {masked_email}",
                    severity=AlertSeverity.INFO,
                    metadata={"user_email": masked_email, "details": waitlist_details},
                )
            else:
                logger.error("Failed to handle waitlist success screen")

                # Send alert for waitlist failure (ERROR severity)
                await send_alert_safe(
                    self.deps.workflow.alert_service,
                    message=f"❌ Failed to handle waitlist success for {masked_email}",
                    severity=AlertSeverity.ERROR,
                    metadata={"user_email": masked_email},
                )

        except Exception as e:
            logger.error(f"Error in waitlist flow: {e}", exc_info=True)
            await self._capture_error_safe(
                page, e, "waitlist_flow", user["id"], mask_email(user["email"])
            )

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
                await self.deps.infra.error_capture.capture(
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
