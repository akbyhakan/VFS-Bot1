"""VFS Bot orchestrator - coordinates all bot components."""

import asyncio
import os
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger
from playwright.async_api import Page

from ...constants import CircuitBreaker as CircuitBreakerConfig
from ...constants import Intervals, RateLimits, Timeouts
from ...core.infra.circuit_breaker import CircuitBreaker, CircuitState
from ...models.database import Database, DatabaseState
from ...repositories import UserRepository
from ..alert_service import AlertSeverity
from ..notification import NotificationService
from .booking_workflow import BookingWorkflow
from .browser_manager import BrowserManager
from .service_context import BotServiceContext, BotServiceFactory

if TYPE_CHECKING:
    from ...core.infra.runners import BotConfigDict

# Module-level optional import for metrics
try:
    from ...utils.metrics import get_metrics as _get_metrics

    _HAS_METRICS = True
except ImportError:
    _get_metrics = None  # type: ignore
    _HAS_METRICS = False


@dataclass
class UserCache:
    """Cache for active users to support graceful degradation."""

    users: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: float = 0.0
    ttl: float = 300.0


class VFSBot:
    """VFS appointment booking bot orchestrator using modular components."""

    def __init__(
        self,
        config: "BotConfigDict",
        db: Database,
        notifier: NotificationService,
        services: Optional[BotServiceContext] = None,
        shutdown_event: Optional[asyncio.Event] = None,
    ):
        """
        Initialize VFS bot with dependency injection.

        Args:
            config: Bot configuration dictionary
            db: Database instance
            notifier: Notification service instance
            shutdown_event: Optional event to signal graceful shutdown
            services: BotServiceContext with all required services
        """
        # Core initialization
        self.config = config
        self.db = db
        self.notifier = notifier
        self.running = False
        self.health_checker = None  # Will be set by main.py if enabled
        self.shutdown_event = shutdown_event or asyncio.Event()

        # Initialize repositories
        self.user_repo = UserRepository(db)

        # Trigger event for immediate slot checks
        self._trigger_event = asyncio.Event()

        # Health checker task reference
        self._health_task: Optional[asyncio.Task] = None

        # Track if stop() has been called to make it idempotent
        self._stopped: bool = False

        # Track active booking tasks for graceful shutdown
        self._active_booking_tasks: set = set()

        # User cache for graceful degradation (Issue 3.3)
        self._user_cache = UserCache(ttl=float(os.getenv("USERS_CACHE_TTL", "300.0")))

        # Initialize services context
        if services is None:
            services = BotServiceFactory.create(config, db, notifier)
        self.services = services

        # Initialize browser manager (needs anti-detection services)
        self.browser_manager = BrowserManager(
            self.config,
            self.services.anti_detection.header_manager,
            self.services.anti_detection.proxy_manager,
        )

        # Initialize circuit breaker with configuration
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=CircuitBreakerConfig.FAIL_THRESHOLD,
            timeout_seconds=CircuitBreakerConfig.RESET_TIMEOUT_SECONDS,
            name="BotCircuitBreaker",
            half_open_threshold=CircuitBreakerConfig.HALF_OPEN_SUCCESS_THRESHOLD,
            max_errors_per_hour=CircuitBreakerConfig.MAX_ERRORS_PER_HOUR,
            error_tracking_window=CircuitBreakerConfig.ERROR_WINDOW_SECONDS,
            backoff_base=CircuitBreakerConfig.BACKOFF_BASE_SECONDS,
            backoff_max=CircuitBreakerConfig.BACKOFF_MAX_SECONDS,
        )

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
                stats = self.circuit_breaker.get_stats()
                await self.services.workflow.error_handler.save_checkpoint(
                    {
                        "running": self.running,
                        "circuit_breaker_open": stats["state"] == CircuitState.OPEN.value,
                        "consecutive_errors": stats["failure_count"],
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

                # Collect task information for checkpoint before cancellation
                task_names = []
                for task in self._active_booking_tasks:
                    try:
                        task_name = task.get_name()
                        task_names.append(task_name)
                    except Exception:
                        task_names.append("unknown")
                
                # Save checkpoint state before cancelling tasks
                try:
                    checkpoint_state = {
                        "event": "forced_shutdown",
                        "cancelled_task_count": len(self._active_booking_tasks),
                        "cancelled_tasks": task_names,
                        "reason": "grace_period_timeout",
                    }
                    await self.services.workflow.error_handler.save_checkpoint(checkpoint_state)
                    logger.info(f"Checkpoint saved for {len(self._active_booking_tasks)} cancelled tasks")
                except Exception as checkpoint_error:
                    # Don't let checkpoint failure block shutdown
                    logger.error(f"Failed to save checkpoint during shutdown: {checkpoint_error}")
                
                # Notify about forced cancellation with checkpoint info
                await self._send_alert_safe(
                    message=(
                        f"⚠️ Forced shutdown - {len(self._active_booking_tasks)} "
                        f"booking(s) cancelled after {grace_period_display} timeout"
                    ),
                    severity=AlertSeverity.ERROR,
                    metadata={
                        "cancelled_bookings": len(self._active_booking_tasks),
                        "cancelled_tasks": task_names,
                    },
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

    def trigger_immediate_check(self) -> None:
        """Trigger an immediate slot check by setting the trigger event."""
        self._trigger_event.set()

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
                logger.error(
                    f"Background task failed with exception: {exception}", exc_info=exception
                )
        except asyncio.CancelledError:
            # Task was cancelled, this is normal during shutdown
            logger.debug("Background task was cancelled")
        except Exception as e:
            # Error getting exception from task
            logger.error(f"Error handling task exception: {e}")

    async def _wait_or_shutdown(self, seconds: float) -> bool:
        """
        Wait for the specified duration or until shutdown/trigger is requested.

        Uses polling with short sleep intervals to avoid creating/canceling tasks
        on each call, reducing GC pressure in high-frequency loops.

        Args:
            seconds: Number of seconds to wait

        Returns:
            True if shutdown was requested during wait, False on normal timeout or trigger
        """
        end_time = asyncio.get_event_loop().time() + seconds
        poll_interval = 0.1  # Poll every 100ms

        while True:
            # Check shutdown event first (highest priority)
            if self.shutdown_event.is_set():
                return True

            # Check trigger event
            if self._trigger_event.is_set():
                self._trigger_event.clear()
                return False

            # Calculate remaining time
            remaining = end_time - asyncio.get_event_loop().time()
            if remaining <= 0:
                # Timeout - normal sleep completion
                return False

            # Sleep for short interval or remaining time, whichever is smaller
            await asyncio.sleep(min(remaining, poll_interval))

    async def _get_users_with_fallback(self) -> List[Dict[str, Any]]:
        """
        Get active users with fallback support for graceful degradation.

        Uses cache as primary strategy with TTL. Only queries DB when cache
        is empty or TTL expired. On DB failure, returns cached users if available.

        Returns:
            List of active users with decrypted passwords
        """
        # Check cache first - if valid and not expired, return immediately
        cache_age = time.time() - self._user_cache.timestamp
        if cache_age < self._user_cache.ttl and self._user_cache.users:
            # Cache is fresh - return without DB query
            return self._user_cache.users

        # Cache expired or empty - query database
        users = await self.db.execute_with_fallback(
            query_func=self.user_repo.get_all_active_with_passwords,
            fallback_value=None,
            critical=False,
        )

        if users is not None:
            # Success - update cache
            self._user_cache.users = users
            self._user_cache.timestamp = time.time()
            return users

        # DB failure - check if we have expired cache to fall back to
        if self._user_cache.users:
            logger.warning(
                f"Database unavailable, using expired cached users (age: {cache_age:.1f}s, "
                f"count: {len(self._user_cache.users)})"
            )
            return self._user_cache.users

        # No cache available at all
        logger.error("Database unavailable and no cached users available - returning empty list")
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

    async def _record_circuit_breaker_trip(self) -> None:
        """
        Record circuit breaker trip metric when circuit breaker opens.

        This method checks if the circuit breaker is in OPEN state and records
        the trip metric. Failures to record metrics are logged but do not raise exceptions.
        """
        if not _HAS_METRICS:
            return
        if self.circuit_breaker.state == CircuitState.OPEN:
            try:
                metrics = await _get_metrics()
                await metrics.record_circuit_breaker_trip()
            except Exception as e:
                logger.debug(f"Failed to record circuit breaker trip metric: {e}")

    async def _handle_circuit_breaker_open(self) -> bool:
        """
        Handle circuit breaker open state with logging, alerting, and waiting.

        Returns:
            True if shutdown was requested during wait, False otherwise
        """
        wait_time = await self.circuit_breaker.get_wait_time()
        stats = self.circuit_breaker.get_stats()
        logger.warning(
            f"Circuit breaker OPEN - waiting {wait_time}s before retry "
            f"(consecutive errors: {stats['failure_count']})"
        )

        # Send alert for circuit breaker open (WARNING severity)
        await self._send_alert_safe(
            message=(
                f"Circuit breaker OPEN - consecutive errors: "
                f"{stats['failure_count']}, waiting {wait_time}s"
            ),
            severity=AlertSeverity.WARNING,
            metadata={"stats": stats, "wait_time": wait_time},
        )

        if await self._wait_or_shutdown(wait_time):
            logger.info("Shutdown requested during circuit breaker wait")
            return True
        # Don't unconditionally reset - let the next successful iteration close it
        # Unconditional reset could cause premature recovery if underlying
        # issues persist
        # Circuit will be closed by record_success() if the next attempt succeeds
        logger.info(
            "Circuit breaker wait time elapsed - attempting next iteration "
            "(circuit will close on success)"
        )
        return False

    async def _process_batch(self, users: List[Dict[str, Any]]) -> None:
        """
        Process batch of users with parallel processing and error handling.

        Creates tasks for each user, executes them in parallel with semaphore control,
        analyzes results, and updates circuit breaker state based on error rate.
        Sends alerts on batch errors.

        Args:
            users: List of user dictionaries to process
        """
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

        # Calculate error rate
        errors_in_batch = sum(1 for r in results if isinstance(r, Exception))
        total_users = len(users)
        error_rate = errors_in_batch / total_users if total_users > 0 else 0.0

        # Use error rate threshold from constants
        threshold = CircuitBreakerConfig.BATCH_ERROR_RATE_THRESHOLD

        if error_rate >= threshold:
            # Systemic issue - high error rate (>= 50%)
            logger.error(
                f"High error rate in batch: {errors_in_batch}/{total_users} "
                f"({error_rate:.1%}) >= threshold ({threshold:.1%})"
            )
            await self.circuit_breaker.record_failure()

            # Record circuit breaker trip in metrics if it just opened
            await self._record_circuit_breaker_trip()

            # Send alert for batch errors (ERROR severity)
            await self._send_alert_safe(
                message=(
                    f"High batch error rate: {errors_in_batch}/{total_users} "
                    f"({error_rate:.1%}) - systemic issue"
                ),
                severity=AlertSeverity.ERROR,
                metadata={
                    "errors": errors_in_batch,
                    "total_users": total_users,
                    "error_rate": error_rate,
                },
            )
        elif error_rate > 0:
            # Isolated errors - low error rate (< 50%)
            logger.warning(
                f"Isolated errors in batch: {errors_in_batch}/{total_users} "
                f"({error_rate:.1%}) < threshold ({threshold:.1%})"
            )
            # Record success to reset consecutive failure count
            await self.circuit_breaker.record_success()

            # Send alert for tracking (WARNING severity)
            await self._send_alert_safe(
                message=(
                    f"Batch errors (isolated): {errors_in_batch}/{total_users} "
                    f"({error_rate:.1%})"
                ),
                severity=AlertSeverity.WARNING,
                metadata={
                    "errors": errors_in_batch,
                    "total_users": total_users,
                    "error_rate": error_rate,
                },
            )
        else:
            # Perfect success - no errors
            await self.circuit_breaker.record_success()

    async def _wait_adaptive_interval(self) -> bool:
        """
        Wait for adaptive interval before next check.

        Uses the adaptive scheduler to determine optimal wait time based on
        current system state and activity patterns.

        Returns:
            True if shutdown was requested during wait, False otherwise
        """
        check_interval = self.services.automation.scheduler.get_optimal_interval()
        mode_info = self.services.automation.scheduler.get_mode_info()
        logger.info(
            f"Adaptive mode: {mode_info['mode']} "
            f"({mode_info['description']}), "
            f"Waiting {check_interval}s before next check..."
        )
        if await self._wait_or_shutdown(check_interval):
            logger.info("Shutdown requested during interval wait")
            return True
        return False

    async def run_bot_loop(self) -> None:
        """Main bot loop to check for slots with circuit breaker and parallel processing."""
        while self.running and not self.shutdown_event.is_set():
            try:
                # Note: Token synchronization between VFSApiClient and SessionManager
                # is handled by TokenSyncService when VFSApiClient is integrated.
                # The TokenSyncService ensures proactive token refresh before expiry.

                # Check circuit breaker
                if not await self.circuit_breaker.can_execute():
                    if await self._handle_circuit_breaker_open():
                        break
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
                    if await self._wait_adaptive_interval():
                        break
                    continue

                # Process users in batch
                await self._process_batch(users)

                # Wait before next check
                if await self._wait_adaptive_interval():
                    break

            except Exception as e:
                logger.error(f"Error in bot loop: {e}", exc_info=True)
                await self.notifier.notify_error("Bot Loop Error", str(e))
                await self.circuit_breaker.record_failure()

                # Record circuit breaker trip in metrics if it just opened
                await self._record_circuit_breaker_trip()

                # Send alert for bot loop error (ERROR severity)
                await self._send_alert_safe(
                    message=f"Bot loop error: {str(e)}",
                    severity=AlertSeverity.ERROR,
                    metadata={"error": str(e), "type": type(e).__name__},
                )

                # If circuit breaker open, wait longer
                if not await self.circuit_breaker.can_execute():
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
                    # Force browser restart on next cycle to prevent orphan page accumulation
                    self.browser_manager._page_count = self.browser_manager._max_pages_before_restart
                    logger.warning(
                        "Browser restart forced due to page close failure - "
                        "orphan pages may cause memory leaks"
                    )

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
