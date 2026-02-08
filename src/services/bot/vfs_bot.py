"""VFS Bot orchestrator - coordinates all bot components."""

import asyncio
import logging
import random
import time
import warnings
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from ...constants import Intervals, RateLimits, Timeouts
from ...models.database import Database, DatabaseState
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
        
        # Trigger event for immediate slot checks
        self._trigger_event = asyncio.Event()
        
        # Health checker task reference
        self._health_task: Optional[asyncio.Task] = None
        
        # Track if stop() has been called to make it idempotent
        self._stopped: bool = False

        # Track active booking tasks for graceful shutdown
        self._active_booking_tasks: set = set()

        # User cache for graceful degradation (Issue 3.3)
        self._cached_users: List[Dict[str, Any]] = []
        self._cached_users_time: float = 0
        self._USERS_CACHE_TTL: float = 300.0  # 5 minutes

        # Emit deprecation warnings for legacy parameters
        if captcha_solver is not None:
            warnings.warn(
                "VFSBot(captcha_solver=...) is deprecated since v2.0. "
                "Use services=BotServiceContext(...) instead. "
                "This parameter will be removed in v3.0.",
                DeprecationWarning,
                stacklevel=2,
            )

        if centre_fetcher is not None:
            warnings.warn(
                "VFSBot(centre_fetcher=...) is deprecated since v2.0. "
                "Use services=BotServiceContext(...) instead. "
                "This parameter will be removed in v3.0.",
                DeprecationWarning,
                stacklevel=2,
            )

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

    # Service attribute mapping for backward compatibility
    _LEGACY_ATTRS = {
        # Workflow services
        "auth_service": ("workflow", "auth_service"),
        "slot_checker": ("workflow", "slot_checker"),
        "booking_service": ("workflow", "booking_service"),
        "error_handler": ("workflow", "error_handler"),
        "waitlist_handler": ("workflow", "waitlist_handler"),
        "alert_service": ("workflow", "alert_service"),
        "payment_service": ("workflow", "payment_service"),
        # Core services
        "captcha_solver": ("core", "captcha_solver"),
        "centre_fetcher": ("core", "centre_fetcher"),
        "otp_service": ("core", "otp_service"),
        "rate_limiter": ("core", "rate_limiter"),
        "error_capture": ("core", "error_capture"),
        "user_semaphore": ("core", "user_semaphore"),
        # Anti-detection services
        "human_sim": ("anti_detection", "human_sim"),
        "header_manager": ("anti_detection", "header_manager"),
        "session_manager": ("anti_detection", "session_manager"),
        "token_sync": ("anti_detection", "token_sync"),
        "cloudflare_handler": ("anti_detection", "cloudflare_handler"),
        "proxy_manager": ("anti_detection", "proxy_manager"),
        # Automation services
        "scheduler": ("automation", "scheduler"),
        "slot_analyzer": ("automation", "slot_analyzer"),
        "self_healing": ("automation", "self_healing"),
        "session_recovery": ("automation", "session_recovery"),
        "country_profiles": ("automation", "country_profiles"),
    }

    _LEGACY_SPECIAL_ATTRS = {
        "anti_detection_enabled": ("anti_detection", "enabled"),
    }

    def __getattr__(self, name: str):
        """
        Handle legacy attribute access with deprecation warnings.
        
        This method provides backward compatibility for code that accesses
        service attributes directly on the VFSBot instance instead of
        through the services context.
        """
        if name in self._LEGACY_ATTRS:
            warnings.warn(
                f"Direct access to '{name}' is deprecated since v2.0. "
                f"Use 'bot.services.{self._LEGACY_ATTRS[name][0]}.{self._LEGACY_ATTRS[name][1]}' instead. "
                f"This will be removed in v3.0.",
                DeprecationWarning,
                stacklevel=2,
            )
            group, attr = self._LEGACY_ATTRS[name]
            return getattr(getattr(self.services, group), attr)

        if name in self._LEGACY_SPECIAL_ATTRS:
            group, attr = self._LEGACY_SPECIAL_ATTRS[name]
            warnings.warn(
                f"Direct access to '{name}' is deprecated since v2.0. "
                f"Use 'bot.services.{group}.{attr}' instead. "
                f"This will be removed in v3.0.",
                DeprecationWarning,
                stacklevel=2,
            )
            return getattr(getattr(self.services, group), attr)

        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

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
            try:
                stats = await self.circuit_breaker.get_stats()
                await self.services.workflow.error_handler.save_checkpoint(
                    {
                        "running": self.running,
                        "circuit_breaker_open": stats["is_open"],
                        "consecutive_errors": stats["consecutive_errors"],
                        "total_errors_count": stats["total_errors_in_window"],
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to save checkpoint on exit: {e}")

        # Call stop() which is idempotent
        await self.stop()
        return False

    async def cleanup(self) -> None:
        """Clean up browser resources."""
        try:
            await self.browser_manager.close()
            logger.info("Bot cleanup completed")
        except Exception as e:
            logger.warning(f"Error during browser cleanup: {e}")

    async def start(self) -> None:
        """Start the bot."""
        self.running = True
        self._stopped = False  # Reset stopped flag when starting
        logger.info("Starting VFS-Bot...")
        await self.notifier.notify_bot_started()

        # Start browser manager
        await self.browser_manager.start()

        try:
            # Start health checker if configured
            if self.health_checker and self.browser_manager.browser:
                self._health_task = asyncio.create_task(
                    self.health_checker.run_continuous(self.browser_manager.browser)
                )
                self._health_task.add_done_callback(self._handle_task_exception)
                logger.info("Selector health monitoring started")

            await self.run_bot_loop()
        finally:
            await self.stop()

    async def stop(self) -> None:
        """
        Stop the bot with graceful shutdown of active bookings.
        Sends notifications about shutdown status to keep users informed.
        This method is idempotent and can be called multiple times safely.
        """
        # Make stop() idempotent - return early if already stopped
        if self._stopped:
            logger.debug("stop() called but bot is already stopped")
            return
        
        self._stopped = True
        self.running = False

        # Cancel health checker task if running
        if self._health_task and not self._health_task.done():
            logger.info("Cancelling health checker task...")
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                logger.debug("Health checker task cancelled successfully")
            except Exception as e:
                logger.warning(f"Error cancelling health checker task: {e}")

        # Wait for active booking tasks to complete gracefully
        if self._active_booking_tasks:
            active_count = len(self._active_booking_tasks)
            grace_period_seconds = Timeouts.GRACEFUL_SHUTDOWN_GRACE_PERIOD
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

        # Clean up browser resources
        await self.cleanup()
        
        # Notify bot stopped with error handling
        try:
            await self.notifier.notify_bot_stopped()
        except Exception as e:
            logger.warning(f"Failed to send bot stopped notification: {e}")
        
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
    
    def _handle_task_exception(self, task: asyncio.Task) -> None:
        """
        Handle exceptions from background tasks.
        
        Args:
            task: The completed task to check for exceptions
        """
        try:
            # Check if task raised an exception
            exception = task.exception()
            if exception:
                logger.error(f"Background task failed with exception: {exception}", exc_info=exception)
        except asyncio.CancelledError:
            # Task was cancelled, this is normal during shutdown
            logger.debug("Background task was cancelled")
        except Exception as e:
            # Error getting exception from task
            logger.error(f"Error handling task exception: {e}")
    
    async def _wait_or_shutdown(self, seconds: float) -> bool:
        """
        Wait for the specified duration or until shutdown/trigger is requested.
        
        Args:
            seconds: Number of seconds to wait
            
        Returns:
            True if shutdown was requested during wait, False on normal timeout or trigger
        """
        try:
            # Wait for either shutdown or trigger event
            shutdown_task = asyncio.create_task(self.shutdown_event.wait())
            trigger_task = asyncio.create_task(self._trigger_event.wait())
            
            done, pending = await asyncio.wait(
                [shutdown_task, trigger_task],
                timeout=seconds,
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Check which event was triggered
            if shutdown_task in done:
                # Shutdown was requested
                return True
            elif trigger_task in done:
                # Trigger event - clear it and continue loop
                self._trigger_event.clear()
                return False
            else:
                # Timeout - normal sleep completion
                return False
        except asyncio.TimeoutError:
            # Normal timeout - no shutdown requested
            return False

    async def _get_users_with_fallback(self) -> List[Dict[str, Any]]:
        """
        Get active users with fallback support for graceful degradation.
        
        Uses execute_with_fallback() to implement caching layer.
        On DB failure, returns cached users if available.
        
        Returns:
            List of active users with decrypted passwords
        """
        # Try to get users from database using fallback mechanism
        users = await self.db.execute_with_fallback(
            query_func=self.db.get_active_users_with_decrypted_passwords,
            fallback_value=None,
            critical=False,
        )
        
        if users is not None:
            # Success - update cache
            self._cached_users = users
            self._cached_users_time = time.time()
            return users
        
        # DB failure - check if cache is still fresh
        cache_age = time.time() - self._cached_users_time
        if cache_age < self._USERS_CACHE_TTL and self._cached_users:
            logger.warning(
                f"Database unavailable, using cached users (age: {cache_age:.1f}s, "
                f"count: {len(self._cached_users)})"
            )
            return self._cached_users
        
        # Cache expired or empty
        logger.error(
            f"Database unavailable and cache expired (age: {cache_age:.1f}s) - "
            "returning empty user list"
        )
        return []

    async def _ensure_db_connection(self) -> None:
        """
        Ensure database connection is healthy and attempt reconnection if needed.
        
        Checks database state and calls reconnect() if degraded or disconnected.
        Sends alert on successful reconnection.
        """
        db_state = self.db.state
        
        if db_state in (DatabaseState.DEGRADED, DatabaseState.DISCONNECTED):
            logger.warning(f"Database in {db_state} state - attempting reconnection")
            
            try:
                reconnected = await self.db.reconnect()
                if reconnected:
                    logger.info("Database reconnection successful")
                    await self._send_alert_safe(
                        message="Database connection restored",
                        severity=AlertSeverity.INFO,
                        metadata={"previous_state": db_state, "new_state": self.db.state},
                    )
                else:
                    logger.error("Database reconnection failed")
            except Exception as e:
                logger.error(f"Error during database reconnection: {e}")

    async def run_bot_loop(self) -> None:
        """Main bot loop to check for slots with circuit breaker and parallel processing."""
        while self.running and not self.shutdown_event.is_set():
            try:
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

                    if await self._wait_or_shutdown(wait_time):
                        logger.info("Shutdown requested during circuit breaker wait")
                        break
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

                # Ensure database connection is healthy
                await self._ensure_db_connection()

                # Get active users with fallback support
                users = await self._get_users_with_fallback()
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
                    if await self._wait_or_shutdown(check_interval):
                        logger.info("Shutdown requested during interval wait")
                        break
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
                if await self._wait_or_shutdown(check_interval):
                    logger.info("Shutdown requested during interval wait")
                    break

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
                    if await self._wait_or_shutdown(wait_time):
                        logger.info("Shutdown requested during error recovery wait")
                        break
                else:
                    # Add jitter to prevent thundering herd on recovery
                    jitter = random.uniform(0.8, 1.2)
                    if await self._wait_or_shutdown(Intervals.ERROR_RECOVERY * jitter):
                        logger.info("Shutdown requested during error recovery wait")
                        break

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
