"""VFS Bot orchestrator - coordinates all bot components."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from playwright.async_api import Page
from tenacity import retry, stop_after_attempt, wait_random_exponential

from .browser_manager import BrowserManager
from .auth_service import AuthService
from .slot_checker import SlotChecker
from .circuit_breaker_service import CircuitBreakerService
from .error_handler import ErrorHandler
from ..captcha_solver import CaptchaSolver
from ..centre_fetcher import CentreFetcher
from ..notification import NotificationService
from ...constants import Intervals, Retries, RateLimits
from ...models.database import Database
from ...utils.anti_detection.cloudflare_handler import CloudflareHandler
from ...utils.anti_detection.human_simulator import HumanSimulator
from ...utils.security.header_manager import HeaderManager
from ...utils.security.proxy_manager import ProxyManager
from ...utils.security.session_manager import SessionManager
from ...utils.security.rate_limiter import get_rate_limiter
from ...utils.error_capture import ErrorCapture
from ...utils.helpers import smart_fill, smart_click, wait_for_selector_smart
from ...utils.masking import mask_email

logger = logging.getLogger(__name__)


class VFSBot:
    """VFS appointment booking bot orchestrator using modular components."""

    def __init__(
        self,
        config: Dict[str, Any],
        db: Database,
        notifier: NotificationService,
        shutdown_event: Optional[asyncio.Event] = None,
        captcha_solver: Optional[CaptchaSolver] = None,
        centre_fetcher: Optional[CentreFetcher] = None,
    ):
        """
        Initialize VFS bot with dependency injection.

        Args:
            config: Bot configuration dictionary
            db: Database instance
            notifier: Notification service instance
            shutdown_event: Optional event to signal graceful shutdown
            captcha_solver: Optional CaptchaSolver instance (created if not provided)
            centre_fetcher: Optional CentreFetcher instance (created if not provided)
        """
        self.config = config
        self.db = db
        self.notifier = notifier
        self.running = False
        self.health_checker = None  # Will be set by main.py if enabled
        self.shutdown_event = shutdown_event or asyncio.Event()

        # Concurrent processing semaphore
        self.user_semaphore = asyncio.Semaphore(RateLimits.CONCURRENT_USERS)

        # Initialize rate limiter
        self.rate_limiter = get_rate_limiter()

        # Initialize error capture
        self.error_capture = ErrorCapture()

        # Initialize OTP service
        from ..otp_webhook import get_otp_service

        self.otp_service = get_otp_service()

        # Initialize components with dependency injection
        self.captcha_solver = captcha_solver or CaptchaSolver(
            api_key=config["captcha"].get("api_key", ""),
            manual_timeout=config["captcha"].get("manual_timeout", 120),
        )

        self.centre_fetcher = centre_fetcher or CentreFetcher(
            base_url=config["vfs"]["base_url"],
            country=config["vfs"]["country"],
            mission=config["vfs"]["mission"],
            language=config["vfs"].get("language", "tr"),
        )

        # Initialize anti-detection components
        anti_detection_config = config.get("anti_detection", {})
        self.anti_detection_enabled = anti_detection_config.get("enabled", True)

        if self.anti_detection_enabled:
            # Human behavior simulator
            self.human_sim: Optional[HumanSimulator] = HumanSimulator(
                config.get("human_behavior", {})
            )

            # Header manager
            self.header_manager: Optional[HeaderManager] = HeaderManager()

            # Session manager
            session_config = config.get("session", {})
            self.session_manager: Optional[SessionManager] = SessionManager(
                session_file=session_config.get("save_file", "data/session.json"),
                token_refresh_buffer=session_config.get("token_refresh_buffer", 5),
            )

            # Cloudflare handler
            self.cloudflare_handler: Optional[CloudflareHandler] = CloudflareHandler(
                config.get("cloudflare", {})
            )

            # Proxy manager
            self.proxy_manager: Optional[ProxyManager] = ProxyManager(config.get("proxy", {}))

            logger.info("Anti-detection features initialized")
        else:
            self.human_sim = None
            self.header_manager = None
            self.session_manager = None
            self.cloudflare_handler = None
            self.proxy_manager = None
            logger.info("Anti-detection features disabled")

        # Initialize appointment booking service (PART 2)
        from ..appointment_booking_service import AppointmentBookingService

        self.booking_service = AppointmentBookingService(
            config, self.captcha_solver, self.human_sim
        )

        # Initialize modular components
        self.browser_manager = BrowserManager(config, self.header_manager, self.proxy_manager)
        self.circuit_breaker = CircuitBreakerService()
        self.error_handler = ErrorHandler()

        self.auth_service = AuthService(
            config,
            self.captcha_solver,
            self.human_sim,
            self.cloudflare_handler,
            self.error_capture,
            self.otp_service,
        )

        self.slot_checker = SlotChecker(
            config,
            self.rate_limiter,
            self.human_sim,
            self.cloudflare_handler,
            self.error_capture,
        )

        logger.info("VFSBot initialized with modular components")

    async def __aenter__(self) -> "VFSBot":
        """
        Async context manager entry.

        Returns:
            Self instance
        """
        await self.browser_manager.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """
        Async context manager exit with cleanup.

        Args:
            exc_type: Exception type if any
            exc_val: Exception value if any
            exc_tb: Exception traceback if any

        Returns:
            False to propagate exceptions
        """
        # Save checkpoint if there was an error
        if exc_type is not None:
            stats = await self.circuit_breaker.get_stats()
            await self.error_handler.save_checkpoint(
                {
                    "running": self.running,
                    "circuit_breaker_open": stats["is_open"],
                    "consecutive_errors": stats["consecutive_errors"],
                    "total_errors_count": stats["total_errors_in_window"],
                }
            )

        await self.cleanup()
        return False

    async def cleanup(self) -> None:
        """Clean up browser resources."""
        await self.browser_manager.close()
        logger.info("Bot cleanup completed")

    async def start(self) -> None:
        """Start the bot."""
        self.running = True
        logger.info("Starting VFS-Bot...")
        await self.notifier.notify_bot_started()

        # Start browser manager
        await self.browser_manager.start()

        try:
            # Start health checker if configured
            if self.health_checker and self.browser_manager.browser:
                asyncio.create_task(
                    self.health_checker.run_continuous(self.browser_manager.browser)
                )
                logger.info("Selector health monitoring started")

            await self.run_bot_loop()
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the bot."""
        self.running = False
        await self.browser_manager.close()
        await self.notifier.notify_bot_stopped()
        logger.info("VFS-Bot stopped")

    async def run_bot_loop(self) -> None:
        """Main bot loop to check for slots with circuit breaker and parallel processing."""
        while self.running and not self.shutdown_event.is_set():
            try:
                # Check for shutdown request
                if self.shutdown_event.is_set():
                    logger.info("Shutdown requested, stopping bot loop...")
                    break

                # Check circuit breaker
                if not await self.circuit_breaker.is_available():
                    wait_time = await self.circuit_breaker.get_wait_time()
                    stats = await self.circuit_breaker.get_stats()
                    logger.warning(
                        f"Circuit breaker OPEN - waiting {wait_time}s before retry "
                        f"(consecutive errors: {stats['consecutive_errors']})"
                    )
                    await asyncio.sleep(wait_time)
                    # Don't unconditionally reset - let the next successful iteration close it
                    # Circuit will be closed by record_success() if the next attempt succeeds
                    logger.info(
                        "Circuit breaker wait time elapsed - attempting next iteration "
                        "(circuit will close on success)"
                    )
                    continue

                # Get active users with decrypted passwords
                users = await self.db.get_active_users_with_decrypted_passwords()
                logger.info(
                    f"Processing {len(users)} active users "
                    f"(max {RateLimits.CONCURRENT_USERS} concurrent)"
                )

                if not users:
                    logger.info("No active users to process")
                    check_interval = self.config["bot"].get(
                        "check_interval", Intervals.CHECK_SLOTS_DEFAULT
                    )
                    await asyncio.sleep(check_interval)
                    continue

                # Process users in parallel with semaphore limit
                tasks = [self._process_user_with_semaphore(user) for user in users]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Check results and update circuit breaker
                errors_in_batch = sum(1 for r in results if isinstance(r, Exception))
                if errors_in_batch > 0:
                    logger.warning(f"{errors_in_batch}/{len(users)} users failed processing")
                    await self.circuit_breaker.record_failure()
                else:
                    # Successful batch - reset consecutive errors
                    await self.circuit_breaker.record_success()

                # Wait before next check
                check_interval = self.config["bot"].get(
                    "check_interval", Intervals.CHECK_SLOTS_DEFAULT
                )
                logger.info(f"Waiting {check_interval}s before next check...")
                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error in bot loop: {e}", exc_info=True)
                await self.notifier.notify_error("Bot Loop Error", str(e))
                await self.circuit_breaker.record_failure()

                # If circuit breaker open, wait longer
                if not await self.circuit_breaker.is_available():
                    wait_time = await self.circuit_breaker.get_wait_time()
                    await asyncio.sleep(wait_time)
                else:
                    await asyncio.sleep(Intervals.ERROR_RECOVERY)

    async def _process_user_with_semaphore(self, user: Dict[str, Any]) -> None:
        """
        Process user with semaphore for concurrency control.

        Args:
            user: User dictionary from database
        """
        async with self.user_semaphore:
            await self.process_user(user)

    @retry(
        stop=stop_after_attempt(Retries.MAX_PROCESS_USER_ATTEMPTS),
        wait=wait_random_exponential(
            multiplier=Retries.EXPONENTIAL_MULTIPLIER,
            min=Retries.EXPONENTIAL_MIN,
            max=Retries.EXPONENTIAL_MAX,
        ),
    )
    async def process_user(self, user: Dict[str, Any]) -> None:
        """
        Process a single user's appointment booking.

        Args:
            user: User dictionary from database
        """
        masked_email = mask_email(user["email"])
        logger.info(f"Processing user: {masked_email}")

        page = await self.browser_manager.new_page()

        try:
            # Login
            if not await self.auth_service.login(page, user["email"], user["password"]):
                logger.error(f"Login failed for {masked_email}")
                return

            # Check slots
            centres = user["centre"].split(",")
            for centre in centres:
                centre = centre.strip()
                slot = await self.slot_checker.check_slots(
                    page, centre, user["category"], user["subcategory"]
                )

                if slot:
                    await self.notifier.notify_slot_found(centre, slot["date"], slot["time"])

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
                    break
        except Exception as e:
            logger.error(f"Error processing user {masked_email}: {e}")
            if self.config["bot"].get("screenshot_on_error", True):
                try:
                    await self.error_handler.take_screenshot(
                        page, f"error_{user['id']}_{datetime.now().timestamp()}"
                    )
                except Exception as screenshot_error:
                    logger.error(f"Failed to take screenshot: {screenshot_error}")
        finally:
            # Always close the page to prevent resource leak
            try:
                await page.close()
            except Exception as close_error:
                logger.error(f"Failed to close page: {close_error}")

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
            from ...constants import Timeouts

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
            from ...constants import Timeouts

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

    async def book_appointment_for_request(self, page: Page, reservation: Dict[str, Any]) -> bool:
        """
        Book appointment using reservation data from API.

        Args:
            page: Playwright page
            reservation: Reservation data from database

        Returns:
            True if booking successful
        """
        return await self.booking_service.run_booking_flow(page, reservation)
