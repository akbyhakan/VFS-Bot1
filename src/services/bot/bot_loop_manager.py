"""Bot loop manager - handles the main bot processing loop."""

import asyncio
import random
from typing import TYPE_CHECKING

from loguru import logger

from ...constants import AccountPoolConfig, Intervals
from ...core.infra.circuit_breaker import CircuitBreaker, CircuitState
from ...models.database import Database, DatabaseState
from ..notification.alert_service import AlertSeverity, send_alert_safe
from ..notification.notification import NotificationService
from ..session.account_pool import AccountPool
from ..session.session_orchestrator import SessionOrchestrator
from .browser_manager import BrowserManager
from .service_context import BotServiceContext

if TYPE_CHECKING:
    from ...core.infra.runners import BotConfigDict

# Module-level optional import for metrics
try:
    from ...utils.metrics import get_metrics as _get_metrics

    _HAS_METRICS = True
except ImportError:
    _get_metrics = None  # type: ignore
    _HAS_METRICS = False


class BotLoopManager:
    """Manages the main bot processing loop and associated helpers."""

    def __init__(
        self,
        *,
        config: "BotConfigDict",
        db: Database,
        services: BotServiceContext,
        browser_manager: BrowserManager,
        circuit_breaker: CircuitBreaker,
        account_pool: AccountPool,
        session_orchestrator: SessionOrchestrator,
        notifier: NotificationService,
        shutdown_event: asyncio.Event,
        trigger_event: asyncio.Event,
    ):
        self.config = config
        self.db = db
        self.services = services
        self.browser_manager = browser_manager
        self.circuit_breaker = circuit_breaker
        self.account_pool = account_pool
        self.session_orchestrator = session_orchestrator
        self.notifier = notifier
        self.shutdown_event = shutdown_event
        self._trigger_event = trigger_event
        self.running = True

    async def _wait_or_shutdown(self, seconds: float) -> bool:
        """
        Wait for the specified duration or until shutdown/trigger is requested.

        Uses event-based waiting with asyncio.wait() for efficient resource usage.
        Responds instantly to shutdown or trigger events without polling overhead.

        Args:
            seconds: Number of seconds to wait

        Returns:
            True if shutdown was requested during wait, False on normal timeout or trigger
        """
        if self.shutdown_event.is_set():
            return True
        shutdown_task = asyncio.create_task(self.shutdown_event.wait())
        trigger_task = asyncio.create_task(self._trigger_event.wait())

        try:
            done, pending = await asyncio.wait(
                {shutdown_task, trigger_task},
                timeout=seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            if shutdown_task in done:
                return True

            if trigger_task in done:
                self._trigger_event.clear()
                return False

            # Timeout - normal completion
            return False
        except asyncio.CancelledError:
            shutdown_task.cancel()
            trigger_task.cancel()
            raise

    async def _ensure_db_connection(self) -> bool:
        """
        Ensure database connection is healthy and attempt reconnection if needed.

        Checks database state and calls reconnect() if degraded or disconnected.
        Sends alert on successful reconnection.

        Returns:
            True if the database is connected (or reconnection succeeded),
            False if reconnection failed or an exception occurred.
        """
        db_state = self.db.state

        if db_state in (DatabaseState.DEGRADED, DatabaseState.DISCONNECTED):
            logger.warning(f"Database in {db_state.value} state - attempting reconnection")

            try:
                reconnected = await self.db.reconnect()
                if reconnected:
                    logger.info("Database reconnection successful")
                    await send_alert_safe(
                        alert_service=self.services.workflow.alert_service,
                        message="Database connection restored",
                        severity=AlertSeverity.INFO,
                        metadata={"previous_state": db_state.value, "new_state": self.db.state.value},
                    )
                    return True
                else:
                    logger.error("Database reconnection failed")
                    return False
            except Exception as e:
                logger.error(f"Error during database reconnection: {e}")
                return False

        return True

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
        await send_alert_safe(
            alert_service=self.services.workflow.alert_service,
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
        """Main bot loop using session orchestrator with account pool."""
        while self.running and not self.shutdown_event.is_set():
            try:
                # Check circuit breaker
                if not await self.circuit_breaker.can_execute():
                    if await self._handle_circuit_breaker_open():
                        break
                    continue

                # Check if browser needs restart for memory management
                if await self.browser_manager.should_restart():
                    await self.browser_manager.restart_fresh()

                # Ensure database connection is healthy
                db_healthy = await self._ensure_db_connection()
                if not db_healthy:
                    logger.warning("Database not available - skipping iteration")
                    await send_alert_safe(
                        alert_service=self.services.workflow.alert_service,
                        message="Database connection unavailable - waiting before retry",
                        severity=AlertSeverity.WARNING,
                        metadata={"db_state": self.db.state.value},
                    )
                    if await self._wait_or_shutdown(Intervals.ERROR_RECOVERY):
                        break
                    continue

                # Load accounts from pool (initialization check)
                account_count = await self.account_pool.load_accounts()

                if account_count == 0:
                    logger.warning("No available accounts in pool - waiting before retry")
                    # Wait for accounts to become available or cooldown to expire
                    wait_success = await self.account_pool.wait_for_available_account(
                        timeout=AccountPoolConfig.WAIT_FOR_ACCOUNT_TIMEOUT
                    )
                    if not wait_success:
                        # Still no accounts - wait adaptive interval
                        if await self._wait_adaptive_interval():
                            break
                        continue

                # Run one session cycle
                logger.info("Starting session cycle...")
                session_summary = await self.session_orchestrator.run_session()

                # Log session summary
                logger.info(
                    f"Session {session_summary['session_number']} completed: "
                    f"{session_summary['missions_processed']} mission(s) processed"
                )

                # Record success for circuit breaker
                await self.circuit_breaker.record_success()

                # Get pool status for monitoring
                pool_status = await self.account_pool.get_pool_status()
                logger.info(
                    f"Pool status: {pool_status['available']} available, "
                    f"{pool_status['in_cooldown']} in cooldown, "
                    f"{pool_status['quarantined']} quarantined"
                )

                # Wait before next session
                if await self._wait_adaptive_interval():
                    break

            except Exception as e:
                logger.error(f"Error in bot loop: {e}", exc_info=True)
                await self.notifier.notify_error("Bot Loop Error", str(e))
                await self.circuit_breaker.record_failure()

                # Record circuit breaker trip in metrics if it just opened
                await self._record_circuit_breaker_trip()

                # Send alert for bot loop error (ERROR severity)
                await send_alert_safe(
                    alert_service=self.services.workflow.alert_service,
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
