"""Tests for metrics tracking."""

import pytest
from pathlib import Path
import sys
import asyncio
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.metrics import BotMetrics, MetricsSnapshot, get_metrics


class TestBotMetrics:
    """Test bot metrics functionality."""

    def test_init_default(self):
        """Test BotMetrics initialization with defaults."""
        metrics = BotMetrics()

        assert metrics.retention_minutes == 60
        assert metrics.total_checks == 0
        assert metrics.slots_found == 0
        assert metrics.appointments_booked == 0
        assert metrics.total_errors == 0
        assert metrics.circuit_breaker_trips == 0
        assert metrics.captchas_solved == 0
        assert metrics.active_users == 0
        assert metrics.current_status == "idle"

    def test_init_custom_retention(self):
        """Test BotMetrics initialization with custom retention."""
        metrics = BotMetrics(retention_minutes=120)

        assert metrics.retention_minutes == 120

    @pytest.mark.asyncio
    async def test_record_check(self):
        """Test record_check."""
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

        await metrics.record_check(user_id=1, duration_ms=100)
        await metrics.record_check(user_id=1, duration_ms=200)
        await metrics.record_check(user_id=2, duration_ms=150)

        assert metrics.total_checks == 3
        assert len(metrics.response_times) == 3

    @pytest.mark.asyncio
    async def test_record_slot_found(self):
        """Test record_slot_found."""
        metrics = BotMetrics()

        await metrics.record_slot_found(user_id=1, centre="Istanbul")

        assert metrics.slots_found == 1

    @pytest.mark.asyncio
    async def test_record_appointment_booked(self):
        """Test record_appointment_booked."""
        metrics = BotMetrics()

        await metrics.record_appointment_booked(user_id=1)

        assert metrics.appointments_booked == 1

    @pytest.mark.asyncio
    async def test_record_error(self):
        """Test record_error."""
        metrics = BotMetrics()

        await metrics.record_error(user_id=1, error_type="TimeoutError")

        assert metrics.total_errors == 1
        assert metrics.errors_by_type["TimeoutError"] == 1
        assert metrics.errors_by_user[1] == 1

    @pytest.mark.asyncio
    async def test_record_error_no_user(self):
        """Test record_error without user_id."""
        metrics = BotMetrics()

        await metrics.record_error(user_id=None, error_type="NetworkError")

        assert metrics.total_errors == 1
        assert metrics.errors_by_type["NetworkError"] == 1

    @pytest.mark.asyncio
    async def test_record_circuit_breaker_trip(self):
        """Test record_circuit_breaker_trip."""
        metrics = BotMetrics()

        await metrics.record_circuit_breaker_trip()

        assert metrics.circuit_breaker_trips == 1

    @pytest.mark.asyncio
    async def test_record_captcha_solved(self):
        """Test record_captcha_solved."""
        metrics = BotMetrics()

        await metrics.record_captcha_solved()

        assert metrics.captchas_solved == 1

    @pytest.mark.asyncio
    async def test_set_active_users(self):
        """Test set_active_users."""
        metrics = BotMetrics()

        await metrics.set_active_users(5)

        assert metrics.active_users == 5

    @pytest.mark.asyncio
    async def test_set_status(self):
        """Test set_status."""
        metrics = BotMetrics()

        await metrics.set_status("running")

        assert metrics.current_status == "running"

    def test_get_success_rate_no_checks(self):
        """Test get_success_rate with no checks."""
        metrics = BotMetrics()

        rate = metrics.get_success_rate()

        assert rate == 0.0

    def test_get_success_rate_no_errors(self):
        """Test get_success_rate with no errors."""
        metrics = BotMetrics()
        metrics.total_checks = 10

        rate = metrics.get_success_rate()

        assert rate == 100.0

    def test_get_success_rate_with_errors(self):
        """Test get_success_rate with some errors."""
        metrics = BotMetrics()
        metrics.total_checks = 10
        metrics.total_errors = 2

        rate = metrics.get_success_rate()

        assert rate == 80.0

    def test_get_requests_per_minute_empty(self):
        """Test get_requests_per_minute with no requests."""
        metrics = BotMetrics()

        rpm = metrics.get_requests_per_minute()

        assert rpm == 0.0

    def test_get_requests_per_minute_with_recent(self):
        """Test get_requests_per_minute with recent requests."""
        metrics = BotMetrics()
        current_time = time.time()
        metrics.check_timestamps.extend([current_time - 30, current_time - 20, current_time - 10])

        rpm = metrics.get_requests_per_minute()

        assert rpm == 3.0

    def test_get_requests_per_minute_excludes_old(self):
        """Test get_requests_per_minute excludes old requests."""
        metrics = BotMetrics()
        current_time = time.time()
        metrics.check_timestamps.extend([current_time - 90, current_time - 30])

        rpm = metrics.get_requests_per_minute()

        assert rpm == 1.0

    def test_get_avg_response_time_ms_empty(self):
        """Test get_avg_response_time_ms with no data."""
        metrics = BotMetrics()

        avg = metrics.get_avg_response_time_ms()

        assert avg == 0.0

    def test_get_avg_response_time_ms(self):
        """Test get_avg_response_time_ms."""
        metrics = BotMetrics()
        metrics.response_times.extend([100, 200, 300])

        avg = metrics.get_avg_response_time_ms()

        assert avg == 200.0

    @pytest.mark.asyncio
    async def test_get_snapshot(self):
        """Test get_snapshot."""
        metrics = BotMetrics()
        metrics.total_checks = 10
        metrics.slots_found = 2
        metrics.appointments_booked = 1
        metrics.total_errors = 1
        metrics.circuit_breaker_trips = 0
        metrics.active_users = 3

        snapshot = await metrics.get_snapshot()

        assert isinstance(snapshot, MetricsSnapshot)
        assert snapshot.total_checks == 10
        assert snapshot.slots_found == 2
        assert snapshot.appointments_booked == 1
        assert snapshot.total_errors == 1
        assert snapshot.circuit_breaker_trips == 0
        assert snapshot.active_users == 3
        assert snapshot.success_rate == 90.0

    @pytest.mark.asyncio
    async def test_get_snapshot_stores_in_history(self):
        """Test get_snapshot stores snapshot in history."""
        metrics = BotMetrics()

        snapshot = await metrics.get_snapshot()

        assert len(metrics.snapshots) == 1
        assert metrics.snapshots[0] == snapshot

    @pytest.mark.asyncio
    async def test_get_metrics_dict(self):
        """Test get_metrics_dict."""
        metrics = BotMetrics()
        metrics.total_checks = 5
        metrics.errors_by_type["Error1"] = 1
        metrics.errors_by_user[1] = 2
        metrics.captchas_solved = 3

        result = await metrics.get_metrics_dict()

        assert "current" in result
        assert "status" in result
        assert "errors" in result
        assert "captchas_solved" in result
        assert result["status"] == "idle"
        assert result["captchas_solved"] == 3
        assert result["errors"]["by_type"]["Error1"] == 1
        assert result["errors"]["by_user"][1] == 2

    @pytest.mark.asyncio
    async def test_get_prometheus_metrics(self):
        """Test get_prometheus_metrics."""
        metrics = BotMetrics()
        metrics.total_checks = 10
        metrics.slots_found = 2

        result = await metrics.get_prometheus_metrics()

        assert "vfs_bot_uptime_seconds" in result
        assert "vfs_bot_checks_total 10" in result
        assert "vfs_bot_slots_found_total 2" in result
        assert "# HELP" in result
        assert "# TYPE" in result

    @pytest.mark.asyncio
    async def test_get_prometheus_metrics_format(self):
        """Test Prometheus metrics format."""
        metrics = BotMetrics()

        result = await metrics.get_prometheus_metrics()

        lines = result.split("\n")
        # Should have help and type comments
        assert any("# HELP" in line for line in lines)
        assert any("# TYPE" in line for line in lines)
        # Should have metric values
        assert any("vfs_bot_uptime_seconds" in line and "#" not in line for line in lines)


class TestGetMetrics:
    """Test get_metrics singleton function."""

    @pytest.mark.asyncio
    async def test_get_metrics_singleton(self):
        """Test get_metrics returns singleton instance."""
        # Reset the global instance for testing
        import src.utils.metrics as metrics_module

        metrics_module._metrics_instance = None

        metrics1 = await get_metrics()
        metrics2 = await get_metrics()

        assert metrics1 is metrics2

    @pytest.mark.asyncio
    async def test_get_metrics_creates_instance(self):
        """Test get_metrics creates instance on first call."""
        # Reset the global instance for testing
        import src.utils.metrics as metrics_module

        metrics_module._metrics_instance = None

        metrics = await get_metrics()

        assert metrics is not None
        assert isinstance(metrics, BotMetrics)


class TestMetricsSnapshot:
    """Test MetricsSnapshot dataclass."""

    def test_metrics_snapshot_creation(self):
        """Test creating MetricsSnapshot."""
        snapshot = MetricsSnapshot(
            timestamp="2024-01-01T12:00:00",
            uptime_seconds=3600.0,
            total_checks=100,
            slots_found=5,
            appointments_booked=2,
            total_errors=3,
            success_rate=97.0,
            requests_per_minute=2.5,
            avg_response_time_ms=150.0,
            circuit_breaker_trips=0,
            active_users=10,
        )

        assert snapshot.total_checks == 100
        assert snapshot.slots_found == 5
        assert snapshot.success_rate == 97.0
