"""Tests for web dashboard endpoints."""

import pytest
from fastapi.testclient import TestClient

from web.app import app, bot_state, metrics, check_database_health, increment_metric


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def reset_state():
    """Reset bot state and metrics between tests."""
    bot_state["running"] = False
    bot_state["status"] = "stopped"
    bot_state["slots_found"] = 0
    bot_state["appointments_booked"] = 0
    bot_state["active_users"] = 0
    
    metrics["requests_total"] = 0
    metrics["requests_success"] = 0
    metrics["requests_failed"] = 0
    metrics["slots_checked"] = 0
    metrics["slots_found"] = 0
    metrics["appointments_booked"] = 0
    metrics["captchas_solved"] = 0
    metrics["errors"] = {}
    
    yield
    
    # Cleanup
    bot_state["running"] = False
    bot_state["status"] = "stopped"


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_endpoint_returns_200(self, client, reset_state):
        """Test that health endpoint returns 200 OK."""
        response = client.get("/health")
        
        assert response.status_code == 200

    def test_health_endpoint_structure(self, client, reset_state):
        """Test health endpoint response structure."""
        response = client.get("/health")
        data = response.json()
        
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "components" in data

    def test_health_endpoint_status(self, client, reset_state):
        """Test health endpoint returns healthy status."""
        response = client.get("/health")
        data = response.json()
        
        assert data["status"] == "healthy"

    def test_health_endpoint_version(self, client, reset_state):
        """Test health endpoint includes version."""
        response = client.get("/health")
        data = response.json()
        
        assert data["version"] == "2.0.0"

    def test_health_endpoint_components(self, client, reset_state):
        """Test health endpoint includes component status."""
        response = client.get("/health")
        data = response.json()
        
        assert "database" in data["components"]
        assert "bot" in data["components"]
        assert "notifications" in data["components"]

    def test_health_endpoint_bot_running(self, client, reset_state):
        """Test health endpoint reflects bot running state."""
        bot_state["running"] = True
        
        response = client.get("/health")
        data = response.json()
        
        assert data["components"]["bot"] is True

    def test_health_endpoint_bot_stopped(self, client, reset_state):
        """Test health endpoint reflects bot stopped state."""
        bot_state["running"] = False
        
        response = client.get("/health")
        data = response.json()
        
        assert data["components"]["bot"] is False


class TestMetricsEndpoint:
    """Tests for /metrics endpoint."""

    def test_metrics_endpoint_returns_200(self, client, reset_state):
        """Test that metrics endpoint returns 200 OK."""
        response = client.get("/metrics")
        
        assert response.status_code == 200

    def test_metrics_endpoint_structure(self, client, reset_state):
        """Test metrics endpoint response structure."""
        response = client.get("/metrics")
        data = response.json()
        
        assert "uptime_seconds" in data
        assert "requests_total" in data
        assert "requests_success" in data
        assert "requests_failed" in data
        assert "success_rate" in data
        assert "slots_checked" in data
        assert "slots_found" in data
        assert "appointments_booked" in data
        assert "captchas_solved" in data
        assert "errors_by_type" in data
        assert "bot_status" in data

    def test_metrics_endpoint_initial_values(self, client, reset_state):
        """Test metrics endpoint returns correct initial values."""
        response = client.get("/metrics")
        data = response.json()
        
        assert data["requests_total"] == 0
        assert data["requests_success"] == 0
        assert data["requests_failed"] == 0
        assert data["slots_checked"] == 0
        assert data["slots_found"] == 0
        assert data["appointments_booked"] == 0

    def test_metrics_endpoint_success_rate_zero_requests(self, client, reset_state):
        """Test success rate calculation with zero requests."""
        response = client.get("/metrics")
        data = response.json()
        
        # Should handle division by zero
        assert data["success_rate"] == 0.0

    def test_metrics_endpoint_success_rate(self, client, reset_state):
        """Test success rate calculation."""
        metrics["requests_total"] = 10
        metrics["requests_success"] = 7
        
        response = client.get("/metrics")
        data = response.json()
        
        assert data["success_rate"] == 0.7

    def test_metrics_endpoint_uptime(self, client, reset_state):
        """Test uptime is a positive number."""
        response = client.get("/metrics")
        data = response.json()
        
        assert data["uptime_seconds"] >= 0

    def test_metrics_endpoint_bot_status(self, client, reset_state):
        """Test bot status in metrics."""
        bot_state["status"] = "running"
        
        response = client.get("/metrics")
        data = response.json()
        
        assert data["bot_status"] == "running"


class TestIncrementMetric:
    """Tests for increment_metric function."""

    def test_increment_metric_default(self, reset_state):
        """Test increment_metric with default count."""
        metrics["requests_total"] = 5
        
        increment_metric("requests_total")
        
        assert metrics["requests_total"] == 6

    def test_increment_metric_custom_count(self, reset_state):
        """Test increment_metric with custom count."""
        metrics["slots_found"] = 10
        
        increment_metric("slots_found", count=5)
        
        assert metrics["slots_found"] == 15

    def test_increment_metric_invalid_name(self, reset_state):
        """Test increment_metric with invalid metric name."""
        # Should not raise an error, just do nothing
        increment_metric("invalid_metric", count=5)
        
        # Metrics should remain unchanged
        assert "invalid_metric" not in metrics


class TestCheckDatabaseHealth:
    """Tests for check_database_health function."""

    @pytest.mark.asyncio
    async def test_check_database_health_returns_true(self):
        """Test that database health check returns True."""
        result = await check_database_health()
        
        assert result is True


class TestApiStatusEndpoint:
    """Tests for /api/status endpoint."""

    def test_api_status_endpoint(self, client, reset_state):
        """Test /api/status endpoint returns correct data."""
        bot_state["running"] = True
        bot_state["status"] = "running"
        bot_state["slots_found"] = 5
        bot_state["appointments_booked"] = 2
        
        response = client.get("/api/status")
        data = response.json()
        
        assert data["running"] is True
        assert data["status"] == "running"
        assert data["stats"]["slots_found"] == 5
        assert data["stats"]["appointments_booked"] == 2
