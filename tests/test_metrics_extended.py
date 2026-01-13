"""Extended tests for metrics.py - Target 97% coverage."""

import pytest
import time
from datetime import datetime, timezone
from unittest.mock import patch

from src.utils.metrics import BotMetrics, MetricsSnapshot, get_metrics


@pytest.mark.asyncio
async def test_bot_metrics_initialization():
    """Test BotMetrics initialization."""
    metrics = BotMetrics(retention_minutes=30)
    assert metrics.retention_minutes == 30
    assert metrics.total_checks == 0
    assert metrics.slots_found == 0
    assert metrics.appointments_booked == 0
    assert metrics.total_errors == 0
    assert metrics.circuit_breaker_trips == 0
    assert metrics.captchas_solved == 0
    assert metrics.active_users == 0
    assert metrics.current_status == "idle"


@pytest.mark.asyncio
async def test_record_check():
    """Test recording a slot check."""
    metrics = BotMetrics()
    await metrics.record_check(user_id=1, duration_ms=150.5)
    assert metrics.total_checks == 1
    assert len(metrics.response_times) == 1
    assert metrics.response_times[0] == 150.5
    assert len(metrics.check_timestamps) == 1


@pytest.mark.asyncio
async def test_record_multiple_checks():
    """Test recording multiple checks."""
    metrics = BotMetrics()
    for i in range(5):
        await metrics.record_check(user_id=1, duration_ms=100.0 + i)
    assert metrics.total_checks == 5
    assert len(metrics.response_times) == 5


@pytest.mark.asyncio
async def test_record_slot_found():
    """Test recording a slot found event."""
    metrics = BotMetrics()
    await metrics.record_slot_found(user_id=1, centre="Istanbul")
    assert metrics.slots_found == 1

    await metrics.record_slot_found(user_id=2, centre="Ankara")
    assert metrics.slots_found == 2


@pytest.mark.asyncio
async def test_record_appointment_booked():
    """Test recording an appointment booking."""
    metrics = BotMetrics()
    await metrics.record_appointment_booked(user_id=1)
    assert metrics.appointments_booked == 1

    await metrics.record_appointment_booked(user_id=2)
    assert metrics.appointments_booked == 2


@pytest.mark.asyncio
async def test_record_error():
    """Test recording errors."""
    metrics = BotMetrics()
    await metrics.record_error(user_id=1, error_type="LoginError")
    assert metrics.total_errors == 1
    assert metrics.errors_by_type["LoginError"] == 1
    assert metrics.errors_by_user[1] == 1

    await metrics.record_error(user_id=1, error_type="NetworkError")
    assert metrics.total_errors == 2
    assert metrics.errors_by_type["NetworkError"] == 1
    assert metrics.errors_by_user[1] == 2


@pytest.mark.asyncio
async def test_record_error_without_user_id():
    """Test recording errors without user ID."""
    metrics = BotMetrics()
    await metrics.record_error(user_id=None, error_type="SystemError")
    assert metrics.total_errors == 1
    assert metrics.errors_by_type["SystemError"] == 1
    assert len(metrics.errors_by_user) == 0


@pytest.mark.asyncio
async def test_record_circuit_breaker_trip():
    """Test recording circuit breaker trips."""
    metrics = BotMetrics()
    await metrics.record_circuit_breaker_trip()
    assert metrics.circuit_breaker_trips == 1

    await metrics.record_circuit_breaker_trip()
    assert metrics.circuit_breaker_trips == 2


@pytest.mark.asyncio
async def test_record_captcha_solved():
    """Test recording captcha solutions."""
    metrics = BotMetrics()
    await metrics.record_captcha_solved()
    assert metrics.captchas_solved == 1

    await metrics.record_captcha_solved()
    assert metrics.captchas_solved == 2


@pytest.mark.asyncio
async def test_set_active_users():
    """Test setting active users count."""
    metrics = BotMetrics()
    await metrics.set_active_users(5)
    assert metrics.active_users == 5

    await metrics.set_active_users(10)
    assert metrics.active_users == 10


@pytest.mark.asyncio
async def test_set_status():
    """Test setting bot status."""
    metrics = BotMetrics()
    await metrics.set_status("running")
    assert metrics.current_status == "running"

    await metrics.set_status("paused")
    assert metrics.current_status == "paused"


def test_get_success_rate_no_checks():
    """Test success rate with no checks."""
    metrics = BotMetrics()
    assert metrics.get_success_rate() == 0.0


@pytest.mark.asyncio
async def test_get_success_rate_with_errors():
    """Test success rate calculation with errors."""
    metrics = BotMetrics()
    await metrics.record_check(user_id=1, duration_ms=100.0)
    await metrics.record_check(user_id=1, duration_ms=100.0)
    await metrics.record_check(user_id=1, duration_ms=100.0)
    await metrics.record_error(user_id=1, error_type="TestError")

    # 3 checks, 1 error = (3-1)/3 * 100 = 66.67%
    assert abs(metrics.get_success_rate() - 66.67) < 0.01


@pytest.mark.asyncio
async def test_get_success_rate_no_errors():
    """Test success rate with no errors."""
    metrics = BotMetrics()
    await metrics.record_check(user_id=1, duration_ms=100.0)
    await metrics.record_check(user_id=1, duration_ms=100.0)
    assert metrics.get_success_rate() == 100.0


def test_get_requests_per_minute_no_requests():
    """Test requests per minute with no requests."""
    metrics = BotMetrics()
    assert metrics.get_requests_per_minute() == 0.0


@pytest.mark.asyncio
async def test_get_requests_per_minute_with_requests():
    """Test requests per minute calculation."""
    metrics = BotMetrics()
    # Add some requests
    current_time = time.time()
    for i in range(5):
        await metrics.record_check(user_id=1, duration_ms=100.0)
    # All requests are recent (within last minute)
    assert metrics.get_requests_per_minute() == 5.0


@pytest.mark.asyncio
async def test_get_requests_per_minute_old_requests():
    """Test requests per minute with old requests."""
    metrics = BotMetrics()
    # Simulate old timestamps (more than 60 seconds ago)
    old_time = time.time() - 120
    metrics.check_timestamps.append(old_time)
    metrics.check_timestamps.append(old_time)
    # Add recent request
    await metrics.record_check(user_id=1, duration_ms=100.0)
    # Only the recent request should count
    assert metrics.get_requests_per_minute() == 1.0


def test_get_avg_response_time_no_data():
    """Test average response time with no data."""
    metrics = BotMetrics()
    assert metrics.get_avg_response_time_ms() == 0.0


@pytest.mark.asyncio
async def test_get_avg_response_time_with_data():
    """Test average response time calculation."""
    metrics = BotMetrics()
    await metrics.record_check(user_id=1, duration_ms=100.0)
    await metrics.record_check(user_id=1, duration_ms=200.0)
    await metrics.record_check(user_id=1, duration_ms=300.0)
    # Average = (100 + 200 + 300) / 3 = 200.0
    assert metrics.get_avg_response_time_ms() == 200.0


@pytest.mark.asyncio
async def test_get_snapshot():
    """Test getting metrics snapshot."""
    metrics = BotMetrics()
    await metrics.record_check(user_id=1, duration_ms=150.0)
    await metrics.record_slot_found(user_id=1, centre="Istanbul")
    await metrics.set_active_users(3)

    snapshot = await metrics.get_snapshot()

    assert isinstance(snapshot, MetricsSnapshot)
    assert snapshot.total_checks == 1
    assert snapshot.slots_found == 1
    assert snapshot.active_users == 3
    assert snapshot.uptime_seconds > 0
    assert isinstance(snapshot.timestamp, str)


@pytest.mark.asyncio
async def test_snapshot_storage():
    """Test that snapshots are stored."""
    metrics = BotMetrics(retention_minutes=5)
    snapshot1 = await metrics.get_snapshot()
    snapshot2 = await metrics.get_snapshot()

    assert len(metrics.snapshots) == 2
    assert metrics.snapshots[0] == snapshot1
    assert metrics.snapshots[1] == snapshot2


@pytest.mark.asyncio
async def test_get_metrics_dict():
    """Test getting metrics as dictionary."""
    metrics = BotMetrics()
    await metrics.record_check(user_id=1, duration_ms=100.0)
    await metrics.record_error(user_id=1, error_type="TestError")
    await metrics.record_captcha_solved()
    await metrics.set_status("running")

    metrics_dict = await metrics.get_metrics_dict()

    assert "current" in metrics_dict
    assert "status" in metrics_dict
    assert "errors" in metrics_dict
    assert "captchas_solved" in metrics_dict

    assert metrics_dict["status"] == "running"
    assert metrics_dict["captchas_solved"] == 1
    assert "by_type" in metrics_dict["errors"]
    assert "by_user" in metrics_dict["errors"]
    assert metrics_dict["errors"]["by_type"]["TestError"] == 1


@pytest.mark.asyncio
async def test_get_prometheus_metrics():
    """Test Prometheus metrics format."""
    metrics = BotMetrics()
    await metrics.record_check(user_id=1, duration_ms=100.0)
    await metrics.record_slot_found(user_id=1, centre="Istanbul")
    await metrics.record_appointment_booked(user_id=1)

    prom_metrics = await metrics.get_prometheus_metrics()

    assert isinstance(prom_metrics, str)
    assert "vfs_bot_uptime_seconds" in prom_metrics
    assert "vfs_bot_checks_total 1" in prom_metrics
    assert "vfs_bot_slots_found_total 1" in prom_metrics
    assert "vfs_bot_appointments_booked_total 1" in prom_metrics
    assert "# HELP" in prom_metrics
    assert "# TYPE" in prom_metrics


@pytest.mark.asyncio
async def test_prometheus_metrics_format():
    """Test that Prometheus metrics follow correct format."""
    metrics = BotMetrics()
    await metrics.set_active_users(5)

    prom_metrics = await metrics.get_prometheus_metrics()
    lines = prom_metrics.split("\n")

    # Check for proper structure
    help_lines = [l for l in lines if l.startswith("# HELP")]
    type_lines = [l for l in lines if l.startswith("# TYPE")]
    metric_lines = [l for l in lines if l and not l.startswith("#")]

    assert len(help_lines) > 0
    assert len(type_lines) > 0
    assert len(metric_lines) > 0


@pytest.mark.asyncio
async def test_get_metrics_singleton():
    """Test get_metrics returns singleton instance."""
    metrics1 = await get_metrics()
    metrics2 = await get_metrics()
    assert metrics1 is metrics2


@pytest.mark.asyncio
async def test_get_metrics_concurrent_access():
    """Test concurrent access to get_metrics."""
    import asyncio

    async def get_instance():
        return await get_metrics()

    # Create multiple concurrent tasks
    tasks = [get_instance() for _ in range(10)]
    results = await asyncio.gather(*tasks)

    # All should return the same instance
    first_instance = results[0]
    for instance in results[1:]:
        assert instance is first_instance


@pytest.mark.asyncio
async def test_metrics_snapshot_dataclass():
    """Test MetricsSnapshot dataclass."""
    snapshot = MetricsSnapshot(
        timestamp="2024-01-01T00:00:00Z",
        uptime_seconds=100.5,
        total_checks=10,
        slots_found=2,
        appointments_booked=1,
        total_errors=1,
        success_rate=90.0,
        requests_per_minute=5.0,
        avg_response_time_ms=150.0,
        circuit_breaker_trips=0,
        active_users=3,
    )

    assert snapshot.timestamp == "2024-01-01T00:00:00Z"
    assert snapshot.uptime_seconds == 100.5
    assert snapshot.total_checks == 10
    assert snapshot.success_rate == 90.0


@pytest.mark.asyncio
async def test_response_times_maxlen():
    """Test that response_times respects maxlen."""
    metrics = BotMetrics()
    # Add 1500 responses (maxlen is 1000)
    for i in range(1500):
        await metrics.record_check(user_id=1, duration_ms=float(i))

    assert len(metrics.response_times) == 1000
    # Should keep the most recent 1000
    assert metrics.response_times[-1] == 1499.0


@pytest.mark.asyncio
async def test_check_timestamps_maxlen():
    """Test that check_timestamps respects maxlen."""
    metrics = BotMetrics()
    # Add 1500 timestamps (maxlen is 1000)
    for i in range(1500):
        await metrics.record_check(user_id=1, duration_ms=100.0)

    assert len(metrics.check_timestamps) == 1000


@pytest.mark.asyncio
async def test_snapshots_retention():
    """Test that snapshots respect retention limit."""
    metrics = BotMetrics(retention_minutes=3)
    # Create 5 snapshots (retention is 3)
    for _ in range(5):
        await metrics.get_snapshot()

    assert len(metrics.snapshots) == 3
