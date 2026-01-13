"""Tests for metrics tracking."""

import pytest
import pytest_asyncio
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.metrics import BotMetrics, get_metrics, MetricsSnapshot


@pytest_asyncio.fixture
async def metrics():
    """Create a test metrics instance."""
    return BotMetrics(retention_minutes=60)


@pytest.mark.asyncio
async def test_metrics_initialization(metrics):
    """Test metrics initialization."""
    assert metrics.total_checks == 0
    assert metrics.slots_found == 0
    assert metrics.appointments_booked == 0
    assert metrics.total_errors == 0
    assert metrics.circuit_breaker_trips == 0
    assert metrics.captchas_solved == 0
    assert metrics.active_users == 0
    assert metrics.current_status == "idle"


@pytest.mark.asyncio
async def test_record_check(metrics):
    """Test recording a check operation."""
    await metrics.record_check(user_id=1, duration_ms=150.0)

    assert metrics.total_checks == 1
    assert len(metrics.response_times) == 1
    assert metrics.response_times[0] == 150.0
    assert len(metrics.check_timestamps) == 1


@pytest.mark.asyncio
async def test_record_multiple_checks(metrics):
    """Test recording multiple check operations."""
    for i in range(5):
        await metrics.record_check(user_id=1, duration_ms=100.0 + i * 10)

    assert metrics.total_checks == 5
    assert len(metrics.response_times) == 5


@pytest.mark.asyncio
async def test_record_slot_found(metrics):
    """Test recording a slot found event."""
    await metrics.record_slot_found(user_id=1, centre="Istanbul")

    assert metrics.slots_found == 1


@pytest.mark.asyncio
async def test_record_appointment_booked(metrics):
    """Test recording an appointment booked event."""
    await metrics.record_appointment_booked(user_id=1)

    assert metrics.appointments_booked == 1


@pytest.mark.asyncio
async def test_record_error(metrics):
    """Test recording an error."""
    await metrics.record_error(user_id=1, error_type="ConnectionError")

    assert metrics.total_errors == 1
    assert metrics.errors_by_type["ConnectionError"] == 1
    assert metrics.errors_by_user[1] == 1


@pytest.mark.asyncio
async def test_record_error_without_user_id(metrics):
    """Test recording an error without user ID."""
    await metrics.record_error(user_id=None, error_type="SystemError")

    assert metrics.total_errors == 1
    assert metrics.errors_by_type["SystemError"] == 1


@pytest.mark.asyncio
async def test_record_multiple_error_types(metrics):
    """Test recording multiple error types."""
    await metrics.record_error(user_id=1, error_type="ConnectionError")
    await metrics.record_error(user_id=1, error_type="TimeoutError")
    await metrics.record_error(user_id=2, error_type="ConnectionError")

    assert metrics.total_errors == 3
    assert metrics.errors_by_type["ConnectionError"] == 2
    assert metrics.errors_by_type["TimeoutError"] == 1
    assert metrics.errors_by_user[1] == 2
    assert metrics.errors_by_user[2] == 1


@pytest.mark.asyncio
async def test_record_circuit_breaker_trip(metrics):
    """Test recording a circuit breaker trip."""
    await metrics.record_circuit_breaker_trip()

    assert metrics.circuit_breaker_trips == 1


@pytest.mark.asyncio
async def test_record_captcha_solved(metrics):
    """Test recording a solved captcha."""
    await metrics.record_captcha_solved()

    assert metrics.captchas_solved == 1


@pytest.mark.asyncio
async def test_set_active_users(metrics):
    """Test setting active users count."""
    await metrics.set_active_users(5)

    assert metrics.active_users == 5


@pytest.mark.asyncio
async def test_set_status(metrics):
    """Test setting bot status."""
    await metrics.set_status("running")

    assert metrics.current_status == "running"


def test_get_success_rate_zero_checks(metrics):
    """Test success rate with zero checks."""
    rate = metrics.get_success_rate()
    assert rate == 0.0


@pytest.mark.asyncio
async def test_get_success_rate_all_successful(metrics):
    """Test success rate with all successful checks."""
    for i in range(10):
        await metrics.record_check(user_id=1, duration_ms=100.0)

    rate = metrics.get_success_rate()
    assert rate == 100.0


@pytest.mark.asyncio
async def test_get_success_rate_with_errors(metrics):
    """Test success rate with some errors."""
    for i in range(10):
        await metrics.record_check(user_id=1, duration_ms=100.0)

    for i in range(2):
        await metrics.record_error(user_id=1, error_type="TestError")

    rate = metrics.get_success_rate()
    assert rate == 80.0  # 8 successful out of 10


def test_get_requests_per_minute_empty(metrics):
    """Test requests per minute with no requests."""
    rpm = metrics.get_requests_per_minute()
    assert rpm == 0.0


@pytest.mark.asyncio
async def test_get_requests_per_minute_recent(metrics):
    """Test requests per minute with recent requests."""
    # Simulate 5 checks
    for i in range(5):
        await metrics.record_check(user_id=1, duration_ms=100.0)

    rpm = metrics.get_requests_per_minute()
    assert rpm >= 5.0  # At least 5 requests


def test_get_avg_response_time_empty(metrics):
    """Test average response time with no requests."""
    avg = metrics.get_avg_response_time_ms()
    assert avg == 0.0


@pytest.mark.asyncio
async def test_get_avg_response_time(metrics):
    """Test average response time calculation."""
    await metrics.record_check(user_id=1, duration_ms=100.0)
    await metrics.record_check(user_id=1, duration_ms=200.0)
    await metrics.record_check(user_id=1, duration_ms=300.0)

    avg = metrics.get_avg_response_time_ms()
    assert avg == 200.0  # (100 + 200 + 300) / 3


@pytest.mark.asyncio
async def test_get_snapshot(metrics):
    """Test getting metrics snapshot."""
    await metrics.record_check(user_id=1, duration_ms=150.0)
    await metrics.record_slot_found(user_id=1, centre="Istanbul")
    await metrics.record_appointment_booked(user_id=1)
    await metrics.set_active_users(3)
    await metrics.set_status("running")

    snapshot = await metrics.get_snapshot()

    assert isinstance(snapshot, MetricsSnapshot)
    assert snapshot.total_checks == 1
    assert snapshot.slots_found == 1
    assert snapshot.appointments_booked == 1
    assert snapshot.active_users == 3
    assert snapshot.uptime_seconds > 0


@pytest.mark.asyncio
async def test_get_snapshot_stores_in_history(metrics):
    """Test that snapshots are stored in history."""
    initial_count = len(metrics.snapshots)
    await metrics.get_snapshot()
    assert len(metrics.snapshots) == initial_count + 1


@pytest.mark.asyncio
async def test_get_metrics_dict(metrics):
    """Test getting metrics as dictionary."""
    await metrics.record_check(user_id=1, duration_ms=150.0)
    await metrics.record_error(user_id=1, error_type="TestError")
    await metrics.record_captcha_solved()

    metrics_dict = await metrics.get_metrics_dict()

    assert "current" in metrics_dict
    assert "status" in metrics_dict
    assert "errors" in metrics_dict
    assert "captchas_solved" in metrics_dict

    assert metrics_dict["status"] == "idle"
    assert metrics_dict["captchas_solved"] == 1
    assert "by_type" in metrics_dict["errors"]
    assert "by_user" in metrics_dict["errors"]


@pytest.mark.asyncio
async def test_get_prometheus_metrics(metrics):
    """Test getting Prometheus formatted metrics."""
    await metrics.record_check(user_id=1, duration_ms=150.0)
    await metrics.record_slot_found(user_id=1, centre="Istanbul")

    prometheus_output = await metrics.get_prometheus_metrics()

    assert isinstance(prometheus_output, str)
    assert "vfs_bot_uptime_seconds" in prometheus_output
    assert "vfs_bot_checks_total" in prometheus_output
    assert "vfs_bot_slots_found_total" in prometheus_output
    assert "vfs_bot_appointments_booked_total" in prometheus_output
    assert "vfs_bot_errors_total" in prometheus_output
    assert "vfs_bot_success_rate" in prometheus_output
    assert "# HELP" in prometheus_output
    assert "# TYPE" in prometheus_output


@pytest.mark.asyncio
async def test_prometheus_metrics_format(metrics):
    """Test Prometheus metrics format validity."""
    await metrics.record_check(user_id=1, duration_ms=100.0)
    prometheus_output = await metrics.get_prometheus_metrics()

    lines = prometheus_output.strip().split("\n")

    # Check for help and type comments
    help_lines = [line for line in lines if line.startswith("# HELP")]
    type_lines = [line for line in lines if line.startswith("# TYPE")]

    assert len(help_lines) > 0
    assert len(type_lines) > 0


@pytest.mark.asyncio
async def test_metrics_thread_safety(metrics):
    """Test metrics recording with concurrent operations."""
    import asyncio

    async def record_operations():
        for i in range(10):
            await metrics.record_check(user_id=1, duration_ms=100.0)

    # Run multiple tasks concurrently
    await asyncio.gather(record_operations(), record_operations(), record_operations())

    assert metrics.total_checks == 30


@pytest.mark.asyncio
async def test_get_metrics_singleton():
    """Test get_metrics returns singleton instance."""
    metrics1 = await get_metrics()
    metrics2 = await get_metrics()

    assert metrics1 is metrics2


@pytest.mark.asyncio
async def test_metrics_snapshot_dataclass():
    """Test MetricsSnapshot dataclass fields."""
    snapshot = MetricsSnapshot(
        timestamp="2024-01-15T10:00:00",
        uptime_seconds=100.0,
        total_checks=10,
        slots_found=2,
        appointments_booked=1,
        total_errors=0,
        success_rate=100.0,
        requests_per_minute=5.0,
        avg_response_time_ms=150.0,
        circuit_breaker_trips=0,
        active_users=3,
    )

    assert snapshot.timestamp == "2024-01-15T10:00:00"
    assert snapshot.total_checks == 10
    assert snapshot.slots_found == 2
    assert snapshot.appointments_booked == 1


@pytest.mark.asyncio
async def test_response_times_deque_limit(metrics):
    """Test that response times deque respects max length."""
    # Record more than maxlen (1000)
    for i in range(1500):
        await metrics.record_check(user_id=1, duration_ms=100.0)

    # Should only keep last 1000
    assert len(metrics.response_times) == 1000
    assert len(metrics.check_timestamps) == 1000
