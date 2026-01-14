"""Prometheus metrics for monitoring."""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

# Counters
slots_checked_total = Counter(
    'vfs_slots_checked_total',
    'Total number of slot checks performed',
    ['centre', 'category']
)

slots_found_total = Counter(
    'vfs_slots_found_total',
    'Total number of available slots found',
    ['centre']
)

bookings_total = Counter(
    'vfs_bookings_total',
    'Total number of booking attempts',
    ['centre', 'status']
)

errors_total = Counter(
    'vfs_errors_total',
    'Total number of errors',
    ['error_type']
)

captchas_solved_total = Counter(
    'vfs_captchas_solved_total',
    'Total captchas solved',
    ['provider', 'status']
)

# Histograms
slot_check_duration = Histogram(
    'vfs_slot_check_duration_seconds',
    'Time spent checking for slots',
    buckets=[1, 2, 5, 10, 30, 60, 120]
)

booking_duration = Histogram(
    'vfs_booking_duration_seconds',
    'Time spent on booking process',
    buckets=[5, 10, 30, 60, 120, 300]
)

# Gauges
active_users_gauge = Gauge(
    'vfs_active_users',
    'Number of active users being monitored'
)

bot_running_gauge = Gauge(
    'vfs_bot_running',
    'Whether the bot is currently running (1=running, 0=stopped)'
)

circuit_breaker_open_gauge = Gauge(
    'vfs_circuit_breaker_open',
    'Whether circuit breaker is open (1=open, 0=closed)'
)


def get_metrics_response() -> Response:
    """Generate Prometheus metrics response."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
