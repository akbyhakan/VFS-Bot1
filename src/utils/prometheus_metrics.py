"""Prometheus metrics integration for VFS-Bot."""

from loguru import logger
from prometheus_client import REGISTRY, Counter, Gauge, Histogram, generate_latest

from src.core.enums import MetricsStatus, SlotCheckStatus

# Slot checking metrics
SLOT_CHECKS_TOTAL = Counter(
    "vfs_slot_checks_total",
    "Total number of slot checks performed",
    ["centre", "status"],
    registry=REGISTRY,
)

# Booking metrics
BOOKING_SUCCESS = Counter(
    "vfs_bookings_success_total",
    "Total number of successful bookings",
    ["centre"],
    registry=REGISTRY,
)

BOOKING_FAILED = Counter(
    "vfs_bookings_failed_total",
    "Total number of failed bookings",
    ["centre", "reason"],
    registry=REGISTRY,
)

# Response time metrics
RESPONSE_TIME = Histogram(
    "vfs_response_time_seconds",
    "Response time for VFS operations",
    ["operation"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    registry=REGISTRY,
)

# Active users gauge
ACTIVE_USERS = Gauge(
    "vfs_active_users", "Currently active users being monitored", registry=REGISTRY
)

# Circuit breaker state
CIRCUIT_BREAKER_STATE = Gauge(
    "vfs_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open)",
    ["service"],
    registry=REGISTRY,
)

# HTTP request metrics
HTTP_REQUESTS_TOTAL = Counter(
    "vfs_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=REGISTRY,
)

# Database metrics
DB_CONNECTIONS_ACTIVE = Gauge(
    "vfs_db_connections_active", "Number of active database connections", registry=REGISTRY
)

DB_QUERIES_TOTAL = Counter(
    "vfs_db_queries_total",
    "Total number of database queries",
    ["operation", "status"],
    registry=REGISTRY,
)

DB_QUERY_DURATION = Histogram(
    "vfs_db_query_duration_seconds",
    "Database query duration",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
    registry=REGISTRY,
)

# OTP metrics
OTP_RECEIVED_TOTAL = Counter(
    "vfs_otp_received_total", "Total OTPs received via webhook", ["type"], registry=REGISTRY
)

OTP_WAIT_DURATION = Histogram(
    "vfs_otp_wait_duration_seconds",
    "Time waiting for OTP to arrive",
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
    registry=REGISTRY,
)

# Payment metrics
PAYMENT_ATTEMPTS_TOTAL = Counter(
    "vfs_payment_attempts_total", "Total payment attempts", ["method", "status"], registry=REGISTRY
)

# Captcha solving metrics
CAPTCHA_SOLVED_TOTAL = Counter(
    "vfs_captcha_solved_total", "Total captchas solved", ["solver", "status"], registry=REGISTRY
)

CAPTCHA_SOLVE_DURATION = Histogram(
    "vfs_captcha_solve_duration_seconds",
    "Time to solve captcha",
    ["solver"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0),
    registry=REGISTRY,
)

# Error metrics
ERRORS_TOTAL = Counter(
    "vfs_errors_total", "Total errors by type", ["error_type", "component"], registry=REGISTRY
)

# Bot state metrics
BOT_RUNNING = Gauge(
    "vfs_bot_running", "Bot running state (1=running, 0=stopped)", registry=REGISTRY
)

BOT_UPTIME_SECONDS = Gauge("vfs_bot_uptime_seconds", "Bot uptime in seconds", registry=REGISTRY)


class MetricsHelper:
    """Helper class for common metrics operations."""

    @staticmethod
    def record_slot_check(centre: str, found: bool) -> None:
        """
        Record a slot check operation.

        Args:
            centre: VFS centre name
            found: Whether slot was found
        """
        status = SlotCheckStatus.FOUND if found else SlotCheckStatus.NOT_FOUND
        SLOT_CHECKS_TOTAL.labels(centre=centre, status=status.value).inc()

    @staticmethod
    def record_booking_success(centre: str) -> None:
        """
        Record a successful booking.

        Args:
            centre: VFS centre name
        """
        BOOKING_SUCCESS.labels(centre=centre).inc()

    @staticmethod
    def record_booking_failure(centre: str, reason: str) -> None:
        """
        Record a failed booking.

        Args:
            centre: VFS centre name
            reason: Failure reason
        """
        BOOKING_FAILED.labels(centre=centre, reason=reason).inc()

    @staticmethod
    def set_active_users(count: int) -> None:
        """
        Set the number of active users.

        Args:
            count: Number of active users
        """
        ACTIVE_USERS.set(count)

    @staticmethod
    def set_circuit_breaker_state(service: str, is_open: bool) -> None:
        """
        Set circuit breaker state.

        Args:
            service: Service name
            is_open: Whether circuit breaker is open
        """
        CIRCUIT_BREAKER_STATE.labels(service=service).set(1 if is_open else 0)

    @staticmethod
    def record_http_request(method: str, endpoint: str, status: int) -> None:
        """
        Record an HTTP request.

        Args:
            method: HTTP method
            endpoint: API endpoint
            status: HTTP status code
        """
        HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status=str(status)).inc()

    @staticmethod
    def record_db_query(operation: str, duration: float, success: bool) -> None:
        """
        Record a database query.

        Args:
            operation: Query operation type
            duration: Query duration in seconds
            success: Whether query was successful
        """
        status = MetricsStatus.SUCCESS if success else MetricsStatus.FAILED
        DB_QUERIES_TOTAL.labels(operation=operation, status=status.value).inc()
        DB_QUERY_DURATION.labels(operation=operation).observe(duration)

    @staticmethod
    def set_db_connections(count: int) -> None:
        """
        Set active database connections count.

        Args:
            count: Number of active connections
        """
        DB_CONNECTIONS_ACTIVE.set(count)

    @staticmethod
    def record_otp_received(otp_type: str) -> None:
        """
        Record OTP received.

        Args:
            otp_type: Type of OTP (appointment, payment)
        """
        OTP_RECEIVED_TOTAL.labels(type=otp_type).inc()

    @staticmethod
    def record_otp_wait(duration: float) -> None:
        """
        Record OTP wait time.

        Args:
            duration: Wait duration in seconds
        """
        OTP_WAIT_DURATION.observe(duration)

    @staticmethod
    def record_payment_attempt(method: str, success: bool) -> None:
        """
        Record payment attempt.

        Args:
            method: Payment method
            success: Whether payment was successful
        """
        status = MetricsStatus.SUCCESS if success else MetricsStatus.FAILED
        PAYMENT_ATTEMPTS_TOTAL.labels(method=method, status=status.value).inc()

    @staticmethod
    def record_captcha_solved(solver: str, duration: float, success: bool) -> None:
        """
        Record captcha solving.

        Args:
            solver: Captcha solver used
            duration: Time to solve in seconds
            success: Whether solving was successful
        """
        status = MetricsStatus.SUCCESS if success else MetricsStatus.FAILED
        CAPTCHA_SOLVED_TOTAL.labels(solver=solver, status=status.value).inc()
        CAPTCHA_SOLVE_DURATION.labels(solver=solver).observe(duration)

    @staticmethod
    def record_error(error_type: str, component: str) -> None:
        """
        Record an error.

        Args:
            error_type: Type of error
            component: Component where error occurred
        """
        ERRORS_TOTAL.labels(error_type=error_type, component=component).inc()

    @staticmethod
    def set_bot_running(is_running: bool) -> None:
        """
        Set bot running state.

        Args:
            is_running: Whether bot is running
        """
        BOT_RUNNING.set(1 if is_running else 0)

    @staticmethod
    def set_bot_uptime(seconds: float) -> None:
        """
        Set bot uptime.

        Args:
            seconds: Uptime in seconds
        """
        BOT_UPTIME_SECONDS.set(seconds)


def get_metrics() -> bytes:
    """
    Get Prometheus metrics in text format.

    Returns:
        Metrics in Prometheus exposition format
    """
    result: bytes = generate_latest(REGISTRY)
    return result


# Initialize metrics helper
metrics_helper = MetricsHelper()

logger.info("Prometheus metrics initialized")
