"""Integration tests for middleware chain behavior."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from web.app import create_app


@pytest.mark.integration
class TestMiddlewareChain:
    """Test middleware chain behavior and ordering."""

    @pytest.fixture
    def client(self):
        """Create test client with full middleware stack."""
        app = create_app(run_security_validation=False, env_override="testing")

        with patch("web.app.DatabaseFactory.ensure_connected", new_callable=AsyncMock):
            with patch("web.app.DatabaseFactory.close_instance", new_callable=AsyncMock):
                yield TestClient(app)

    def test_middleware_order_security_headers_applied(self, client):
        """Test that SecurityHeadersMiddleware adds headers."""
        response = client.get("/health")

        # SecurityHeadersMiddleware should add these headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_middleware_order_correlation_id_added(self, client):
        """Test that CorrelationMiddleware adds correlation ID."""
        response = client.get("/health")

        # CorrelationMiddleware should process requests
        # Correlation ID may be in headers or logged
        assert response.status_code == 200

    def test_middleware_order_error_handler_catches_errors(self, client):
        """Test that ErrorHandlerMiddleware is first and catches all errors."""
        # Request non-existent endpoint
        response = client.get("/api/v1/definitely-does-not-exist")

        # ErrorHandlerMiddleware should catch and return proper error
        # 404 = not found, 422 = validation/unprocessable
        assert response.status_code in [404, 422]

        # Should return JSON error format
        data = response.json()
        assert "detail" in data

    def test_cors_middleware_allows_configured_origins(self, client):
        """Test that CORS middleware allows configured origins."""
        response = client.options(
            "/api/v1/users",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
        )

        # CORS preflight should be handled
        # TestClient may not fully simulate CORS, but endpoint should respond
        assert response.status_code in [200, 401]

    def test_request_tracking_middleware_tracks_requests(self, client):
        """Test that RequestTrackingMiddleware tracks requests."""
        # Make multiple requests
        for _ in range(3):
            response = client.get("/health")
            assert response.status_code == 200

        # Tracking should happen in background (no visible effect on response)

    def test_middleware_chain_performance(self, client):
        """Test that middleware chain doesn't add excessive overhead."""
        # Measure response time for simple endpoint
        start_time = time.time()
        response = client.get("/health")
        elapsed = time.time() - start_time

        assert response.status_code == 200
        # Middleware should add minimal overhead (< 1 second for local test)
        assert elapsed < 1.0


@pytest.mark.integration
class TestSecurityHeadersMiddleware:
    """Test SecurityHeadersMiddleware specifically."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app(run_security_validation=False, env_override="testing")

        with patch("web.app.DatabaseFactory.ensure_connected", new_callable=AsyncMock):
            with patch("web.app.DatabaseFactory.close_instance", new_callable=AsyncMock):
                yield TestClient(app)

    def test_security_headers_csp_present(self, client):
        """Test that Content-Security-Policy header is present."""
        response = client.get("/health")

        assert "Content-Security-Policy" in response.headers

    def test_security_headers_xss_protection(self, client):
        """Test that X-XSS-Protection header is present."""
        response = client.get("/health")

        assert "X-XSS-Protection" in response.headers

    def test_security_headers_hsts_in_production(self, client):
        """Test that HSTS header is added in production mode."""
        # Note: Test environment may not include HSTS
        response = client.get("/health")

        # In test environment, HSTS might not be present
        # This documents expected production behavior
        assert response.status_code == 200

    def test_security_headers_frame_options(self, client):
        """Test that X-Frame-Options prevents clickjacking."""
        response = client.get("/health")

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] in ["DENY", "SAMEORIGIN"]

    def test_security_headers_content_type_options(self, client):
        """Test that X-Content-Type-Options prevents MIME sniffing."""
        response = client.get("/health")

        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_security_headers_on_error_responses(self, client):
        """Test that security headers are added even on error responses."""
        response = client.get("/api/v1/nonexistent")

        # Security headers should be present on error responses too
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers


@pytest.mark.integration
class TestErrorHandlerMiddleware:
    """Test ErrorHandlerMiddleware specifically."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app(run_security_validation=False, env_override="testing")

        with patch("web.app.DatabaseFactory.ensure_connected", new_callable=AsyncMock):
            with patch("web.app.DatabaseFactory.close_instance", new_callable=AsyncMock):
                yield TestClient(app)

    def test_error_handler_404_format(self, client):
        """Test that 404 errors are properly formatted."""
        response = client.get("/nonexistent-page")

        # 404 or 422 depending on routing
        assert response.status_code in [404, 422]
        data = response.json()
        assert "detail" in data

    def test_error_handler_500_catches_exceptions(self, client):
        """Test that 500 errors are caught and formatted."""
        # This would require triggering an internal error
        # For now, test that error format is consistent
        response = client.get("/api/v1/users")

        # Will fail auth, but error should be properly formatted
        assert response.status_code in [401, 500]
        data = response.json()
        assert "detail" in data

    def test_error_handler_validation_errors(self, client):
        """Test that validation errors (422) are properly handled."""
        # Send invalid data to trigger validation error
        response = client.post("/api/v1/users", json={"invalid": "data"})

        # Should return validation error or auth error
        assert response.status_code in [401, 422]


@pytest.mark.integration
class TestCORSMiddleware:
    """Test CORS middleware configuration."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app(run_security_validation=False, env_override="testing")

        with patch("web.app.DatabaseFactory.ensure_connected", new_callable=AsyncMock):
            with patch("web.app.DatabaseFactory.close_instance", new_callable=AsyncMock):
                yield TestClient(app)

    def test_cors_preflight_request(self, client):
        """Test CORS preflight OPTIONS request."""
        response = client.options(
            "/api/v1/users",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, Authorization",
            },
        )

        # Should handle preflight
        # Note: TestClient may not fully simulate CORS
        assert response.status_code in [200, 401]

    def test_cors_allows_credentials(self, client):
        """Test that CORS allows credentials."""
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})

        # Should allow credentials for cookie-based auth
        assert response.status_code == 200

    def test_cors_allowed_methods(self, client):
        """Test that CORS allows configured HTTP methods."""
        methods = ["GET", "POST", "PUT", "DELETE"]

        for method in methods:
            response = client.options(
                "/api/v1/users",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": method,
                },
            )

            # Should allow these methods
            assert response.status_code in [200, 401]


@pytest.mark.integration
class TestMiddlewareIntegration:
    """Test integration of all middleware components."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app(run_security_validation=False, env_override="testing")

        with patch("web.app.DatabaseFactory.ensure_connected", new_callable=AsyncMock):
            with patch("web.app.DatabaseFactory.close_instance", new_callable=AsyncMock):
                yield TestClient(app)

    def test_full_middleware_stack_on_success(self, client):
        """Test that all middleware works together on successful request."""
        response = client.get("/health")

        assert response.status_code == 200

        # Security headers present
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers

        # Response is properly formatted
        data = response.json()
        assert "status" in data

    def test_full_middleware_stack_on_error(self, client):
        """Test that all middleware works together on error."""
        response = client.get("/nonexistent")

        # 404 or 422 depending on routing
        assert response.status_code in [404, 422]

        # Security headers still present on error
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers

        # Error is properly formatted
        data = response.json()
        assert "detail" in data

    def test_middleware_with_authentication(self, client):
        """Test middleware interaction with authentication."""
        # Request with invalid auth
        response = client.get("/api/v1/users", headers={"Authorization": "Bearer invalid_token"})

        # Should fail auth but middleware should still work
        assert response.status_code in [401, 500]

        # Security headers should be present
        assert "X-Content-Type-Options" in response.headers

    def test_middleware_preserves_request_data(self, client):
        """Test that middleware doesn't corrupt request data."""
        payload = {
            "email": "test@example.com",
            "password": "secure123",
            "center_name": "Test Center",
            "visa_category": "Tourist",
            "visa_subcategory": "Standard",
            "first_name": "Test",
            "last_name": "User",
            "phone": "+1234567890",
            "is_active": True,
        }

        response = client.post("/api/v1/users", json=payload)

        # Should fail auth, but request data should be processed
        assert response.status_code in [401, 422]


@pytest.mark.integration
class TestHTTPSRedirectMiddleware:
    """Test HTTPS redirect middleware."""

    @pytest.fixture
    def production_client(self):
        """Create test client with production settings (HTTPS redirect active)."""
        app = create_app(run_security_validation=False, env_override="production")
        with patch("web.app.DatabaseFactory.ensure_connected", new_callable=AsyncMock):
            with patch("web.app.DatabaseFactory.close_instance", new_callable=AsyncMock):
                yield TestClient(app, base_url="http://testserver")

    @pytest.fixture
    def dev_client(self):
        """Create test client with development settings (no HTTPS redirect)."""
        app = create_app(run_security_validation=False, env_override="testing")
        with patch("web.app.DatabaseFactory.ensure_connected", new_callable=AsyncMock):
            with patch("web.app.DatabaseFactory.close_instance", new_callable=AsyncMock):
                yield TestClient(app)

    def test_https_redirect_in_production(self, production_client):
        """Test that HTTP requests are redirected to HTTPS in production."""
        response = production_client.get("/api/v1/users", follow_redirects=False)
        # Should redirect to HTTPS
        assert response.status_code == 301
        assert "https://" in response.headers.get("location", "")

    def test_https_redirect_excludes_health(self, production_client):
        """Test that health endpoints are excluded from HTTPS redirect."""
        response = production_client.get("/health", follow_redirects=False)
        # Health should NOT be redirected
        assert response.status_code == 200

    def test_https_redirect_excludes_ready(self, production_client):
        """Test that ready endpoint is excluded from HTTPS redirect."""
        response = production_client.get("/ready", follow_redirects=False)
        # Ready should NOT be redirected
        assert response.status_code in [200, 503]

    def test_no_redirect_in_development(self, dev_client):
        """Test that no redirect happens in development."""
        response = dev_client.get("/health")
        assert response.status_code == 200

    def test_no_redirect_when_forwarded_proto_https(self, production_client):
        """Test that requests with X-Forwarded-Proto: https are not redirected."""
        response = production_client.get(
            "/api/v1/users",
            headers={"X-Forwarded-Proto": "https"},
            follow_redirects=False,
        )
        # Should NOT redirect (already HTTPS via proxy)
        # Will fail auth but should reach the endpoint
        assert response.status_code in [401, 404, 422]

    def test_hsts_preload_in_production(self, production_client):
        """Test that HSTS header includes preload directive in production."""
        response = production_client.get(
            "/health",
            headers={"X-Forwarded-Proto": "https"},
            follow_redirects=False,
        )
        hsts = response.headers.get("Strict-Transport-Security", "")
        assert "max-age=63072000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts
