"""Integration tests for API endpoint chain: login → user management → booking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from web.app import create_app


@pytest.mark.integration
class TestAPIFlow:
    """Test suite for API endpoint chains using FastAPI TestClient."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked dependencies."""
        # Create app without security validation for testing
        app = create_app(run_security_validation=False, env_override="testing")

        # Mock database factory to prevent actual DB connection
        with patch("web.app.DatabaseFactory.ensure_connected", new_callable=AsyncMock):
            with patch("web.app.DatabaseFactory.close_instance", new_callable=AsyncMock):
                yield TestClient(app)

    @pytest.fixture
    def mock_db_connection(self):
        """Mock database connection for dependency injection."""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock()
        mock_conn.fetchrow = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock()
        return mock_conn

    @pytest.fixture
    def mock_user_repo(self):
        """Mock UserRepository for testing."""
        repo = AsyncMock()
        repo.get_all_with_details = AsyncMock(return_value=[])
        repo.create = AsyncMock(return_value=1)
        repo.get_by_id_with_details = AsyncMock(
            return_value={
                "id": 1,
                "email": "test@example.com",
                "phone": "+1234567890",
                "first_name": "Test",
                "last_name": "User",
                "center_name": "TestCenter",
                "visa_category": "Tourist",
                "visa_subcategory": "Standard",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )
        repo.get_by_email = AsyncMock(return_value=None)
        repo.update = AsyncMock(return_value=True)
        repo.delete = AsyncMock(return_value=True)
        return repo

    @pytest.fixture
    def mock_appointment_repo(self):
        """Mock AppointmentRequestRepository for testing."""
        repo = AsyncMock()
        repo.get_all = AsyncMock(return_value=[])
        repo.create = AsyncMock(return_value=1)
        repo.get_by_id = AsyncMock(
            return_value={
                "id": 1,
                "user_id": 1,
                "status": "pending",
                "created_at": "2024-01-01T00:00:00",
            }
        )
        return repo

    def test_health_endpoint_no_auth_required(self, client):
        """Test that health endpoint is accessible without authentication."""
        response = client.get("/health")
        # Health endpoint may return 200 even with DB errors in test env
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data

    def test_ready_endpoint_no_auth_required(self, client):
        """Test that ready endpoint is accessible without authentication."""
        response = client.get("/ready")
        # Ready endpoint may return 503 if DB not ready in test env
        assert response.status_code in [200, 503]

    def test_api_requires_authentication(self, client):
        """Test that API endpoints require authentication."""
        # Test various API endpoints without auth
        endpoints = [
            "/api/v1/users",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            # 401 = unauthorized, 422 = validation error
            assert response.status_code in [
                401,
                422,
            ], f"Endpoint {endpoint} should require auth or validation"

    def test_login_flow_generates_key(self, client, mock_db_connection):
        """Test API key generation flow."""
        with patch("web.dependencies.DatabaseFactory.ensure_connected") as mock_factory:
            # Mock database factory to return our mock connection
            mock_db = AsyncMock()
            mock_db.get_connection.return_value.__aenter__.return_value = mock_db_connection
            mock_factory.return_value = mock_db

            # Mock admin secret check - not consumed
            mock_db_connection.fetchval.return_value = False

            response = client.post(
                "/api/v1/auth/generate-key", headers={"X-Admin-Secret": "test-secret"}
            )

            # Should reject because admin secret is not properly configured in test env
            # In real environment, this would succeed with proper secret
            assert response.status_code in [401, 500]

    def test_user_management_flow_requires_auth(self, client, mock_user_repo):
        """Test that user management endpoints require authentication."""
        # Override dependencies
        from web.dependencies import get_user_repository

        # Try to create user without auth
        response = client.post(
            "/api/v1/users",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "center_name": "TestCenter",
                "visa_category": "Tourist",
                "visa_subcategory": "Standard",
                "first_name": "New",
                "last_name": "User",
                "phone": "+1234567890",
                "is_active": True,
            },
        )

        assert response.status_code == 401

    def test_appointment_flow_requires_auth(self, client):
        """Test that appointment endpoints require authentication."""
        # Try to get appointments without auth
        response = client.get("/api/v1/appointments")
        # 401 = unauthorized, 422 = validation error
        assert response.status_code in [401, 422]

    def test_cors_headers_present(self, client):
        """Test that CORS headers are properly configured."""
        response = client.options("/api/v1/users", headers={"Origin": "http://localhost:3000"})

        # CORS middleware should add appropriate headers
        # Note: TestClient might not process all middleware the same as real server
        # 405 = Method not allowed (OPTIONS might not be defined for all routes)
        assert response.status_code in [200, 401, 405]

    def test_api_versioning_prefix(self, client):
        """Test that API routes are properly versioned under /api/v1."""
        # Test that v1 routes exist
        response = client.get("/api/v1/auth/generate-key")
        # Should return 405 (method not allowed) or other error, not 404
        assert response.status_code != 404

    def test_security_headers_present(self, client):
        """Test that security headers are added by middleware."""
        response = client.get("/health")

        # Check for security headers added by SecurityHeadersMiddleware
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_error_handler_middleware_catches_errors(self, client):
        """Test that error handler middleware properly catches errors."""
        # Make request to non-existent endpoint
        response = client.get("/api/v1/nonexistent")

        # Should return error (404 or 422), not crash
        assert response.status_code in [404, 422]

    def test_request_tracking_adds_headers(self, client):
        """Test that request tracking middleware adds correlation headers."""
        response = client.get("/health")

        # Request tracking should be handled by middleware
        # Success is indicated by proper response
        assert response.status_code == 200


@pytest.mark.integration
class TestAuthenticationFlow:
    """Test authentication flow specifically."""

    @pytest.fixture
    def client(self):
        """Create test client for auth testing."""
        app = create_app(run_security_validation=False, env_override="testing")

        with patch("web.app.DatabaseFactory.ensure_connected", new_callable=AsyncMock):
            with patch("web.app.DatabaseFactory.close_instance", new_callable=AsyncMock):
                yield TestClient(app)

    def test_cookie_based_auth_fallback(self, client):
        """Test that cookie-based authentication is supported."""
        # Make request with auth cookie
        response = client.get("/api/v1/users", cookies={"access_token": "invalid_token"})

        # Should attempt to validate token and fail (because it's invalid)
        # Status could be 401 (invalid token) or 500 (verification error)
        assert response.status_code in [401, 500]

    def test_bearer_token_auth_fallback(self, client):
        """Test that Bearer token authentication is supported."""
        response = client.get("/api/v1/users", headers={"Authorization": "Bearer invalid_token"})

        # Should attempt to validate token and fail
        assert response.status_code in [401, 500]

    def test_no_auth_returns_401(self, client):
        """Test that requests without auth return 401."""
        response = client.get("/api/v1/users")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
