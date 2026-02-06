"""Isolated worker for country-based reservation checking."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from playwright.async_api import Page

from ...appointment_booking_service import AppointmentBookingService
from ...captcha_solver import CaptchaSolver
from ...otp_webhook import get_otp_service
from ...session_recovery import SessionRecovery
from ...slot_analyzer import SlotPatternAnalyzer
from ....utils.anti_detection.cloudflare_handler import CloudflareHandler
from ....utils.anti_detection.human_simulator import HumanSimulator
from ....utils.error_capture import ErrorCapture
from ....utils.security.rate_limiter import get_rate_limiter
from ..auth_service import AuthService
from ..booking_workflow import BookingWorkflow
from ..browser_manager import BrowserManager
from ..error_handler import ErrorHandler
from ..slot_checker import SlotChecker
from ..waitlist_handler import WaitlistHandler
from .resource_pool import ResourcePool

logger = logging.getLogger(__name__)


class ReservationWorker:
    """
    Independent worker for a single reservation (country).

    Each worker:
    - Has its own browser instance
    - Rotates account and proxy on each cycle
    - Completely cleans browser at the end of each cycle
    """

    def __init__(
        self,
        reservation_id: int,
        country: str,
        config: Dict[str, Any],
        account_pool: ResourcePool,
        proxy_pool: ResourcePool,
        db: Any,
        notifier: Any,
    ):
        """
        Initialize reservation worker.

        Args:
            reservation_id: Database reservation ID
            country: Country/mission code (fra, nld, bel, etc.)
            config: Bot configuration
            account_pool: Shared account pool for round-robin
            proxy_pool: Shared proxy pool for round-robin
            db: Database instance
            notifier: Notification service
        """
        self.reservation_id = reservation_id
        self.country = country
        self.config = config
        self.account_pool = account_pool
        self.proxy_pool = proxy_pool
        self.db = db
        self.notifier = notifier

        self.running = False
        self.browser_manager: Optional[BrowserManager] = None
        self.current_account: Optional[Dict[str, Any]] = None
        self.current_proxy: Optional[Dict[str, Any]] = None
        self.check_count = 0
        self.last_check_time: Optional[datetime] = None

        logger.info(f"ReservationWorker initialized for {country} (ID: {reservation_id})")

    async def start(self) -> None:
        """Start the worker loop."""
        self.running = True
        logger.info(f"[{self.country}] Worker starting...")

        try:
            await self.run_check_loop()
        except asyncio.CancelledError:
            logger.info(f"[{self.country}] Worker cancelled")
        except Exception as e:
            logger.error(f"[{self.country}] Worker error: {e}", exc_info=True)
        finally:
            await self.cleanup()

    async def stop(self) -> None:
        """Stop the worker."""
        self.running = False
        logger.info(f"[{self.country}] Worker stopping...")

    async def cleanup(self) -> None:
        """Clean up all resources."""
        if self.browser_manager:
            try:
                await self.browser_manager.close()
            except Exception as e:
                logger.error(f"[{self.country}] Browser cleanup error: {e}")
            self.browser_manager = None

        logger.info(f"[{self.country}] Worker cleanup completed")

    async def run_check_loop(self) -> None:
        """Main check loop with full browser isolation per iteration."""
        while self.running:
            try:
                # 1. Get next account in country-specific sequence
                self.current_account = await self.account_pool.get_next(self.country)

                # 2. Get next proxy in country-specific sequence
                self.current_proxy = await self.proxy_pool.get_next(self.country)

                # Handle None check for current_account
                if self.current_account is None:
                    account_email = "unknown"
                else:
                    account_email = self.current_account.get("email", "unknown")
                proxy_server = (
                    self.current_proxy.get("server", "no-proxy")
                    if self.current_proxy
                    else "no-proxy"
                )

                logger.info(
                    f"[{self.country}] Cycle {self.check_count + 1} starting - "
                    f"Account: {self._mask_email(account_email)}, "
                    f"Proxy: {proxy_server}"
                )

                # 3. Start NEW browser (CLEAN, with this proxy)
                await self._start_fresh_browser()

                try:
                    # 4. Create new page
                    if self.browser_manager is None:
                        raise RuntimeError("Browser manager not initialized")
                    page = await self.browser_manager.new_page()

                    # 5. Process check
                    result = await self._process_check(page)

                    if result.get("slot_found"):
                        logger.info(f"[{self.country}] 🎉 SLOT FOUND!")
                        await self.notifier.notify_slot_found(
                            self.country, result.get("date"), result.get("time")
                        )
                        # Booking process can be done here

                    self.check_count += 1
                    self.last_check_time = datetime.now(timezone.utc)

                except Exception as e:
                    logger.error(f"[{self.country}] Check error: {e}")

                finally:
                    # 6. FULL CLEANUP - Close browser completely
                    await self._close_browser()
                    logger.debug(f"[{self.country}] Browser cleaned")

                # 7. Move to next cycle
                check_interval = self.config["bot"].get("check_interval", 30)
                logger.info(f"[{self.country}] Next check in {check_interval}s...")
                await asyncio.sleep(check_interval)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"[{self.country}] Loop error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Error recovery wait

    async def _start_fresh_browser(self) -> None:
        """Start a completely fresh browser instance with current proxy."""
        # Close previous browser if exists
        await self._close_browser()

        # Create proxy config
        proxy_config = None
        if self.current_proxy:
            proxy_config = {
                "enabled": True,
                "server": self.current_proxy.get("server"),
                "username": self.current_proxy.get("username"),
                "password": self.current_proxy.get("password"),
            }

        # Create new config (with proxy)
        browser_config = dict(self.config)
        if proxy_config:
            browser_config["proxy"] = proxy_config

        # Start new browser
        self.browser_manager = BrowserManager(browser_config)
        await self.browser_manager.start()

        logger.debug(f"[{self.country}] Fresh browser started")

    async def _close_browser(self) -> None:
        """Close browser and clear all session data."""
        if self.browser_manager:
            try:
                await self.browser_manager.close()
            except Exception as e:
                logger.warning(f"[{self.country}] Browser close warning: {e}")
            finally:
                self.browser_manager = None

    def _create_booking_workflow(self) -> BookingWorkflow:
        """Create a BookingWorkflow with fresh dependencies for this cycle."""
        # Create captcha solver
        captcha_config = self.config.get("captcha", {})
        captcha_solver = CaptchaSolver(
            api_key=captcha_config.get("api_key", ""),
            manual_timeout=captcha_config.get("manual_timeout", 120),
        )

        # Get rate limiter and OTP service (singletons)
        rate_limiter = get_rate_limiter()
        otp_service = get_otp_service()

        # Create anti-detection components if enabled
        anti_detection_config = self.config.get("anti_detection", {})
        if anti_detection_config.get("enabled", True):
            human_sim = HumanSimulator(self.config.get("human_behavior", {}))
            cloudflare_handler = CloudflareHandler(self.config.get("cloudflare", {}))
        else:
            human_sim = None
            cloudflare_handler = None

        # Create error capture
        error_capture = ErrorCapture()

        # Create service instances
        auth_service = AuthService(
            self.config,
            captcha_solver,
            human_sim,
            cloudflare_handler,
            error_capture,
            otp_service,
        )

        slot_checker = SlotChecker(
            self.config,
            rate_limiter,
            human_sim,
            cloudflare_handler,
            error_capture,
        )

        booking_service = AppointmentBookingService(
            self.config,
            captcha_solver,
            human_sim,
        )

        waitlist_handler = WaitlistHandler(self.config, human_sim)

        error_handler = ErrorHandler()

        slot_analyzer = SlotPatternAnalyzer()

        session_recovery = SessionRecovery()

        # Create and return BookingWorkflow
        return BookingWorkflow(
            config=self.config,
            db=self.db,
            notifier=self.notifier,
            auth_service=auth_service,
            slot_checker=slot_checker,
            booking_service=booking_service,
            waitlist_handler=waitlist_handler,
            error_handler=error_handler,
            slot_analyzer=slot_analyzer,
            session_recovery=session_recovery,
            human_sim=human_sim,
        )

    async def _process_check(self, page: Page) -> Dict[str, Any]:
        """
        Process a single check iteration.

        Delegates to BookingWorkflow.process_user() for actual business logic.
        BookingWorkflow handles slot detection, booking, and notifications internally.

        Returns:
            Dict with slot_found=False (BookingWorkflow handles its own notifications)
            or error dict if check fails
        """
        if not self.current_account:
            return {"slot_found": False, "error": "No account available"}

        try:
            workflow = self._create_booking_workflow()
            await workflow.process_user(page, self.current_account)
            # BookingWorkflow handles all notifications internally
            # Return False to avoid duplicate notifications in run_check_loop
            return {"slot_found": False}
        except Exception as e:
            logger.error(f"[{self.country}] Error in _process_check: {e}", exc_info=True)
            return {"slot_found": False, "error": str(e)}

    def _mask_email(self, email: str) -> str:
        """Mask email for logging."""
        if "@" in email:
            local, domain = email.split("@", 1)
            if len(local) > 3:
                return f"{local[:3]}***@{domain}"
        return "***"

    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        return {
            "reservation_id": self.reservation_id,
            "country": self.country,
            "running": self.running,
            "check_count": self.check_count,
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "current_account": self._mask_email(
                self.current_account.get("email", "none") if self.current_account else "none"
            ),
            "current_proxy": self.current_proxy.get("server") if self.current_proxy else "none",
        }
