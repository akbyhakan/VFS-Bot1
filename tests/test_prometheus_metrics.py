"""Tests for Prometheus metrics."""

import pytest
from unittest.mock import patch, MagicMock

from src.utils.prometheus_metrics import (
    MetricsHelper,
    get_metrics,
    SLOT_CHECKS_TOTAL,
    BOOKING_SUCCESS,
    ACTIVE_USERS,
)


class TestMetricsHelper:
    """Tests for MetricsHelper."""
    
    def test_record_slot_check_found(self):
        """Test recording slot check when slot is found."""
        # Should not raise
        MetricsHelper.record_slot_check(centre="Istanbul", found=True)
    
    def test_record_slot_check_not_found(self):
        """Test recording slot check when slot is not found."""
        # Should not raise
        MetricsHelper.record_slot_check(centre="Ankara", found=False)
    
    def test_record_booking_success(self):
        """Test recording successful booking."""
        # Should not raise
        MetricsHelper.record_booking_success(centre="Istanbul")
    
    def test_record_booking_failure(self):
        """Test recording failed booking."""
        # Should not raise
        MetricsHelper.record_booking_failure(
            centre="Istanbul",
            reason="payment_failed"
        )
    
    def test_set_active_users(self):
        """Test setting active users count."""
        # Should not raise
        MetricsHelper.set_active_users(count=5)
    
    def test_set_circuit_breaker_state(self):
        """Test setting circuit breaker state."""
        # Should not raise - open
        MetricsHelper.set_circuit_breaker_state(
            service="vfs_api",
            is_open=True
        )
        
        # Should not raise - closed
        MetricsHelper.set_circuit_breaker_state(
            service="vfs_api",
            is_open=False
        )
    
    def test_record_http_request(self):
        """Test recording HTTP request."""
        # Should not raise
        MetricsHelper.record_http_request(
            method="POST",
            endpoint="/api/appointments",
            status=200
        )
    
    def test_record_db_query(self):
        """Test recording database query."""
        # Should not raise - success
        MetricsHelper.record_db_query(
            operation="select",
            duration=0.015,
            success=True
        )
        
        # Should not raise - failure
        MetricsHelper.record_db_query(
            operation="insert",
            duration=0.025,
            success=False
        )
    
    def test_record_captcha_solved(self):
        """Test recording captcha solving."""
        # Should not raise
        MetricsHelper.record_captcha_solved(
            solver="2captcha",
            duration=15.5,
            success=True
        )
    
    def test_record_error(self):
        """Test recording error."""
        # Should not raise
        MetricsHelper.record_error(
            error_type="timeout",
            component="payment_service"
        )
    
    def test_set_bot_running(self):
        """Test setting bot running state."""
        # Should not raise
        MetricsHelper.set_bot_running(is_running=True)
        MetricsHelper.set_bot_running(is_running=False)


class TestPrometheusMetrics:
    """Tests for Prometheus metrics module."""
    
    def test_get_metrics_returns_bytes(self):
        """Test that get_metrics returns bytes."""
        metrics = get_metrics()
        assert isinstance(metrics, bytes)
    
    def test_metrics_contain_vfs_prefix(self):
        """Test that metrics contain vfs prefix."""
        metrics = get_metrics()
        metrics_str = metrics.decode('utf-8')
        # Check for at least one of our custom metrics
        assert 'vfs_' in metrics_str
    
    def test_slot_checks_total_metric_exists(self):
        """Test that slot checks total metric exists."""
        # Record a metric
        SLOT_CHECKS_TOTAL.labels(centre="Istanbul", status="found").inc()
        
        metrics = get_metrics()
        metrics_str = metrics.decode('utf-8')
        assert 'vfs_slot_checks_total' in metrics_str
    
    def test_booking_success_metric_exists(self):
        """Test that booking success metric exists."""
        # Record a metric
        BOOKING_SUCCESS.labels(centre="Istanbul").inc()
        
        metrics = get_metrics()
        metrics_str = metrics.decode('utf-8')
        assert 'vfs_bookings_success_total' in metrics_str
    
    def test_active_users_metric_exists(self):
        """Test that active users metric exists."""
        # Set metric
        ACTIVE_USERS.set(10)
        
        metrics = get_metrics()
        metrics_str = metrics.decode('utf-8')
        assert 'vfs_active_users' in metrics_str


class TestMetricsIntegration:
    """Integration tests for metrics."""
    
    def test_multiple_metrics_recorded(self):
        """Test recording multiple different metrics."""
        # Record various metrics
        MetricsHelper.record_slot_check(centre="Istanbul", found=True)
        MetricsHelper.record_booking_success(centre="Ankara")
        MetricsHelper.set_active_users(count=3)
        MetricsHelper.record_error(error_type="network", component="api")
        
        # Get metrics output
        metrics = get_metrics()
        metrics_str = metrics.decode('utf-8')
        
        # All metrics should be present
        assert 'vfs_slot_checks_total' in metrics_str
        assert 'vfs_bookings_success_total' in metrics_str
        assert 'vfs_active_users' in metrics_str
        assert 'vfs_errors_total' in metrics_str
