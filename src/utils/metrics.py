"""Metrics tracking for VFS-Bot performance monitoring."""

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from loguru import logger


@dataclass
class MetricsSnapshot:
    """Snapshot of metrics at a point in time."""

    timestamp: str
    uptime_seconds: float
    total_checks: int
    slots_found: int
    appointments_booked: int
    total_errors: int
    success_rate: float
    requests_per_minute: float
    avg_response_time_ms: float
    circuit_breaker_trips: int
    active_users: int


class BotMetrics:
    """Track and expose bot performance metrics."""

    def __init__(self, retention_minutes: int = 60):
        """
        Initialize metrics tracker.

        Args:
            retention_minutes: How long to keep detailed metrics
        """
        self.start_time = time.time()
        self.retention_minutes = retention_minutes
        self._lock = asyncio.Lock()

        # Counters
        self.total_checks = 0
        self.slots_found = 0
        self.appointments_booked = 0
        self.total_errors = 0
        self.circuit_breaker_trips = 0
        self.captchas_solved = 0

        # Error breakdown
        self.errors_by_type: Dict[str, int] = defaultdict(int)
        self.errors_by_user: Dict[int, int] = defaultdict(int)

        # Timing data
        self.response_times: deque = deque(maxlen=1000)  # Last 1000 requests
        self.check_timestamps: deque = deque(maxlen=1000)  # Last 1000 checks

        # Active state
        self.active_users = 0
        self.current_status = "idle"  # idle, running, paused, error

        # Historical snapshots
        self.snapshots: deque = deque(maxlen=retention_minutes)

        logger.info(f"Metrics tracking initialized (retention: {retention_minutes}m)")

    async def record_check(self, user_id: int, duration_ms: float, centre: str = "unknown") -> None:
        """
        Record a slot check operation.

        Args:
            user_id: User ID
            duration_ms: Duration in milliseconds
            centre: VFS centre name (default: "unknown")
        """
        async with self._lock:
            self.total_checks += 1
            self.response_times.append(duration_ms)
            self.check_timestamps.append(time.time())

        # Update Prometheus metrics
        from .prometheus_metrics import RESPONSE_TIME, MetricsHelper

        MetricsHelper.record_slot_check(centre=centre, found=False)
        RESPONSE_TIME.labels(operation="slot_check").observe(duration_ms / 1000.0)

    async def record_slot_found(self, user_id: int, centre: str) -> None:
        """
        Record a slot found event.

        Args:
            user_id: User ID
            centre: VFS centre name
        """
        async with self._lock:
            self.slots_found += 1
        logger.info(f"📊 Metrics: Slot found for user {user_id} at {centre}")

        # Update Prometheus metrics
        from .prometheus_metrics import MetricsHelper

        MetricsHelper.record_slot_check(centre=centre, found=True)

    async def record_appointment_booked(self, user_id: int, centre: str = "unknown") -> None:
        """
        Record a successful booking.

        Args:
            user_id: User ID
            centre: VFS centre name
        """
        async with self._lock:
            self.appointments_booked += 1
        logger.info(f"📊 Metrics: Appointment booked for user {user_id}")

        # Update Prometheus metrics
        from .prometheus_metrics import MetricsHelper

        MetricsHelper.record_booking_success(centre=centre)

    async def record_error(self, user_id: Optional[int], error_type: str, component: str = "bot") -> None:
        """
        Record an error.

        Args:
            user_id: User ID (if applicable)
            error_type: Type of error
            component: Component where error occurred
        """
        async with self._lock:
            self.total_errors += 1
            self.errors_by_type[error_type] += 1
            if user_id:
                self.errors_by_user[user_id] += 1

        # Update Prometheus metrics
        from .prometheus_metrics import MetricsHelper

        MetricsHelper.record_error(error_type=error_type, component=component)

    async def record_circuit_breaker_trip(self) -> None:
        """Record circuit breaker opening."""
        async with self._lock:
            self.circuit_breaker_trips += 1
        logger.warning("📊 Metrics: Circuit breaker tripped")

    async def record_captcha_solved(self) -> None:
        """Record a solved captcha."""
        async with self._lock:
            self.captchas_solved += 1

    async def batch_update(self, updates: Dict[str, int]) -> None:
        """
        Batch update multiple metrics atomically.

        Args:
            updates: Dictionary of metric names to increment values

        Example:
            await metrics.batch_update({
                "total_checks": 1,
                "slots_found": 1,
                "total_errors": 0
            })
        """
        async with self._lock:
            for key, value in updates.items():
                if hasattr(self, key) and isinstance(getattr(self, key), int):
                    setattr(self, key, getattr(self, key) + value)

    async def set_active_users(self, count: int) -> None:
        """
        Set number of active users.

        Args:
            count: Active user count
        """
        async with self._lock:
            self.active_users = count

        # Update Prometheus metrics
        from .prometheus_metrics import MetricsHelper

        MetricsHelper.set_active_users(count)

    async def set_status(self, status: str) -> None:
        """
        Set bot status.

        Args:
            status: Status string (idle, running, paused, error)
        """
        async with self._lock:
            self.current_status = status

    def get_success_rate(self) -> float:
        """
        Calculate success rate (thread-safe read-only).

        Returns:
            Success rate as percentage (0-100)
        """
        # Note: This is a read-only operation on integers, which are atomic in Python
        # For critical accuracy, wrap in async with self._lock if needed
        total = self.total_checks
        if total == 0:
            return 0.0
        errors = self.total_errors
        return (total - errors) / total * 100

    def get_requests_per_minute(self) -> float:
        """
        Calculate current requests per minute (thread-safe read-only).

        Returns:
            Requests per minute
        """
        # Note: deque operations are thread-safe for this use case
        if not self.check_timestamps:
            return 0.0

        current_time = time.time()
        minute_ago = current_time - 60

        # Count requests in last minute
        recent = sum(1 for ts in self.check_timestamps if ts > minute_ago)
        return float(recent)

    def get_avg_response_time_ms(self) -> float:
        """
        Get average response time (thread-safe read-only).

        Returns:
            Average response time in milliseconds
        """
        # Note: deque operations are thread-safe for this use case
        response_times = list(self.response_times)  # Snapshot
        if not response_times:
            return 0.0
        return float(sum(response_times) / len(response_times))

    async def get_snapshot(self) -> MetricsSnapshot:
        """
        Get current metrics snapshot.

        Returns:
            MetricsSnapshot object
        """
        async with self._lock:
            uptime = time.time() - self.start_time

            snapshot = MetricsSnapshot(
                timestamp=datetime.now(timezone.utc).isoformat(),
                uptime_seconds=uptime,
                total_checks=self.total_checks,
                slots_found=self.slots_found,
                appointments_booked=self.appointments_booked,
                total_errors=self.total_errors,
                success_rate=self.get_success_rate(),
                requests_per_minute=self.get_requests_per_minute(),
                avg_response_time_ms=self.get_avg_response_time_ms(),
                circuit_breaker_trips=self.circuit_breaker_trips,
                active_users=self.active_users,
            )

            # Store snapshot
            self.snapshots.append(snapshot)

            return snapshot

    async def get_metrics_dict(self) -> Dict[str, Any]:
        """
        Get metrics as dictionary (for API responses).

        Returns:
            Metrics dictionary
        """
        snapshot = await self.get_snapshot()

        async with self._lock:
            return {
                "current": asdict(snapshot),
                "status": self.current_status,
                "errors": {
                    "by_type": dict(self.errors_by_type),
                    "by_user": dict(self.errors_by_user),
                },
                "captchas_solved": self.captchas_solved,
            }

    async def get_prometheus_metrics(self) -> str:
        """
        Get metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics string
        """
        snapshot = await self.get_snapshot()

        metrics = [
            "# HELP vfs_bot_uptime_seconds Bot uptime in seconds",
            "# TYPE vfs_bot_uptime_seconds gauge",
            f"vfs_bot_uptime_seconds {snapshot.uptime_seconds}",
            "",
            "# HELP vfs_bot_checks_total Total slot checks performed",
            "# TYPE vfs_bot_checks_total counter",
            f"vfs_bot_checks_total {snapshot.total_checks}",
            "",
            "# HELP vfs_bot_slots_found_total Total slots found",
            "# TYPE vfs_bot_slots_found_total counter",
            f"vfs_bot_slots_found_total {snapshot.slots_found}",
            "",
            "# HELP vfs_bot_appointments_booked_total Total appointments booked",
            "# TYPE vfs_bot_appointments_booked_total counter",
            f"vfs_bot_appointments_booked_total {snapshot.appointments_booked}",
            "",
            "# HELP vfs_bot_errors_total Total errors encountered",
            "# TYPE vfs_bot_errors_total counter",
            f"vfs_bot_errors_total {snapshot.total_errors}",
            "",
            "# HELP vfs_bot_success_rate Success rate percentage",
            "# TYPE vfs_bot_success_rate gauge",
            f"vfs_bot_success_rate {snapshot.success_rate}",
            "",
            "# HELP vfs_bot_requests_per_minute Current requests per minute",
            "# TYPE vfs_bot_requests_per_minute gauge",
            f"vfs_bot_requests_per_minute {snapshot.requests_per_minute}",
            "",
            "# HELP vfs_bot_avg_response_time_ms Average response time in milliseconds",
            "# TYPE vfs_bot_avg_response_time_ms gauge",
            f"vfs_bot_avg_response_time_ms {snapshot.avg_response_time_ms}",
            "",
            "# HELP vfs_bot_circuit_breaker_trips_total Circuit breaker trips",
            "# TYPE vfs_bot_circuit_breaker_trips_total counter",
            f"vfs_bot_circuit_breaker_trips_total {snapshot.circuit_breaker_trips}",
            "",
            "# HELP vfs_bot_active_users Current active users",
            "# TYPE vfs_bot_active_users gauge",
            f"vfs_bot_active_users {snapshot.active_users}",
            "",
        ]

        return "\n".join(metrics)


# Global metrics instance
_metrics_instance: Optional[BotMetrics] = None
_metrics_lock = asyncio.Lock()


async def get_metrics() -> BotMetrics:
    """
    Get global metrics instance (singleton, thread-safe).

    Returns:
        BotMetrics instance
    """
    global _metrics_instance
    if _metrics_instance is None:
        async with _metrics_lock:
            # Double-check pattern for thread safety
            if _metrics_instance is None:
                _metrics_instance = BotMetrics()
    return _metrics_instance
