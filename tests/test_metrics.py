"""Tests for metrics tracking functionality."""

import sys
import time
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.metrics import BotMetrics, MetricsSnapshot


class TestBotMetrics:
    """Test bot metrics functionality."""

    @pytest.mark.asyncio
    async def test_init(self):
        """Test BotMetrics initialization."""
        metrics = BotMetrics(retention_minutes=30)

        assert metrics.retention_minutes == 30
        assert metrics.total_checks == 0
        assert metrics.slots_found == 0
        assert metrics.appointments_booked == 0
        assert metrics.total_errors == 0
        assert metrics.circuit_breaker_trips == 0
        assert metrics.active_users == 0
        assert metrics.current_status == "idle"

    @pytest.mark.asyncio
    async def test_record_check(self):
        """Test recording a check operation."""
        metrics = BotMetrics()

        await metrics.record_check(user_id=1, duration_ms=150.5)

        assert metrics.total_checks == 1
        assert len(metrics.response_times) == 1
        assert metrics.response_times[0] == 150.5
        assert len(metrics.check_timestamps) == 1

    @pytest.mark.asyncio
    async def test_record_multiple_checks(self):
        """Test recording multiple checks."""
        metrics = BotMetrics()

        for i in range(10):
            await metrics.record_check(user_id=1, duration_ms=100.0 + i)

        assert metrics.total_checks == 10
        assert len(metrics.response_times) == 10

    @pytest.mark.asyncio
    async def test_record_slot_found(self):
        """Test recording a slot found event."""
        metrics = BotMetrics()

        await metrics.record_slot_found(user_id=1, centre="Istanbul")

        assert metrics.slots_found == 1

    @pytest.mark.asyncio
    async def test_record_appointment_booked(self):
        """Test recording an appointment booking."""
        metrics = BotMetrics()

        await metrics.record_appointment_booked(user_id=1)

        assert metrics.appointments_booked == 1

    @pytest.mark.asyncio
    async def test_record_error(self):
        """Test recording an error."""
        metrics = BotMetrics()

        await metrics.record_error(user_id=1, error_type="NetworkError")

        assert metrics.total_errors == 1
        assert metrics.errors_by_type["NetworkError"] == 1
        assert metrics.errors_by_user[1] == 1

    @pytest.mark.asyncio
    async def test_record_multiple_error_types(self):
        """Test recording multiple error types."""
        metrics = BotMetrics()

        await metrics.record_error(user_id=1, error_type="NetworkError")
        await metrics.record_error(user_id=1, error_type="TimeoutError")
        await metrics.record_error(user_id=2, error_type="NetworkError")

        assert metrics.total_errors == 3
        assert metrics.errors_by_type["NetworkError"] == 2
        assert metrics.errors_by_type["TimeoutError"] == 1
        assert metrics.errors_by_user[1] == 2
        assert metrics.errors_by_user[2] == 1

    @pytest.mark.asyncio
    async def test_record_circuit_breaker_trip(self):
        """Test recording circuit breaker trips."""
        metrics = BotMetrics()

        await metrics.record_circuit_breaker_trip()

        assert metrics.circuit_breaker_trips == 1

    @pytest.mark.asyncio
    async def test_set_active_users(self):
        """Test setting active users count."""
        metrics = BotMetrics()

        await metrics.set_active_users(5)

        assert metrics.active_users == 5

    @pytest.mark.asyncio
    async def test_set_status(self):
        """Test setting bot status."""
        metrics = BotMetrics()

        await metrics.set_status("running")

        assert metrics.current_status == "running"

    def test_get_uptime(self):
        """Test getting uptime."""
        metrics = BotMetrics()

        # Sleep a tiny bit to ensure uptime > 0
        time.sleep(0.01)

        uptime = time.time() - metrics.start_time

        assert uptime > 0

    def test_get_success_rate_no_checks(self):
        """Test success rate when no checks performed."""
        metrics = BotMetrics()

        success_rate = metrics.get_success_rate()

        assert success_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_success_rate_with_checks(self):
        """Test success rate calculation."""
        metrics = BotMetrics()

        # Record 10 checks, 2 errors
        for _ in range(10):
            await metrics.record_check(user_id=1, duration_ms=100.0)

        await metrics.record_error(user_id=1, error_type="Error1")
        await metrics.record_error(user_id=1, error_type="Error2")

        success_rate = metrics.get_success_rate()

        # Success rate = (10 - 2) / 10 = 0.8 = 80%
        assert success_rate == 80.0

    def test_get_requests_per_minute_no_checks(self):
        """Test requests per minute when no checks."""
        metrics = BotMetrics()

        rpm = metrics.get_requests_per_minute()

        assert rpm == 0.0

    @pytest.mark.asyncio
    async def test_get_requests_per_minute_with_checks(self):
        """Test requests per minute calculation."""
        metrics = BotMetrics()

        # Record some checks
        for _ in range(5):
            await metrics.record_check(user_id=1, duration_ms=100.0)

        rpm = metrics.get_requests_per_minute()

        # Should be 5 since we just recorded them
        assert rpm == 5.0

    def test_get_avg_response_time_no_data(self):
        """Test average response time with no data."""
        metrics = BotMetrics()

        avg_time = metrics.get_avg_response_time_ms()

        assert avg_time == 0.0

    @pytest.mark.asyncio
    async def test_get_avg_response_time_with_data(self):
        """Test average response time calculation."""
        metrics = BotMetrics()

        await metrics.record_check(user_id=1, duration_ms=100.0)
        await metrics.record_check(user_id=1, duration_ms=200.0)
        await metrics.record_check(user_id=1, duration_ms=300.0)

        avg_time = metrics.get_avg_response_time_ms()

        # Average should be 200.0
        assert avg_time == 200.0

    @pytest.mark.asyncio
    async def test_get_snapshot(self):
        """Test getting a metrics snapshot."""
        metrics = BotMetrics()

        # Record some activity
        await metrics.record_check(user_id=1, duration_ms=150.0)
        await metrics.record_slot_found(user_id=1, centre="Istanbul")
        await metrics.set_active_users(3)

        snapshot = await metrics.get_snapshot()

        assert isinstance(snapshot, MetricsSnapshot)
        assert snapshot.total_checks == 1
        assert snapshot.slots_found == 1
        assert snapshot.active_users == 3
        assert snapshot.uptime_seconds > 0
        assert snapshot.timestamp is not None  # Just verify it exists

    @pytest.mark.asyncio
    async def test_response_times_retention(self):
        """Test that response times are limited to maxlen."""
        metrics = BotMetrics()

        # Record more than maxlen (1000) checks
        for i in range(1100):
            await metrics.record_check(user_id=1, duration_ms=float(i))

        # Should only keep last 1000
        assert len(metrics.response_times) == 1000
        # Last value should be 1099
        assert metrics.response_times[-1] == 1099.0

    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test concurrent access to metrics."""
        metrics = BotMetrics()

        # Create multiple concurrent tasks
        import asyncio

        tasks = [metrics.record_check(user_id=i, duration_ms=100.0) for i in range(100)]

        await asyncio.gather(*tasks)

        # All 100 checks should be recorded
        assert metrics.total_checks == 100

    @pytest.mark.asyncio
    async def test_error_types_tracking(self):
        """Test that error types are tracked separately."""
        metrics = BotMetrics()

        await metrics.record_error(user_id=1, error_type="NetworkError")
        await metrics.record_error(user_id=2, error_type="NetworkError")
        await metrics.record_error(user_id=1, error_type="TimeoutError")
        await metrics.record_error(user_id=3, error_type="ValidationError")

        assert len(metrics.errors_by_type) == 3
        assert metrics.errors_by_type["NetworkError"] == 2
        assert metrics.errors_by_type["TimeoutError"] == 1
        assert metrics.errors_by_type["ValidationError"] == 1

    @pytest.mark.asyncio
    async def test_snapshot_retention(self):
        """Test that snapshots are retained according to limit."""
        metrics = BotMetrics(retention_minutes=5)

        # Add more snapshots than the retention limit
        for _ in range(10):
            snapshot = await metrics.get_snapshot()
            metrics.snapshots.append(snapshot)

        # Should only keep 5
        assert len(metrics.snapshots) <= 5


class TestMetricsSnapshot:
    """Test MetricsSnapshot dataclass."""

    def test_snapshot_creation(self):
        """Test creating a metrics snapshot."""
        snapshot = MetricsSnapshot(
            timestamp="2024-01-01T00:00:00",
            uptime_seconds=3600.0,
            total_checks=100,
            slots_found=5,
            appointments_booked=2,
            total_errors=3,
            success_rate=95.0,
            requests_per_minute=10.0,
            avg_response_time_ms=150.0,
            circuit_breaker_trips=1,
            active_users=3,
        )

        assert snapshot.timestamp == "2024-01-01T00:00:00"
        assert snapshot.uptime_seconds == 3600.0
        assert snapshot.total_checks == 100
        assert snapshot.slots_found == 5
        assert snapshot.appointments_booked == 2

    def test_snapshot_to_dict(self):
        """Test converting snapshot to dictionary."""
        snapshot = MetricsSnapshot(
            timestamp="2024-01-01T00:00:00",
            uptime_seconds=3600.0,
            total_checks=100,
            slots_found=5,
            appointments_booked=2,
            total_errors=3,
            success_rate=95.0,
            requests_per_minute=10.0,
            avg_response_time_ms=150.0,
            circuit_breaker_trips=1,
            active_users=3,
        )

        from dataclasses import asdict

        snapshot_dict = asdict(snapshot)

        assert isinstance(snapshot_dict, dict)
        assert snapshot_dict["total_checks"] == 100
        assert snapshot_dict["success_rate"] == 95.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
