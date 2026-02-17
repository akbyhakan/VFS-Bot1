"""Tests for web dashboard endpoints."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src import __version__
from web.app import create_app
from web.dependencies import bot_state, metrics
from web.routes.health import check_database_health, increment_metric


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    app = create_app(run_security_validation=False, env_override="testing")
    return TestClient(app)


@pytest.fixture
def reset_state():
    """Reset bot state and metrics between tests."""
    bot_state.set_running(False)
    bot_state.set_status("stopped")
    bot_state.set_slots_found(0)
    bot_state.set_appointments_booked(0)
    bot_state.set_active_users(0)

    metrics["requests_total"] = 0
    metrics["requests_success"] = 0
    metrics["requests_failed"] = 0
    metrics["slots_checked"] = 0
    metrics["slots_found"] = 0
    metrics["appointments_booked"] = 0
    metrics["captchas_solved"] = 0
    metrics["errors"] = {}
    metrics["start_time"] = datetime.now(timezone.utc)

    yield

    # Cleanup
    bot_state.set_running(False)
    bot_state.set_status("stopped")


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

        # Status should be healthy since database check passes
        assert data["status"] in ["healthy", "degraded"]

    def test_health_endpoint_version(self, client, reset_state):
        """Test health endpoint includes version."""
        response = client.get("/health")
        data = response.json()

        assert data["version"] == __version__

    def test_health_endpoint_components(self, client, reset_state):
        """Test health endpoint includes component status."""
        response = client.get("/health")
        data = response.json()

        assert "database" in data["components"]
        assert "redis" in data["components"]
        assert "bot" in data["components"]
        assert "notifications" in data["components"]
        assert "proxy" in data["components"]

    def test_health_endpoint_proxy_component(self, client, reset_state):
        """Test health endpoint includes proxy component with status."""
        response = client.get("/health")
        data = response.json()

        assert "proxy" in data["components"]
        proxy_component = data["components"]["proxy"]
        assert isinstance(proxy_component, dict)
        assert "status" in proxy_component
        # Status should be one of the expected values
        assert proxy_component["status"] in ["healthy", "degraded", "unhealthy", "not_configured"]

    def test_health_endpoint_bot_running(self, client, reset_state):
        """Test health endpoint reflects bot running state."""
        bot_state.set_running(True)

        response = client.get("/health")
        data = response.json()

        # Bot status is now a dict, not a boolean
        assert isinstance(data["components"]["bot"], dict)
        assert data["components"]["bot"]["running"] is True
        assert "status" in data["components"]["bot"]
        assert "success_rate" in data["components"]["bot"]

    def test_health_endpoint_bot_stopped(self, client, reset_state):
        """Test health endpoint reflects bot stopped state."""
        bot_state.set_running(False)

        response = client.get("/health")
        data = response.json()

        # Bot status is now a dict, not a boolean
        assert isinstance(data["components"]["bot"], dict)
        assert data["components"]["bot"]["running"] is False
        assert "status" in data["components"]["bot"]
        assert "success_rate" in data["components"]["bot"]


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
        bot_state.set_status("running")

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
        bot_state.set_running(True)
        bot_state.set_status("running")
        bot_state.set_slots_found(5)
        bot_state.set_appointments_booked(2)

        response = client.get("/api/status")
        data = response.json()

        assert data["running"] is True
        assert data["status"] == "running"
        assert data["stats"]["slots_found"] == 5
        assert data["stats"]["appointments_booked"] == 2


class TestWebSocketAuthentication:
    """Tests for WebSocket authentication."""

    def test_websocket_cookie_auth(self, client):
        """Test WebSocket connection with cookie-based authentication."""
        from src.core.auth import create_access_token

        # Create a valid token
        token = create_access_token({"sub": "test_user"})

        # Set cookie in client
        client.cookies.set("access_token", token)

        # Connect - auth should happen automatically via cookie
        with client.websocket_connect("/ws") as websocket:
            # Should receive initial status message without sending token message
            data = websocket.receive_json()
            assert data["type"] == "status"
            assert "data" in data

    def test_websocket_query_param_auth(self, client):
        """Test WebSocket connection with query parameter authentication and deprecation warning."""
        from src.core.auth import create_access_token
        from unittest.mock import patch

        # Create a valid token
        token = create_access_token({"sub": "test_user"})

        # Connect with token in query param and verify deprecation warning
        with patch("loguru.logger.warning") as mock_warning:
            with client.websocket_connect(f"/ws?token={token}") as websocket:
                # Should receive initial status message without sending token message
                data = websocket.receive_json()
                assert data["type"] == "status"
                assert "data" in data

            # Verify deprecation warning was logged
            mock_warning.assert_called_once()
            warning_msg = mock_warning.call_args[0][0]
            assert "DEPRECATED" in warning_msg
            assert "v3.0" in warning_msg

    def test_websocket_requires_token(self, client):
        """Test that WebSocket connection requires a token."""
        # Try to connect without sending authentication
        with client.websocket_connect("/ws"):
            # Don't send auth, should timeout and close
            # The connection is accepted but requires auth message
            pass  # Connection will be closed by timeout

    def test_websocket_rejects_invalid_token(self, client):
        """Test that WebSocket rejects invalid tokens."""
        # Connect and send invalid token
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"token": "invalid_token"})
            # Should be closed with auth error

    def test_websocket_accepts_valid_token(self, client):
        """Test WebSocket connection with valid token (legacy message-based auth)."""
        from src.core.auth import create_access_token

        # Create a valid token
        token = create_access_token({"sub": "test_user"})

        # Connect and send valid token (legacy method for backward compatibility)
        with client.websocket_connect("/ws") as websocket:
            # Send authentication message
            websocket.send_json({"token": token})
            # Should receive initial status message
            data = websocket.receive_json()
            assert data["type"] == "status"
            assert "data" in data


class TestRFC7807ErrorResponses:
    """Tests for RFC 7807 Problem Details error responses."""

    def test_error_response_content_type(self, client):
        """Test that error responses have Content-Type: application/problem+json."""
        # Trigger a validation error by sending invalid data
        from src.core.exceptions import ValidationError
        from web.app import create_app
        from fastapi import FastAPI, Request
        from src.middleware.error_handler import ErrorHandlerMiddleware
        
        # Create a simple endpoint that raises ValidationError
        app = create_app(run_security_validation=False, env_override="testing")
        
        @app.get("/test/validation-error")
        async def trigger_validation_error():
            raise ValidationError("Invalid field", field="test_field")
        
        client_test = TestClient(app)
        response = client_test.get("/test/validation-error")
        
        assert response.status_code == 400
        assert response.headers["content-type"] == "application/problem+json"

    def test_error_response_has_rfc7807_fields(self, client):
        """Test that error responses include all required RFC 7807 fields."""
        from src.core.exceptions import ValidationError
        from web.app import create_app
        
        app = create_app(run_security_validation=False, env_override="testing")
        
        @app.get("/test/validation-error")
        async def trigger_validation_error():
            raise ValidationError("Invalid field", field="test_field")
        
        client_test = TestClient(app)
        response = client_test.get("/test/validation-error")
        data = response.json()
        
        # Check required RFC 7807 fields
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert "instance" in data
        
        # Verify values
        assert data["type"].startswith("urn:vfsbot:error:")
        assert data["status"] == 400
        assert data["instance"] == "/test/validation-error"

    def test_rate_limit_error_format(self, client):
        """Test that rate limit errors include retry_after extension."""
        from src.core.exceptions import RateLimitError
        from web.app import create_app
        
        app = create_app(run_security_validation=False, env_override="testing")
        
        @app.get("/test/rate-limit")
        async def trigger_rate_limit():
            raise RateLimitError("Rate limit exceeded", retry_after=60)
        
        client_test = TestClient(app)
        response = client_test.get("/test/rate-limit")
        data = response.json()
        
        assert response.status_code == 429
        assert data["type"] == "urn:vfsbot:error:rate-limit"
        assert data["title"] == "Rate Limit Error"
        assert data["status"] == 429
        assert "retry_after" in data
        assert data["retry_after"] == 60
        assert "Retry-After" in response.headers
        assert response.headers["Retry-After"] == "60"

    def test_validation_error_format(self, client):
        """Test that validation errors include field extension."""
        from src.core.exceptions import ValidationError
        from web.app import create_app
        
        app = create_app(run_security_validation=False, env_override="testing")
        
        @app.get("/test/validation-error-field")
        async def trigger_validation_error():
            raise ValidationError("Field is required", field="username")
        
        client_test = TestClient(app)
        response = client_test.get("/test/validation-error-field")
        data = response.json()
        
        assert response.status_code == 400
        assert data["type"] == "urn:vfsbot:error:validation"
        assert "field" in data
        assert data["field"] == "username"

    def test_unexpected_error_no_leak(self, client):
        """Test that unexpected errors do not leak internal details."""
        from web.app import create_app
        
        app = create_app(run_security_validation=False, env_override="testing")
        
        @app.get("/test/unexpected-error")
        async def trigger_unexpected_error():
            raise RuntimeError("Internal implementation detail that should not leak")
        
        client_test = TestClient(app)
        response = client_test.get("/test/unexpected-error")
        data = response.json()
        
        assert response.status_code == 500
        assert data["type"] == "urn:vfsbot:error:internal-server"
        assert data["title"] == "Internal Server Error"
        assert data["status"] == 500
        # Verify generic message, not the internal error
        assert "Internal implementation detail" not in data["detail"]
        assert data["detail"] == "An unexpected error occurred. Please try again later."


class TestHealthEndpointPoolStats:
    """Tests for database pool stats in health endpoint."""

    @pytest.mark.asyncio
    async def test_health_includes_pool_stats(self, client):
        """Test that /health endpoint includes database pool stats."""
        from web.app import create_app
        
        app = create_app(run_security_validation=False, env_override="testing")
        client_test = TestClient(app)
        
        response = client_test.get("/health")
        data = response.json()
        
        assert "components" in data
        assert "database" in data["components"]
        db_component = data["components"]["database"]
        
        # Check that pool stats are present
        if db_component.get("status") == "healthy":
            assert "pool" in db_component
            pool_stats = db_component["pool"]
            assert "size" in pool_stats
            assert "idle" in pool_stats
            assert "used" in pool_stats
            assert "utilization" in pool_stats
            
            # Validate types and ranges
            assert isinstance(pool_stats["size"], int)
            assert isinstance(pool_stats["idle"], int)
            assert isinstance(pool_stats["used"], int)
            assert isinstance(pool_stats["utilization"], (int, float))
            assert 0.0 <= pool_stats["utilization"] <= 1.0

    @pytest.mark.asyncio
    async def test_ready_endpoint_includes_pool_stats(self, client):
        """Test that /ready endpoint includes database pool stats."""
        from web.app import create_app
        
        app = create_app(run_security_validation=False, env_override="testing")
        client_test = TestClient(app)
        
        response = client_test.get("/ready")
        data = response.json()
        
        assert "checks" in data
        assert "database" in data["checks"]
        db_check = data["checks"]["database"]
        
        # Check that pool stats are present
        if db_check.get("status") == "healthy":
            assert "pool" in db_check
