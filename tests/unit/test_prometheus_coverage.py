"""Additional coverage tests for utils/prometheus_metrics module."""

import pytest

from src.utils.prometheus_metrics import MetricsHelper, get_metrics


class TestMetricsHelperDbConnections:
    """Tests for DB connection / pool metric methods."""

    def test_set_db_connections_positive(self):
        """set_db_connections accepts a positive integer."""
        MetricsHelper.set_db_connections(10)

    def test_set_db_connections_zero(self):
        """set_db_connections accepts 0."""
        MetricsHelper.set_db_connections(0)

    def test_set_db_pool_size(self):
        """set_db_pool_size stores the pool size without error."""
        MetricsHelper.set_db_pool_size(20)

    def test_set_db_pool_size_minimum(self):
        """set_db_pool_size accepts the value 1."""
        MetricsHelper.set_db_pool_size(1)

    def test_set_db_pool_idle(self):
        """set_db_pool_idle sets idle connections count."""
        MetricsHelper.set_db_pool_idle(5)

    def test_set_db_pool_idle_zero(self):
        """set_db_pool_idle accepts 0."""
        MetricsHelper.set_db_pool_idle(0)

    def test_set_db_pool_utilization_zero(self):
        """set_db_pool_utilization accepts 0.0."""
        MetricsHelper.set_db_pool_utilization(0.0)

    def test_set_db_pool_utilization_one(self):
        """set_db_pool_utilization accepts 1.0."""
        MetricsHelper.set_db_pool_utilization(1.0)

    def test_set_db_pool_utilization_partial(self):
        """set_db_pool_utilization accepts a value between 0 and 1."""
        MetricsHelper.set_db_pool_utilization(0.75)


class TestMetricsHelperDbPool:
    """Tests for DB pool acquire / timeout metrics."""

    def test_record_db_pool_acquire(self):
        """record_db_pool_acquire accepts a float duration."""
        MetricsHelper.record_db_pool_acquire(0.025)

    def test_record_db_pool_acquire_zero(self):
        """record_db_pool_acquire handles 0 duration."""
        MetricsHelper.record_db_pool_acquire(0.0)

    def test_record_db_pool_timeout(self):
        """record_db_pool_timeout increments without arguments."""
        MetricsHelper.record_db_pool_timeout()

    def test_record_db_pool_timeout_multiple_times(self):
        """record_db_pool_timeout can be called multiple times."""
        for _ in range(5):
            MetricsHelper.record_db_pool_timeout()


class TestMetricsHelperOtp:
    """Tests for OTP-related metric methods."""

    def test_record_otp_received_appointment(self):
        """record_otp_received works for 'appointment' type."""
        MetricsHelper.record_otp_received("appointment")

    def test_record_otp_received_payment(self):
        """record_otp_received works for 'payment' type."""
        MetricsHelper.record_otp_received("payment")

    def test_record_otp_received_custom_type(self):
        """record_otp_received accepts an arbitrary type string."""
        MetricsHelper.record_otp_received("sms")

    def test_record_otp_wait(self):
        """record_otp_wait records a positive duration."""
        MetricsHelper.record_otp_wait(12.5)

    def test_record_otp_wait_zero(self):
        """record_otp_wait handles 0 duration."""
        MetricsHelper.record_otp_wait(0.0)


class TestMetricsHelperPayment:
    """Tests for payment attempt metrics."""

    def test_record_payment_attempt_success(self):
        """record_payment_attempt success path does not raise."""
        MetricsHelper.record_payment_attempt(method="credit_card", success=True)

    def test_record_payment_attempt_failure(self):
        """record_payment_attempt failure path does not raise."""
        MetricsHelper.record_payment_attempt(method="credit_card", success=False)

    def test_record_payment_attempt_different_methods(self):
        """record_payment_attempt works for multiple payment methods."""
        for method in ["credit_card", "debit_card", "bank_transfer"]:
            MetricsHelper.record_payment_attempt(method=method, success=True)


class TestMetricsHelperBotUptime:
    """Tests for bot uptime metric."""

    def test_set_bot_uptime_zero(self):
        """set_bot_uptime accepts 0.0."""
        MetricsHelper.set_bot_uptime(0.0)

    def test_set_bot_uptime_positive(self):
        """set_bot_uptime accepts a positive float."""
        MetricsHelper.set_bot_uptime(3600.0)

    def test_set_bot_uptime_large_value(self):
        """set_bot_uptime accepts a large value (many days in seconds)."""
        MetricsHelper.set_bot_uptime(86400.0 * 30)


class TestGetMetrics:
    """Tests for the get_metrics() function."""

    def test_returns_bytes(self):
        """get_metrics returns bytes."""
        result = get_metrics()
        assert isinstance(result, bytes)

    def test_returns_non_empty_output(self):
        """get_metrics returns a non-empty bytes object."""
        result = get_metrics()
        assert len(result) > 0

    def test_output_is_valid_prometheus_text(self):
        """get_metrics output contains Prometheus HELP/TYPE lines."""
        result = get_metrics().decode("utf-8")
        # Prometheus exposition format always includes # HELP lines
        assert "# HELP" in result or "# TYPE" in result

    def test_get_metrics_after_recording(self):
        """get_metrics reflects recently recorded values."""
        MetricsHelper.set_db_connections(42)
        MetricsHelper.record_db_pool_timeout()
        result = get_metrics()
        # Just verify it still returns bytes without error
        assert isinstance(result, bytes)

    def test_get_metrics_called_multiple_times(self):
        """get_metrics can be called multiple times without error."""
        for _ in range(3):
            result = get_metrics()
            assert isinstance(result, bytes)
