"""VFS Bot orchestrator - coordinates all bot components."""

import asyncio
from typing import TYPE_CHECKING, Any, Dict, Optional

from loguru import logger
from playwright.async_api import Page

from ...constants import CircuitBreakerConfig, Timeouts
from ...core.infra.circuit_breaker import CircuitBreaker, CircuitState
from ...models.database import Database
from ...repositories import AppointmentRepository, AppointmentRequestRepository
from ...repositories.payment_repository import PaymentRepository
from ..notification.alert_service import AlertSeverity, send_alert_safe
from ..notification.notification import NotificationService
from ..session.account_pool import AccountPool
from ..session.session_orchestrator import SessionOrchestrator
from .booking_dependencies import (
    BookingDependencies,
    InfraServices,
    RepositoryServices,
    WorkflowServices,
)
from .booking_workflow import BookingWorkflow
from .bot_loop_manager import BotLoopManager
from .browser_manager import BrowserManager
from .service_context import BotServiceContext, BotServiceFactory

if TYPE_CHECKING:
    from ...core.infra.runners import BotConfigDict


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
        self.health_checker: Any = None  # Will be set by main.py if enabled
        self.shutdown_event = shutdown_event or asyncio.Event()

        # Trigger event for immediate slot checks
        self._trigger_event = asyncio.Event()

        # Health checker task reference
        self._health_task: Optional[asyncio.Task] = None

        # Track if stop() has been called to make it idempotent
        self._stopped: bool = False

        # Track if cleanup() has been called to make it idempotent
        self._cleaned_up: bool = False

        # Track active booking tasks for graceful shutdown
        self._active_booking_tasks: set = set()

        # Initialize services context
        if services is None:
            services = BotServiceFactory.create(config)
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
        deps = self._wire_booking_dependencies(self.services, self.browser_manager, self.db)

        self.booking_workflow = BookingWorkflow(
            config=self.config,
            notifier=self.notifier,
            deps=deps,
        )

        # Initialize account pool and session orchestrator
        self.account_pool = AccountPool(db=self.db, shutdown_event=self.shutdown_event)
        self.session_orchestrator = SessionOrchestrator(
            db=self.db,
            account_pool=self.account_pool,
            booking_workflow=self.booking_workflow,
            browser_manager=self.browser_manager,
        )

        # Initialize bot loop manager
        self._loop_manager = BotLoopManager(
            config=self.config,
            db=self.db,
            services=self.services,
            browser_manager=self.browser_manager,
            circuit_breaker=self.circuit_breaker,
            account_pool=self.account_pool,
            session_orchestrator=self.session_orchestrator,
            notifier=self.notifier,
            shutdown_event=self.shutdown_event,
            trigger_event=self._trigger_event,
        )

        logger.info("VFSBot initialized with account pool and session orchestrator")

    @staticmethod
    def _wire_booking_dependencies(
        services: BotServiceContext,
        browser_manager: BrowserManager,
        db: Database,
    ) -> BookingDependencies:
        """
        Wire booking dependencies from service context and infrastructure.

        Isolates the dependency wiring logic (WorkflowServices → InfraServices →
        RepositoryServices → BookingDependencies) from __init__.

        Args:
            services: BotServiceContext containing workflow and infrastructure services
            browser_manager: Initialized BrowserManager instance
            db: Database instance for repository creation

        Returns:
            Fully wired BookingDependencies instance
        """
        workflow_services = WorkflowServices(
            auth_service=services.workflow.auth_service,
            slot_checker=services.workflow.slot_checker,
            booking_service=services.workflow.booking_service,
            waitlist_handler=services.workflow.waitlist_handler,
            error_handler=services.workflow.error_handler,
            page_state_detector=services.workflow.page_state_detector,
            slot_analyzer=services.automation.slot_analyzer,
            session_recovery=services.automation.session_recovery,
            alert_service=services.workflow.alert_service,
        )

        infra_services = InfraServices(
            browser_manager=browser_manager,
            header_manager=services.anti_detection.header_manager,
            proxy_manager=services.anti_detection.proxy_manager,
            human_sim=services.anti_detection.human_sim,
            error_capture=services.core.error_capture,
        )

        repository_services = RepositoryServices(
            appointment_repo=AppointmentRepository(db),
            appointment_request_repo=AppointmentRequestRepository(db),
            payment_repo=PaymentRepository(db),
        )

        return BookingDependencies(
            workflow=workflow_services,
            infra=infra_services,
            repositories=repository_services,
        )

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
        """Clean up browser resources. Idempotent — safe to call multiple times."""
        if self._cleaned_up:
            logger.debug("cleanup() called but already cleaned up")
            return
        self._cleaned_up = True
        try:
            await self.browser_manager.close()
            logger.info("Bot cleanup completed")
        except Exception as e:
            logger.warning(f"Error during browser cleanup: {e}")

    async def start(self) -> None:
        """Start the bot."""
        self.running = True
        self._stopped = False  # Reset stopped flag when starting
        self._cleaned_up = False  # Reset cleaned up flag when starting
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

            await self._loop_manager.run_bot_loop()
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

        await self._cancel_health_checker()
        await self._shutdown_active_bookings()
        await self.cleanup()
        await self._notify_stopped()
        logger.info("VFS-Bot stopped")

    async def _cancel_health_checker(self) -> None:
        """Cancel health checker task if running."""
        if self._health_task and not self._health_task.done():
            logger.info("Cancelling health checker task...")
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                logger.debug("Health checker task cancelled successfully")
            except Exception as e:
                logger.warning(f"Error cancelling health checker task: {e}")

    async def _shutdown_active_bookings(self) -> None:
        """Wait for active booking tasks to complete gracefully, then force-cancel if needed."""
        if not self._active_booking_tasks:
            return

        active_count = len(self._active_booking_tasks)
        grace_period_seconds = Timeouts.GRACEFUL_SHUTDOWN_GRACE_PERIOD
        grace_period_display = f"{grace_period_seconds // 60} min"

        logger.info(f"Waiting for {active_count} active booking(s) to complete...")

        # Notify about pending shutdown
        await send_alert_safe(
            alert_service=self.services.workflow.alert_service,
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
            await self._force_cancel_bookings(grace_period_display)

    async def _force_cancel_bookings(self, grace_display: str) -> None:
        """Force-cancel all active booking tasks after grace period timeout."""
        task_names = []
        for task in self._active_booking_tasks:
            try:
                task_name = task.get_name()
                task_names.append(task_name)
            except Exception:
                task_names.append("unknown")

        await self._save_shutdown_checkpoint(task_names)

        # Notify about forced cancellation with checkpoint info
        await send_alert_safe(
            alert_service=self.services.workflow.alert_service,
            message=(
                f"⚠️ Forced shutdown - {len(self._active_booking_tasks)} "
                f"booking(s) cancelled after {grace_display} timeout"
            ),
            severity=AlertSeverity.ERROR,
            metadata={
                "cancelled_bookings": len(self._active_booking_tasks),
                "cancelled_tasks": task_names,
            },
        )
        for task in self._active_booking_tasks:
            task.cancel()

    async def _save_shutdown_checkpoint(self, task_names: list) -> None:
        """Save checkpoint state before cancelling tasks."""
        try:
            checkpoint_state = {
                "event": "forced_shutdown",
                "cancelled_task_count": len(self._active_booking_tasks),
                "cancelled_tasks": task_names,
                "reason": "grace_period_timeout",
            }
            await self.services.workflow.error_handler.save_checkpoint(checkpoint_state)
            logger.info(
                f"Checkpoint saved for {len(self._active_booking_tasks)} cancelled tasks"
            )
        except Exception as checkpoint_error:
            # Don't let checkpoint failure block shutdown
            logger.error(f"Failed to save checkpoint during shutdown: {checkpoint_error}")

    async def _notify_stopped(self) -> None:
        """Send bot stopped notification."""
        try:
            await self.notifier.notify_bot_stopped()
        except Exception as e:
            logger.warning(f"Failed to send bot stopped notification: {e}")

    def trigger_immediate_check(self) -> None:
        """Trigger an immediate slot check by setting the trigger event."""
        self._trigger_event.set()

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
