"""VFS Bot orchestrator - coordinates all bot components."""

import asyncio
import logging
import random
from typing import Any, Dict, Optional

from playwright.async_api import Page

from ...constants import Intervals, RateLimits
from ...models.database import Database
from ..alert_service import AlertSeverity
from ..captcha_solver import CaptchaSolver
from ..centre_fetcher import CentreFetcher
from ..notification import NotificationService
from .booking_workflow import BookingWorkflow
from .browser_manager import BrowserManager
from .circuit_breaker_service import CircuitBreakerService
from .service_context import BotServiceContext, BotServiceFactory

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
        services: Optional[BotServiceContext] = None,
    ):
        """
        Initialize VFS bot with dependency injection.

        Args:
            config: Bot configuration dictionary
            db: Database instance
            notifier: Notification service instance
            shutdown_event: Optional event to signal graceful shutdown
            captcha_solver: Optional CaptchaSolver instance (created if not provided)
                DEPRECATED: Use services parameter instead for better testability
            centre_fetcher: Optional CentreFetcher instance (created if not provided)
                DEPRECATED: Use services parameter instead for better testability
            services: Optional pre-created BotServiceContext (created if not provided)
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

        # Initialize services context (either provided or created from config)
        if services is None:
            # Backward compatibility: use deprecated parameters if provided
            self.services = BotServiceFactory.create(config, captcha_solver, centre_fetcher)
        else:
            self.services = services

        # Initialize browser manager (needs anti-detection services)
        self.browser_manager = BrowserManager(
            self.config,
            self.services.anti_detection.header_manager,
            self.services.anti_detection.proxy_manager,
        )

        # Initialize circuit breaker
        self.circuit_breaker = CircuitBreakerService()

        # Initialize booking workflow after all dependencies are ready
        self.booking_workflow = BookingWorkflow(
            config=self.config,
            db=self.db,
            notifier=self.notifier,
            auth_service=self.services.workflow.auth_service,
            slot_checker=self.services.workflow.slot_checker,
            booking_service=self.services.workflow.booking_service,
            waitlist_handler=self.services.workflow.waitlist_handler,
            error_handler=self.services.workflow.error_handler,
            slot_analyzer=self.services.automation.slot_analyzer,
            session_recovery=self.services.automation.session_recovery,
            human_sim=self.services.anti_detection.human_sim,
            error_capture=self.services.core.error_capture,
            alert_service=self.services.workflow.alert_service,
        )

        logger.info("VFSBot initialized with modular components")

    # Backward compatibility properties for legacy code accessing old attributes
    @property
    def auth_service(self):
        """Backward compatibility property for auth_service."""
        return self.services.workflow.auth_service

    @property
    def slot_checker(self):
        """Backward compatibility property for slot_checker."""
        return self.services.workflow.slot_checker

    @property
    def booking_service(self):
        """Backward compatibility property for booking_service."""
        return self.services.workflow.booking_service

    @property
    def error_handler(self):
        """Backward compatibility property for error_handler."""
        return self.services.workflow.error_handler

    @property
    def waitlist_handler(self):
        """Backward compatibility property for waitlist_handler."""
        return self.services.workflow.waitlist_handler

    @property
    def alert_service(self):
        """Backward compatibility property for alert_service."""
        return self.services.workflow.alert_service

    @property
    def payment_service(self):
        """Backward compatibility property for payment_service."""
        return self.services.workflow.payment_service

    @property
    def captcha_solver(self):
        """Backward compatibility property for captcha_solver."""
        return self.services.core.captcha_solver

    @property
    def centre_fetcher(self):
        """Backward compatibility property for centre_fetcher."""
        return self.services.core.centre_fetcher

    @property
    def otp_service(self):
        """Backward compatibility property for otp_service."""
        return self.services.core.otp_service

    @property
    def rate_limiter(self):
        """Backward compatibility property for rate_limiter."""
        return self.services.core.rate_limiter

    @property
    def error_capture(self):
        """Backward compatibility property for error_capture."""
        return self.services.core.error_capture

    @property
    def user_semaphore(self):
        """Backward compatibility property for user_semaphore."""
        return self.services.core.user_semaphore

    @property
    def human_sim(self):
        """Backward compatibility property for human_sim."""
        return self.services.anti_detection.human_sim

    @property
    def header_manager(self):
        """Backward compatibility property for header_manager."""
        return self.services.anti_detection.header_manager

    @property
    def session_manager(self):
        """Backward compatibility property for session_manager."""
        return self.services.anti_detection.session_manager

    @property
    def token_sync(self):
        """Backward compatibility property for token_sync."""
        return self.services.anti_detection.token_sync

    @property
    def cloudflare_handler(self):
        """Backward compatibility property for cloudflare_handler."""
        return self.services.anti_detection.cloudflare_handler

    @property
    def proxy_manager(self):
        """Backward compatibility property for proxy_manager."""
        return self.services.anti_detection.proxy_manager

    @property
    def anti_detection_enabled(self):
        """Backward compatibility property for anti_detection_enabled."""
        return self.services.anti_detection.enabled

    @property
    def scheduler(self):
        """Backward compatibility property for scheduler."""
        return self.services.automation.scheduler

    @property
    def slot_analyzer(self):
        """Backward compatibility property for slot_analyzer."""
        return self.services.automation.slot_analyzer

    @property
    def self_healing(self):
        """Backward compatibility property for self_healing."""
        return self.services.automation.self_healing

    @property
    def session_recovery(self):
        """Backward compatibility property for session_recovery."""
        return self.services.automation.session_recovery

    @property
    def country_profiles(self):
        """Backward compatibility property for country_profiles."""
        return self.services.automation.country_profiles

    async def __aenter__(self) -> "VFSBot":
        """
        Async context manager entry.

        Returns:
            Self instance
        """
        await self.start()
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
            await self.services.workflow.error_handler.save_checkpoint(
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
        Sends notifications about shutdown status to keep users informed.
        """
        self.running = False

        # Wait for active booking tasks to complete gracefully
        if self._active_booking_tasks:
            active_count = len(self._active_booking_tasks)
            grace_period_seconds = 120  # 2 minutes grace period for bookings
            grace_period_display = f"{grace_period_seconds // 60} min"

            logger.info(f"Waiting for {active_count} active booking(s) to complete...")

            # Notify about pending shutdown
            await self._send_alert_safe(
                message=(
                    f"⏳ Bot shutting down - waiting for {active_count} "
                    f"active booking(s) to complete ({grace_period_display} grace period)"
                ),
                severity=AlertSeverity.WARNING,
                metadata={"active_bookings": active_count},
            )

            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._active_booking_tasks, return_exceptions=True),
                    timeout=grace_period_seconds,
                )
                logger.info("All active bookings completed")
            except asyncio.TimeoutError:
                logger.warning("Booking grace period expired, forcing shutdown")
                # Notify about forced cancellation
                await self._send_alert_safe(
                    message=(
                        f"⚠️ Forced shutdown - {len(self._active_booking_tasks)} "
                        f"booking(s) cancelled after {grace_period_display} timeout"
                    ),
                    severity=AlertSeverity.ERROR,
                    metadata={"cancelled_bookings": len(self._active_booking_tasks)},
                )
                for task in self._active_booking_tasks:
                    task.cancel()

        await self.browser_manager.close()
        await self.notifier.notify_bot_stopped()
        logger.info("VFS-Bot stopped")

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
        if not self.services.workflow.alert_service:
            return
        try:
            await self.services.workflow.alert_service.send_alert(
                message=message,
                severity=severity,
                metadata=metadata or {},
            )
        except Exception as e:
            logger.debug(f"Alert delivery failed: {e}")

    async def run_bot_loop(self) -> None:
        """Main bot loop to check for slots with circuit breaker and parallel processing."""
        while self.running and not self.shutdown_event.is_set():
            try:
                # Check for shutdown request
                if self.shutdown_event.is_set():
                    logger.info("Shutdown requested, stopping bot loop...")
                    break

                # Note: Token synchronization between VFSApiClient and SessionManager
                # is handled by TokenSyncService when VFSApiClient is integrated.
                # The TokenSyncService ensures proactive token refresh before expiry.

                # Check circuit breaker
                if not await self.circuit_breaker.is_available():
                    wait_time = await self.circuit_breaker.get_wait_time()
                    stats = await self.circuit_breaker.get_stats()
                    logger.warning(
                        f"Circuit breaker OPEN - waiting {wait_time}s before retry "
                        f"(consecutive errors: {stats['consecutive_errors']})"
                    )

                    # Send alert for circuit breaker open (WARNING severity)
                    await self._send_alert_safe(
                        message=(
                            f"Circuit breaker OPEN - consecutive errors: "
                            f"{stats['consecutive_errors']}, waiting {wait_time}s"
                        ),
                        severity=AlertSeverity.WARNING,
                        metadata={"stats": stats, "wait_time": wait_time},
                    )

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

                # Check if browser needs restart for memory management
                if await self.browser_manager.should_restart():
                    await self.browser_manager.restart_fresh()

                # Get active users with decrypted passwords
                users = await self.db.get_active_users_with_decrypted_passwords()
                logger.info(
                    f"Processing {len(users)} active users "
                    f"(max {RateLimits.CONCURRENT_USERS} concurrent)"
                )

                if not users:
                    logger.info("No active users to process")
                    # Use adaptive scheduler for intelligent interval
                    check_interval = self.services.automation.scheduler.get_optimal_interval()
                    mode_info = self.services.automation.scheduler.get_mode_info()
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
                        name=f"vfs_booking_user_{user.get('id', 'unknown')}",
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
                    await self._send_alert_safe(
                        message=(
                            f"Batch processing errors: {errors_in_batch}/"
                            f"{len(users)} users failed"
                        ),
                        severity=AlertSeverity.ERROR,
                        metadata={"errors": errors_in_batch, "total_users": len(users)},
                    )
                else:
                    # Successful batch - reset consecutive errors
                    await self.circuit_breaker.record_success()

                # Wait before next check - use adaptive scheduler
                check_interval = self.services.automation.scheduler.get_optimal_interval()
                mode_info = self.services.automation.scheduler.get_mode_info()
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
                await self._send_alert_safe(
                    message=f"Bot loop error: {str(e)}",
                    severity=AlertSeverity.ERROR,
                    metadata={"error": str(e), "type": type(e).__name__},
                )

                # If circuit breaker open, wait longer
                if not await self.circuit_breaker.is_available():
                    wait_time = await self.circuit_breaker.get_wait_time()
                    await asyncio.sleep(wait_time)
                else:
                    # Add jitter to prevent thundering herd on recovery
                    jitter = random.uniform(0.8, 1.2)
                    await asyncio.sleep(Intervals.ERROR_RECOVERY * jitter)

    async def _process_user_with_semaphore(self, user: Dict[str, Any]) -> None:
        """
        Process user with semaphore for concurrency control.

        Args:
            user: User dictionary from database
        """
        async with self.services.core.user_semaphore:
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
        return await self.services.workflow.booking_service.run_booking_flow(page, reservation)
