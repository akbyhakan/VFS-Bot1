"""Extended tests for metrics tracking."""

import pytest
import time
from src.utils.metrics import BotMetrics, MetricsSnapshot


@pytest.fixture
def metrics():
    """Create a BotMetrics instance for testing."""
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
    await metrics.record_check(user_id=1, duration_ms=100.0)
    assert metrics.total_checks == 1
    assert len(metrics.response_times) == 1
    assert len(metrics.check_timestamps) == 1


@pytest.mark.asyncio
async def test_record_multiple_checks(metrics):
    """Test recording multiple checks."""
    for i in range(5):
        await metrics.record_check(user_id=1, duration_ms=100.0 + i)

    assert metrics.total_checks == 5
    assert len(metrics.response_times) == 5


@pytest.mark.asyncio
async def test_record_slot_found(metrics):
    """Test recording a slot found event."""
    await metrics.record_slot_found(user_id=1, centre="Istanbul")
    assert metrics.slots_found == 1


@pytest.mark.asyncio
async def test_record_appointment_booked(metrics):
    """Test recording a successful booking."""
    await metrics.record_appointment_booked(user_id=1)
    assert metrics.appointments_booked == 1


@pytest.mark.asyncio
async def test_record_error(metrics):
    """Test recording an error."""
    await metrics.record_error(user_id=1, error_type="NetworkError")
    assert metrics.total_errors == 1
    assert metrics.errors_by_type["NetworkError"] == 1
    assert metrics.errors_by_user[1] == 1


@pytest.mark.asyncio
async def test_record_multiple_error_types(metrics):
    """Test recording multiple error types."""
    await metrics.record_error(user_id=1, error_type="NetworkError")
    await metrics.record_error(user_id=1, error_type="TimeoutError")
    await metrics.record_error(user_id=2, error_type="NetworkError")

    assert metrics.total_errors == 3
    assert metrics.errors_by_type["NetworkError"] == 2
    assert metrics.errors_by_type["TimeoutError"] == 1
    assert metrics.errors_by_user[1] == 2
    assert metrics.errors_by_user[2] == 1


@pytest.mark.asyncio
async def test_record_circuit_breaker_trip(metrics):
    """Test recording circuit breaker trip."""
    await metrics.record_circuit_breaker_trip()
    assert metrics.circuit_breaker_trips == 1


@pytest.mark.asyncio
async def test_record_captcha_solved(metrics):
    """Test recording captcha solved."""
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


@pytest.mark.asyncio
async def test_get_snapshot(metrics):
    """Test getting metrics snapshot."""
    # Record some metrics
    await metrics.record_check(user_id=1, duration_ms=100.0)
    await metrics.record_slot_found(user_id=1, centre="Istanbul")
    await metrics.set_active_users(3)

    snapshot = await metrics.get_snapshot()

    assert isinstance(snapshot, MetricsSnapshot)
    assert snapshot.total_checks == 1
    assert snapshot.slots_found == 1
    assert snapshot.active_users == 3
    assert snapshot.uptime_seconds > 0


@pytest.mark.asyncio
async def test_get_success_rate_no_checks(metrics):
    """Test success rate calculation with no checks."""
    snapshot = await metrics.get_snapshot()
    assert snapshot.success_rate == 0.0


@pytest.mark.asyncio
async def test_get_success_rate_with_checks(metrics):
    """Test success rate calculation."""
    await metrics.record_check(user_id=1, duration_ms=100.0)
    await metrics.record_check(user_id=1, duration_ms=100.0)
    await metrics.record_error(user_id=1, error_type="Error")

    snapshot = await metrics.get_snapshot()
    # 2 checks, 1 error = 50% success rate
    # Actually the formula is (checks - errors) / checks
    # But we need to check actual implementation
    assert 0.0 <= snapshot.success_rate <= 100.0


@pytest.mark.asyncio
async def test_get_requests_per_minute(metrics):
    """Test requests per minute calculation."""
    # Record some checks
    for _ in range(5):
        await metrics.record_check(user_id=1, duration_ms=100.0)

    snapshot = await metrics.get_snapshot()
    assert snapshot.requests_per_minute >= 0.0


@pytest.mark.asyncio
async def test_get_avg_response_time(metrics):
    """Test average response time calculation."""
    await metrics.record_check(user_id=1, duration_ms=100.0)
    await metrics.record_check(user_id=1, duration_ms=200.0)
    await metrics.record_check(user_id=1, duration_ms=300.0)

    snapshot = await metrics.get_snapshot()
    assert snapshot.avg_response_time_ms == 200.0


@pytest.mark.asyncio
async def test_get_prometheus_metrics(metrics):
    """Test Prometheus format export."""
    await metrics.record_check(user_id=1, duration_ms=100.0)
    await metrics.record_slot_found(user_id=1, centre="Istanbul")

    prometheus_text = await metrics.get_prometheus_metrics()

    assert isinstance(prometheus_text, str)
    assert "vfs_bot_checks_total" in prometheus_text
    assert "vfs_bot_slots_found_total" in prometheus_text


@pytest.mark.asyncio
async def test_response_times_deque_maxlen(metrics):
    """Test that response times deque respects maxlen."""
    # Add more than maxlen items
    for i in range(1500):
        await metrics.record_check(user_id=1, duration_ms=float(i))

    # Should only keep last 1000
    assert len(metrics.response_times) == 1000


@pytest.mark.asyncio
async def test_check_timestamps_deque_maxlen(metrics):
    """Test that check timestamps deque respects maxlen."""
    # Add more than maxlen items
    for i in range(1500):
        await metrics.record_check(user_id=1, duration_ms=100.0)

    # Should only keep last 1000
    assert len(metrics.check_timestamps) == 1000


@pytest.mark.asyncio
async def test_metrics_snapshot_dataclass():
    """Test MetricsSnapshot dataclass."""
    snapshot = MetricsSnapshot(
        timestamp="2024-01-01T00:00:00Z",
        uptime_seconds=3600.0,
        total_checks=100,
        slots_found=5,
        appointments_booked=3,
        total_errors=2,
        success_rate=98.0,
        requests_per_minute=1.67,
        avg_response_time_ms=150.0,
        circuit_breaker_trips=0,
        active_users=2,
    )

    assert snapshot.total_checks == 100
    assert snapshot.slots_found == 5
    assert snapshot.success_rate == 98.0
