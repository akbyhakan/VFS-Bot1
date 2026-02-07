"""VFS Bot orchestrator - coordinates all bot components."""

import asyncio
import logging
from typing import Any, Dict, Optional

from playwright.async_api import Page

from ...constants import Intervals, RateLimits
from ...models.database import Database
from ...utils.anti_detection.cloudflare_handler import CloudflareHandler
from ...utils.anti_detection.human_simulator import HumanSimulator
from ...utils.error_capture import ErrorCapture
from ...utils.security.header_manager import HeaderManager
from ...utils.security.proxy_manager import ProxyManager
from ...utils.security.rate_limiter import get_rate_limiter
from ...utils.security.session_manager import SessionManager
from ..adaptive_scheduler import AdaptiveScheduler
from ..appointment_booking_service import AppointmentBookingService
from ..captcha_solver import CaptchaSolver
from ..centre_fetcher import CentreFetcher
from ..country_profile_loader import CountryProfileLoader
from ..notification import NotificationService
from ..otp_webhook import get_otp_service
from ..selector_self_healing import SelectorSelfHealing
from ..session_recovery import SessionRecovery
from ..slot_analyzer import SlotPatternAnalyzer
from .auth_service import AuthService
from .booking_workflow import BookingWorkflow
from .browser_manager import BrowserManager
from .circuit_breaker_service import CircuitBreakerService
from .error_handler import ErrorHandler
from .slot_checker import SlotChecker
from .waitlist_handler import WaitlistHandler

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
        # Core initialization
        self.config = config
        self.db = db
        self.notifier = notifier
        self.running = False
        self.health_checker = None  # Will be set by main.py if enabled
        self.shutdown_event = shutdown_event or asyncio.Event()

        # Track active booking tasks for graceful shutdown
        self._active_booking_tasks: set = set()

        # Declare anti-detection components with Optional types
        self.human_sim: Optional[HumanSimulator] = None
        self.header_manager: Optional[HeaderManager] = None
        self.session_manager: Optional[SessionManager] = None
        self.cloudflare_handler: Optional[CloudflareHandler] = None
        self.proxy_manager: Optional[ProxyManager] = None

        # Initialize core services
        self._init_core_services(captcha_solver, centre_fetcher)

        # Initialize anti-detection (extracted to method)
        self._init_anti_detection()

        # Initialize modular components
        self._init_bot_components()

        logger.info("VFSBot initialized with modular components")

    def _init_core_services(
        self,
        captcha_solver: Optional[CaptchaSolver],
        centre_fetcher: Optional[CentreFetcher],
    ) -> None:
        """Initialize core services with dependency injection.

        Args:
            captcha_solver: Optional CaptchaSolver instance. If None, creates a new
                instance using configuration from self.config["captcha"].
            centre_fetcher: Optional CentreFetcher instance. If None, creates a new
                instance using configuration from self.config["vfs"].

        This method follows the dependency injection pattern, allowing external
        instances to be provided for testing or reuse, while creating defaults
        when not provided.
        """
        self.user_semaphore = asyncio.Semaphore(RateLimits.CONCURRENT_USERS)
        self.rate_limiter = get_rate_limiter()
        self.error_capture = ErrorCapture()

        self.otp_service = get_otp_service()

        captcha_config = self.config.get("captcha", {})
        self.captcha_solver = captcha_solver or CaptchaSolver(
            api_key=captcha_config.get("api_key", ""),
            manual_timeout=captcha_config.get("manual_timeout", 120),
        )

        vfs_config = self.config.get("vfs", {})
        # Validate required VFS configuration fields
        if not centre_fetcher:
            required_fields = ["base_url", "country", "mission"]
            missing_fields = [f for f in required_fields if not vfs_config.get(f)]
            if missing_fields:
                raise ValueError(
                    f"Missing required VFS configuration fields: "
                    f"{', '.join(missing_fields)}. "
                    f"Please ensure config is validated with ConfigValidator "
                    f"before initializing VFSBot."
                )

        self.centre_fetcher = centre_fetcher or CentreFetcher(
            base_url=vfs_config["base_url"],
            country=vfs_config["country"],
            mission=vfs_config["mission"],
            language=vfs_config.get("language", "tr"),
        )

    def _init_anti_detection(self) -> None:
        """Initialize anti-detection components based on configuration."""
        anti_detection_config = self.config.get("anti_detection", {})
        self.anti_detection_enabled = anti_detection_config.get("enabled", True)

        if self.anti_detection_enabled:
            self.human_sim = HumanSimulator(self.config.get("human_behavior", {}))
            self.header_manager = HeaderManager()

            session_config = self.config.get("session", {})
            self.session_manager = SessionManager(
                session_file=session_config.get("save_file", "data/session.json"),
                token_refresh_buffer=session_config.get("token_refresh_buffer", 5),
            )

            self.cloudflare_handler = CloudflareHandler(self.config.get("cloudflare", {}))
            self.proxy_manager = ProxyManager(self.config.get("proxy", {}))

            logger.info("Anti-detection features initialized")
        else:
            self.human_sim = None
            self.header_manager = None
            self.session_manager = None
            self.cloudflare_handler = None
            self.proxy_manager = None
            logger.info("Anti-detection features disabled")

    def _init_bot_components(self) -> None:
        """Initialize modular bot components."""
        # Initialize PaymentService with PCI-DSS security controls
        payment_config = self.config.get("payment", {})
        try:
            from ..services.payment_service import PaymentService
            self.payment_service = PaymentService(payment_config)
            logger.info("PaymentService initialized with PCI-DSS security controls")
        except (ImportError, ValueError) as e:
            # PaymentService is optional - bot can work without it (manual payment mode)
            logger.warning(f"PaymentService not available: {e}")
            self.payment_service = None
        
        # Initialize AlertService for critical notifications
        alert_config_dict = self.config.get("alerts", {})
        try:
            from ..alert_service import AlertChannel, AlertConfig, AlertService
            # Parse enabled channels from config
            enabled_channels_str = alert_config_dict.get("enabled_channels", ["log"])
            enabled_channels = [
                AlertChannel(ch) if isinstance(ch, str) else ch 
                for ch in enabled_channels_str
            ]
            
            alert_config = AlertConfig(
                enabled_channels=enabled_channels,
                telegram_bot_token=alert_config_dict.get("telegram_bot_token"),
                telegram_chat_id=alert_config_dict.get("telegram_chat_id"),
                email_from=alert_config_dict.get("email_from"),
                email_to=alert_config_dict.get("email_to"),
                smtp_host=alert_config_dict.get("smtp_host"),
                smtp_port=alert_config_dict.get("smtp_port"),
                webhook_url=alert_config_dict.get("webhook_url"),
            )
            self.alert_service = AlertService(alert_config)
            logger.info(f"AlertService initialized with channels: {enabled_channels}")
        except (ImportError, ValueError) as e:
            # AlertService is optional - bot can work without it (logs only)
            logger.warning(f"AlertService not available: {e}")
            self.alert_service = None
        
        self.booking_service = AppointmentBookingService(
            self.config, self.captcha_solver, self.human_sim, self.payment_service
        )

        self.waitlist_handler = WaitlistHandler(self.config, self.human_sim)

        self.browser_manager = BrowserManager(self.config, self.header_manager, self.proxy_manager)
        self.circuit_breaker = CircuitBreakerService()
        self.error_handler = ErrorHandler()

        self.auth_service = AuthService(
            self.config,
            self.captcha_solver,
            self.human_sim,
            self.cloudflare_handler,
            self.error_capture,
            self.otp_service,
        )

        self.slot_checker = SlotChecker(
            self.config,
            self.rate_limiter,
            self.human_sim,
            self.cloudflare_handler,
            self.error_capture,
        )

        # Initialize new maintenance-free automation services
        self._init_automation_services()

        # Initialize booking workflow after all dependencies are ready
        self.booking_workflow = BookingWorkflow(
            config=self.config,
            db=self.db,
            notifier=self.notifier,
            auth_service=self.auth_service,
            slot_checker=self.slot_checker,
            booking_service=self.booking_service,
            waitlist_handler=self.waitlist_handler,
            error_handler=self.error_handler,
            slot_analyzer=self.slot_analyzer,
            session_recovery=self.session_recovery,
            human_sim=self.human_sim,
            error_capture=self.error_capture,
            alert_service=self.alert_service,
        )

    def _init_automation_services(self) -> None:
        """Initialize maintenance-free automation services."""
        # Country profile loader
        self.country_profiles = CountryProfileLoader()

        # Get country from config
        vfs_config = self.config.get("vfs", {})
        country_code = vfs_config.get("country", "tur")

        # Adaptive scheduler with country-specific multiplier
        country_multiplier = self.country_profiles.get_retry_multiplier(country_code)
        timezone = self.country_profiles.get_timezone(country_code)
        self.scheduler = AdaptiveScheduler(timezone=timezone, country_multiplier=country_multiplier)

        # Slot pattern analyzer
        self.slot_analyzer = SlotPatternAnalyzer()

        # Selector self-healing
        self.self_healing = SelectorSelfHealing()

        # Session recovery
        self.session_recovery = SessionRecovery()

        logger.info(
            f"Automation services initialized - "
            f"Country: {country_code}, Timezone: {timezone}, "
            f"Multiplier: {country_multiplier}"
        )

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
        """
        Stop the bot with graceful shutdown of active bookings.

        This method waits for active booking tasks to complete gracefully
        before shutting down, with a 120-second timeout. If bookings don't
        complete within the grace period, they are forcefully cancelled.
        """
        self.running = False

        # Wait for active booking tasks to complete gracefully
        if self._active_booking_tasks:
            logger.info(f"Waiting for {len(self._active_booking_tasks)} active booking(s) to complete...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._active_booking_tasks, return_exceptions=True),
                    timeout=120  # 2 minutes grace period for bookings
                )
                logger.info("All active bookings completed")
            except asyncio.TimeoutError:
                logger.warning("Booking grace period expired, forcing shutdown")
                for task in self._active_booking_tasks:
                    task.cancel()

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

                # E5: Check and refresh session token if needed (SessionManager integration)
                if self.session_manager:
                    try:
                        if self.session_manager.is_token_expired():
                            logger.info("Session token expired or expiring soon, attempting refresh...")
                            # Define refresh callback (would need to be implemented in auth_service)
                            # For now, just log - actual refresh logic depends on VFS API
                            async def refresh_callback(refresh_token):
                                # This would call VFS API to refresh the token
                                # Implementation depends on VFS Global's token refresh endpoint
                                logger.warning("Token refresh callback not implemented - would call VFS API")
                                return None
                            
                            refresh_success = await self.session_manager.refresh_token_if_needed(refresh_callback)
                            if not refresh_success:
                                logger.warning("Token refresh failed, continuing with existing session")
                    except Exception as token_error:
                        logger.warning(f"Session token check/refresh error: {token_error}")
                        # Continue - don't stop bot for token issues

                # Check circuit breaker
                if not await self.circuit_breaker.is_available():
                    wait_time = await self.circuit_breaker.get_wait_time()
                    stats = await self.circuit_breaker.get_stats()
                    logger.warning(
                        f"Circuit breaker OPEN - waiting {wait_time}s before retry "
                        f"(consecutive errors: {stats['consecutive_errors']})"
                    )
                    
                    # Send alert for circuit breaker open (WARNING severity)
                    if self.alert_service:
                        try:
                            from ..alert_service import AlertSeverity
                            await self.alert_service.send_alert(
                                message=f"Circuit breaker OPEN - consecutive errors: {stats['consecutive_errors']}, waiting {wait_time}s",
                                severity=AlertSeverity.WARNING,
                                metadata={"stats": stats, "wait_time": wait_time}
                            )
                        except Exception as alert_error:
                            logger.debug(f"Failed to send circuit breaker alert: {alert_error}")
                    
                    await asyncio.sleep(wait_time)
                    # Don't unconditionally reset - let the next successful iteration close it
                    # Unconditional reset could cause premature recovery if underlying
                    # issues persist
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
                    # Use adaptive scheduler for intelligent interval
                    check_interval = self.scheduler.get_optimal_interval()
                    mode_info = self.scheduler.get_mode_info()
                    logger.info(
                        f"Adaptive mode: {mode_info['mode']} "
                        f"({mode_info['description']}), "
                        f"Interval: {check_interval}s"
                    )
                    await asyncio.sleep(check_interval)
                    continue

                # Process users in parallel with semaphore limit
                # Create named tasks for tracking
                tasks = []
                for user in users:
                    task = asyncio.create_task(
                        self._process_user_with_semaphore(user),
                        name=f"vfs_booking_user_{user.get('id', 'unknown')}"
                    )
                    self._active_booking_tasks.add(task)
                    task.add_done_callback(self._active_booking_tasks.discard)
                    tasks.append(task)

                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Check results and update circuit breaker
                errors_in_batch = sum(1 for r in results if isinstance(r, Exception))
                if errors_in_batch > 0:
                    logger.warning(f"{errors_in_batch}/{len(users)} users failed processing")
                    await self.circuit_breaker.record_failure()
                    
                    # Send alert for batch errors (ERROR severity)
                    if self.alert_service:
                        try:
                            from ..alert_service import AlertSeverity
                            await self.alert_service.send_alert(
                                message=f"Batch processing errors: {errors_in_batch}/{len(users)} users failed",
                                severity=AlertSeverity.ERROR,
                                metadata={"errors": errors_in_batch, "total_users": len(users)}
                            )
                        except Exception as alert_error:
                            logger.debug(f"Failed to send batch error alert: {alert_error}")
                else:
                    # Successful batch - reset consecutive errors
                    await self.circuit_breaker.record_success()

                # Wait before next check - use adaptive scheduler
                check_interval = self.scheduler.get_optimal_interval()
                mode_info = self.scheduler.get_mode_info()
                logger.info(
                    f"Adaptive mode: {mode_info['mode']} "
                    f"({mode_info['description']}), "
                    f"Waiting {check_interval}s before next check..."
                )
                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error in bot loop: {e}", exc_info=True)
                await self.notifier.notify_error("Bot Loop Error", str(e))
                await self.circuit_breaker.record_failure()
                
                # Send alert for bot loop error (ERROR severity)
                if self.alert_service:
                    try:
                        from ..alert_service import AlertSeverity
                        await self.alert_service.send_alert(
                            message=f"Bot loop error: {str(e)}",
                            severity=AlertSeverity.ERROR,
                            metadata={"error": str(e), "type": type(e).__name__}
                        )
                    except Exception as alert_error:
                        logger.debug(f"Failed to send bot loop error alert: {alert_error}")

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
            page = await self.browser_manager.new_page()
            try:
                await self.booking_workflow.process_user(page, user)
            finally:
                # Always close the page to prevent resource leak
                try:
                    await page.close()
                except Exception as close_error:
                    logger.error(f"Failed to close page: {close_error}")

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
