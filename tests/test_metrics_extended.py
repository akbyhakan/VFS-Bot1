"""Extended tests for src/utils/metrics.py - aiming for 97% coverage."""

import pytest
import asyncio
import time

from src.utils.metrics import BotMetrics, get_metrics, MetricsSnapshot


@pytest.mark.asyncio
class TestMetricsInitialization:
    """Tests for BotMetrics initialization."""

    async def test_metrics_initialization(self):
        """Test metrics initialization with default values."""
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
class TestRecordCheck:
    """Tests for record_check method."""

    async def test_record_check(self):
        """Test recording a single check."""
        metrics = BotMetrics()
        await metrics.record_check(user_id=1, duration_ms=100.0)

        assert metrics.total_checks == 1
        assert len(metrics.response_times) == 1
        assert metrics.response_times[0] == 100.0
        assert len(metrics.check_timestamps) == 1

    async def test_record_multiple_checks(self):
        """Test recording multiple checks."""
        metrics = BotMetrics()
        await metrics.record_check(user_id=1, duration_ms=100.0)
        await metrics.record_check(user_id=2, duration_ms=200.0)
        await metrics.record_check(user_id=1, duration_ms=150.0)

        assert metrics.total_checks == 3
        assert len(metrics.response_times) == 3
        assert len(metrics.check_timestamps) == 3


@pytest.mark.asyncio
class TestRecordSlotFound:
    """Tests for record_slot_found method."""

    async def test_record_slot_found(self):
        """Test recording a slot found event."""
        metrics = BotMetrics()
        await metrics.record_slot_found(user_id=1, centre="Istanbul")

        assert metrics.slots_found == 1


@pytest.mark.asyncio
class TestRecordAppointmentBooked:
    """Tests for record_appointment_booked method."""

    async def test_record_appointment_booked(self):
        """Test recording an appointment booked event."""
        metrics = BotMetrics()
        await metrics.record_appointment_booked(user_id=1)

        assert metrics.appointments_booked == 1


@pytest.mark.asyncio
class TestRecordError:
    """Tests for record_error method."""

    async def test_record_error(self):
        """Test recording an error."""
        metrics = BotMetrics()
        await metrics.record_error(user_id=1, error_type="LoginError")

        assert metrics.total_errors == 1
        assert metrics.errors_by_type["LoginError"] == 1
        assert metrics.errors_by_user[1] == 1

    async def test_record_multiple_error_types(self):
        """Test recording multiple error types."""
        metrics = BotMetrics()
        await metrics.record_error(user_id=1, error_type="LoginError")
        await metrics.record_error(user_id=2, error_type="NetworkError")
        await metrics.record_error(user_id=1, error_type="LoginError")

        assert metrics.total_errors == 3
        assert metrics.errors_by_type["LoginError"] == 2
        assert metrics.errors_by_type["NetworkError"] == 1
        assert metrics.errors_by_user[1] == 2
        assert metrics.errors_by_user[2] == 1

    async def test_record_error_without_user_id(self):
        """Test recording an error without user ID."""
        metrics = BotMetrics()
        await metrics.record_error(user_id=None, error_type="SystemError")

        assert metrics.total_errors == 1
        assert metrics.errors_by_type["SystemError"] == 1
        assert len(metrics.errors_by_user) == 0


@pytest.mark.asyncio
class TestRecordCircuitBreakerTrip:
    """Tests for record_circuit_breaker_trip method."""

    async def test_record_circuit_breaker_trip(self):
        """Test recording a circuit breaker trip."""
        metrics = BotMetrics()
        await metrics.record_circuit_breaker_trip()

        assert metrics.circuit_breaker_trips == 1


@pytest.mark.asyncio
class TestRecordCaptchaSolved:
    """Tests for record_captcha_solved method."""

    async def test_record_captcha_solved(self):
        """Test recording a solved captcha."""
        metrics = BotMetrics()
        await metrics.record_captcha_solved()

        assert metrics.captchas_solved == 1


@pytest.mark.asyncio
class TestSetActiveUsers:
    """Tests for set_active_users method."""

    async def test_set_active_users(self):
        """Test setting active users count."""
        metrics = BotMetrics()
        await metrics.set_active_users(5)

        assert metrics.active_users == 5


@pytest.mark.asyncio
class TestSetStatus:
    """Tests for set_status method."""

    async def test_set_status(self):
        """Test setting bot status."""
        metrics = BotMetrics()
        await metrics.set_status("running")

        assert metrics.current_status == "running"


@pytest.mark.asyncio
class TestGetSuccessRate:
    """Tests for get_success_rate method."""

    async def test_get_success_rate_zero_checks(self):
        """Test success rate with zero checks."""
        metrics = BotMetrics()
        rate = metrics.get_success_rate()

        assert rate == 0.0

    async def test_get_success_rate_no_errors(self):
        """Test success rate with no errors."""
        metrics = BotMetrics()
        await metrics.record_check(user_id=1, duration_ms=100.0)
        await metrics.record_check(user_id=1, duration_ms=150.0)

        rate = metrics.get_success_rate()
        assert rate == 100.0

    async def test_get_success_rate_with_errors(self):
        """Test success rate with some errors."""
        metrics = BotMetrics()
        await metrics.record_check(user_id=1, duration_ms=100.0)
        await metrics.record_check(user_id=1, duration_ms=150.0)
        await metrics.record_check(user_id=1, duration_ms=200.0)
        await metrics.record_check(user_id=1, duration_ms=250.0)
        await metrics.record_error(user_id=1, error_type="TestError")

        rate = metrics.get_success_rate()
        assert rate == 75.0  # 3 successful out of 4 total


@pytest.mark.asyncio
class TestGetRequestsPerMinute:
    """Tests for get_requests_per_minute method."""

    async def test_get_requests_per_minute_zero(self):
        """Test requests per minute with no checks."""
        metrics = BotMetrics()
        rpm = metrics.get_requests_per_minute()

        assert rpm == 0.0

    async def test_get_requests_per_minute_recent(self):
        """Test requests per minute with recent checks."""
        metrics = BotMetrics()
        # Simulate recent requests
        await metrics.record_check(user_id=1, duration_ms=100.0)
        await metrics.record_check(user_id=1, duration_ms=100.0)
        await metrics.record_check(user_id=1, duration_ms=100.0)

        rpm = metrics.get_requests_per_minute()
        assert rpm == 3.0


@pytest.mark.asyncio
class TestGetAvgResponseTime:
    """Tests for get_avg_response_time_ms method."""

    async def test_get_avg_response_time_zero(self):
        """Test average response time with no requests."""
        metrics = BotMetrics()
        avg = metrics.get_avg_response_time_ms()

        assert avg == 0.0

    async def test_get_avg_response_time_multiple(self):
        """Test average response time with multiple requests."""
        metrics = BotMetrics()
        await metrics.record_check(user_id=1, duration_ms=100.0)
        await metrics.record_check(user_id=1, duration_ms=200.0)
        await metrics.record_check(user_id=1, duration_ms=300.0)

        avg = metrics.get_avg_response_time_ms()
        assert avg == 200.0


@pytest.mark.asyncio
class TestGetSnapshot:
    """Tests for get_snapshot method."""

    async def test_get_snapshot(self):
        """Test getting a metrics snapshot."""
        metrics = BotMetrics()
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
class TestGetMetricsDict:
    """Tests for get_metrics_dict method."""

    async def test_get_metrics_dict(self):
        """Test getting metrics as dictionary."""
        metrics = BotMetrics()
        await metrics.record_check(user_id=1, duration_ms=100.0)
        await metrics.record_error(user_id=1, error_type="TestError")
        await metrics.record_captcha_solved()

        metrics_dict = await metrics.get_metrics_dict()

        assert "current" in metrics_dict
        assert "status" in metrics_dict
        assert "errors" in metrics_dict
        assert "captchas_solved" in metrics_dict
        assert metrics_dict["captchas_solved"] == 1


@pytest.mark.asyncio
class TestGetPrometheusMetrics:
    """Tests for get_prometheus_metrics method."""

    async def test_get_prometheus_metrics(self):
        """Test getting Prometheus-formatted metrics."""
        metrics = BotMetrics()
        await metrics.record_check(user_id=1, duration_ms=100.0)
        await metrics.record_slot_found(user_id=1, centre="Istanbul")

        prom_metrics = await metrics.get_prometheus_metrics()

        assert isinstance(prom_metrics, str)
        assert "vfs_bot_uptime_seconds" in prom_metrics
        assert "vfs_bot_checks_total" in prom_metrics
        assert "vfs_bot_slots_found_total" in prom_metrics
        assert "# HELP" in prom_metrics
        assert "# TYPE" in prom_metrics


@pytest.mark.asyncio
class TestResponseTimesDequeMaxlen:
    """Tests for response_times deque max length."""

    async def test_response_times_deque_maxlen(self):
        """Test that response_times deque respects maxlen."""
        metrics = BotMetrics()

        # Add more than 1000 entries
        for i in range(1100):
            await metrics.record_check(user_id=1, duration_ms=float(i))

        # Should only keep last 1000
        assert len(metrics.response_times) == 1000
        assert metrics.total_checks == 1100


@pytest.mark.asyncio
class TestGetMetricsSingleton:
    """Tests for get_metrics singleton pattern."""

    async def test_get_metrics_singleton(self):
        """Test that get_metrics returns singleton instance."""
        # Import to reset the global instance
        from src.utils import metrics

        # Reset the global instance
        metrics._metrics_instance = None

        instance1 = await get_metrics()
        instance2 = await get_metrics()

        assert instance1 is instance2
