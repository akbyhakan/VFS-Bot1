"""Tests for audit log routes."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from web.app import create_app
from src.repositories.audit_log_repository import AuditLogEntry


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    app = create_app(run_security_validation=False, env_override="testing")
    return TestClient(app)


@pytest.fixture
def mock_audit_repo(monkeypatch):
    """Mock audit log repository."""
    mock_repo = MagicMock()
    
    # Mock get_all method
    mock_repo.get_all = AsyncMock(return_value=[
        {
            "id": 1,
            "action": "login_success",
            "user_id": 1,
            "username": "testuser",
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
            "details": '{"login_method": "password"}',
            "timestamp": "2024-01-01T10:00:00Z",
            "success": True,
            "resource_type": None,
            "resource_id": None,
        },
        {
            "id": 2,
            "action": "user_created",
            "user_id": 1,
            "username": "admin",
            "ip_address": "192.168.1.2",
            "user_agent": "Mozilla/5.0",
            "details": '{"new_user_id": 2}',
            "timestamp": "2024-01-01T11:00:00Z",
            "success": True,
            "resource_type": "user",
            "resource_id": "2",
        },
        {
            "id": 3,
            "action": "login_failure",
            "user_id": None,
            "username": "unknown",
            "ip_address": "192.168.1.3",
            "user_agent": "Mozilla/5.0",
            "details": '{"reason": "invalid_credentials"}',
            "timestamp": "2024-01-01T12:00:00Z",
            "success": False,
            "resource_type": None,
            "resource_id": None,
        },
    ])
    
    # Mock get_by_id method
    async def mock_get_by_id(log_id: int):
        if log_id == 1:
            return AuditLogEntry(
                id=1,
                action="login_success",
                user_id=1,
                username="testuser",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
                details='{"login_method": "password"}',
                timestamp="2024-01-01T10:00:00Z",
                success=True,
            )
        return None
    
    mock_repo.get_by_id = AsyncMock(side_effect=mock_get_by_id)
    
    # Monkeypatch the dependency
    async def mock_get_audit_log_repository():
        return mock_repo
    
    from web import routes
    monkeypatch.setattr(routes.audit, "get_audit_log_repository", lambda: mock_repo)
    
    return mock_repo


@pytest.fixture
def mock_auth_token(monkeypatch):
    """Mock JWT token verification."""
    async def mock_verify_jwt_token(request):
        return {"sub": "testuser", "user_id": 1}
    
    from web import routes
    monkeypatch.setattr(routes.audit, "verify_jwt_token", mock_verify_jwt_token)


class TestAuditLogRoutes:
    """Tests for audit log routes."""
    
    def test_list_audit_logs_requires_auth(self, client):
        """Test that audit log listing requires authentication."""
        response = client.get("/api/v1/audit/logs")
        assert response.status_code == 401
    
    def test_list_audit_logs_success(self, client, mock_audit_repo, mock_auth_token):
        """Test successful audit log listing."""
        # Create a mock dependency override
        from web.dependencies import get_audit_log_repository
        
        async def override_get_audit_log_repository():
            return mock_audit_repo
        
        # Override the dependency
        from web.app import create_app
        app = create_app(run_security_validation=False, env_override="testing")
        app.dependency_overrides[get_audit_log_repository] = override_get_audit_log_repository
        
        client = TestClient(app)
        
        # Mock token verification
        from web.dependencies import verify_jwt_token
        async def mock_verify():
            return {"sub": "testuser", "user_id": 1}
        app.dependency_overrides[verify_jwt_token] = mock_verify
        
        response = client.get("/api/v1/audit/logs")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3
        assert data[0]["action"] == "login_success"
        assert data[0]["username"] == "testuser"
    
    def test_list_audit_logs_with_filters(self, client, mock_audit_repo, mock_auth_token):
        """Test audit log listing with filters."""
        from web.dependencies import get_audit_log_repository, verify_jwt_token
        from web.app import create_app
        
        app = create_app(run_security_validation=False, env_override="testing")
        
        async def override_get_audit_log_repository():
            return mock_audit_repo
        
        async def mock_verify():
            return {"sub": "testuser", "user_id": 1}
        
        app.dependency_overrides[get_audit_log_repository] = override_get_audit_log_repository
        app.dependency_overrides[verify_jwt_token] = mock_verify
        
        client = TestClient(app)
        
        # Test with limit
        response = client.get("/api/v1/audit/logs?limit=2")
        assert response.status_code == 200
        
        # Test with action filter
        response = client.get("/api/v1/audit/logs?action=login_success")
        assert response.status_code == 200
        
        # Test with user_id filter
        response = client.get("/api/v1/audit/logs?user_id=1")
        assert response.status_code == 200
        
        # Test with success filter
        response = client.get("/api/v1/audit/logs?success=true")
        assert response.status_code == 200
        data = response.json()
        # Should filter out the failed login
        assert all(log["success"] for log in data)
    
    def test_get_audit_log_by_id_requires_auth(self, client):
        """Test that getting a specific audit log requires authentication."""
        response = client.get("/api/v1/audit/logs/1")
        assert response.status_code == 401
    
    def test_get_audit_log_by_id_success(self, client, mock_audit_repo, mock_auth_token):
        """Test successful retrieval of a specific audit log."""
        from web.dependencies import get_audit_log_repository, verify_jwt_token
        from web.app import create_app
        
        app = create_app(run_security_validation=False, env_override="testing")
        
        async def override_get_audit_log_repository():
            return mock_audit_repo
        
        async def mock_verify():
            return {"sub": "testuser", "user_id": 1}
        
        app.dependency_overrides[get_audit_log_repository] = override_get_audit_log_repository
        app.dependency_overrides[verify_jwt_token] = mock_verify
        
        client = TestClient(app)
        
        response = client.get("/api/v1/audit/logs/1")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == 1
        assert data["action"] == "login_success"
        assert data["username"] == "testuser"
    
    def test_get_audit_log_by_id_not_found(self, client, mock_audit_repo, mock_auth_token):
        """Test retrieval of non-existent audit log."""
        from web.dependencies import get_audit_log_repository, verify_jwt_token
        from web.app import create_app
        
        app = create_app(run_security_validation=False, env_override="testing")
        
        async def override_get_audit_log_repository():
            return mock_audit_repo
        
        async def mock_verify():
            return {"sub": "testuser", "user_id": 1}
        
        app.dependency_overrides[get_audit_log_repository] = override_get_audit_log_repository
        app.dependency_overrides[verify_jwt_token] = mock_verify
        
        client = TestClient(app)
        
        response = client.get("/api/v1/audit/logs/999")
        assert response.status_code == 404
    
    def test_get_audit_stats_requires_auth(self, client):
        """Test that audit stats endpoint requires authentication."""
        response = client.get("/api/v1/audit/stats")
        assert response.status_code == 401
    
    def test_get_audit_stats_success(self, client, mock_audit_repo, mock_auth_token):
        """Test successful retrieval of audit statistics."""
        from web.dependencies import get_audit_log_repository, verify_jwt_token
        from web.app import create_app
        
        app = create_app(run_security_validation=False, env_override="testing")
        
        async def override_get_audit_log_repository():
            return mock_audit_repo
        
        async def mock_verify():
            return {"sub": "testuser", "user_id": 1}
        
        app.dependency_overrides[get_audit_log_repository] = override_get_audit_log_repository
        app.dependency_overrides[verify_jwt_token] = mock_verify
        
        client = TestClient(app)
        
        response = client.get("/api/v1/audit/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "total" in data
        assert "by_action" in data
        assert "success_rate" in data
        assert "recent_failures" in data
        
        assert data["total"] == 3
        assert data["by_action"]["login_success"] == 1
        assert data["by_action"]["user_created"] == 1
        assert data["by_action"]["login_failure"] == 1
        
        # Success rate: 2 successes out of 3 total
        assert data["success_rate"] == pytest.approx(2/3, rel=0.01)
