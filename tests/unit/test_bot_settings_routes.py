"""Tests for bot settings routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.constants import AccountPoolConfig
from web.app import create_app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    app = create_app(run_security_validation=False, env_override="testing")
    return TestClient(app)


@pytest.fixture
def mock_bot_controller():
    """Mock bot controller."""
    controller = MagicMock()

    # Mock get_cooldown_settings method
    controller.get_cooldown_settings = MagicMock(
        return_value={
            "cooldown_seconds": 600,
            "cooldown_minutes": 10,
            "quarantine_minutes": 30,
            "max_failures": 3,
        }
    )

    # Mock update_settings method
    async def mock_update_settings(**kwargs):
        return {"status": "success", **kwargs}

    controller.update_settings = AsyncMock(side_effect=mock_update_settings)

    return controller


@pytest.fixture
def mock_auth(client):
    """Mock authentication."""

    async def mock_verify_jwt_token():
        return {"sub": "test_user", "name": "Test User"}

    from web.dependencies import verify_jwt_token

    client.app.dependency_overrides[verify_jwt_token] = mock_verify_jwt_token
    yield
    client.app.dependency_overrides.clear()


class TestBotSettingsRoutes:
    """Test bot settings routes."""

    def test_get_bot_settings_default(self, client, mock_auth):
        """Test getting bot settings returns default values when controller not configured."""
        with patch("web.routes.bot._get_controller") as mock_get_controller:
            from fastapi import HTTPException

            mock_get_controller.side_effect = HTTPException(status_code=503)

            response = client.get("/api/v1/bot/settings")

            assert response.status_code == 200
            data = response.json()
            assert data["cooldown_seconds"] == AccountPoolConfig.COOLDOWN_SECONDS
            assert data["cooldown_minutes"] == round(AccountPoolConfig.COOLDOWN_SECONDS / 60)
            assert data["quarantine_minutes"] == AccountPoolConfig.QUARANTINE_SECONDS // 60
            assert data["max_failures"] == AccountPoolConfig.MAX_FAILURES

    def test_get_bot_settings_from_controller(self, client, mock_auth, mock_bot_controller):
        """Test getting bot settings from controller."""
        with patch("web.routes.bot._get_controller") as mock_get_controller:
            mock_get_controller.return_value = mock_bot_controller

            response = client.get("/api/v1/bot/settings")

            assert response.status_code == 200
            data = response.json()
            assert data["cooldown_seconds"] == 600
            assert data["cooldown_minutes"] == 10
            assert data["quarantine_minutes"] == 30
            assert data["max_failures"] == 3

    def test_update_cooldown_only(self, client, mock_auth, mock_bot_controller):
        """Test updating only cooldown (backward compatible)."""
        with patch("web.routes.bot._get_controller") as mock_get_controller:
            mock_get_controller.return_value = mock_bot_controller

            response = client.put("/api/v1/bot/settings", json={"cooldown_minutes": 15})

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

            # Verify update_settings was called with cooldown_seconds
            mock_bot_controller.update_settings.assert_called_once()
            call_kwargs = mock_bot_controller.update_settings.call_args[1]
            assert call_kwargs["cooldown_seconds"] == 900  # 15 * 60

    def test_update_all_settings(self, client, mock_auth, mock_bot_controller):
        """Test updating all bot settings at once."""
        with patch("web.routes.bot._get_controller") as mock_get_controller:
            mock_get_controller.return_value = mock_bot_controller

            response = client.put("/api/v1/bot/settings", json={
                "cooldown_minutes": 15,
                "quarantine_minutes": 45,
                "max_failures": 5,
            })

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

            call_kwargs = mock_bot_controller.update_settings.call_args[1]
            assert call_kwargs["cooldown_seconds"] == 900
            assert call_kwargs["quarantine_seconds"] == 2700  # 45 * 60
            assert call_kwargs["max_failures"] == 5

    def test_update_partial_quarantine_only(self, client, mock_auth, mock_bot_controller):
        """Test updating cooldown and quarantine only."""
        with patch("web.routes.bot._get_controller") as mock_get_controller:
            mock_get_controller.return_value = mock_bot_controller

            response = client.put("/api/v1/bot/settings", json={
                "cooldown_minutes": 10,
                "quarantine_minutes": 60,
            })

            assert response.status_code == 200
            call_kwargs = mock_bot_controller.update_settings.call_args[1]
            assert call_kwargs["cooldown_seconds"] == 600
            assert call_kwargs["quarantine_seconds"] == 3600
            assert "max_failures" not in call_kwargs

    def test_update_bot_settings_validation_min(self, client, mock_auth):
        """Test updating bot settings with value below minimum."""
        response = client.put("/api/v1/bot/settings", json={"cooldown_minutes": 4})
        assert response.status_code == 422

    def test_update_bot_settings_validation_max(self, client, mock_auth):
        """Test updating bot settings with value above maximum."""
        response = client.put("/api/v1/bot/settings", json={"cooldown_minutes": 61})
        assert response.status_code == 422

    def test_quarantine_validation_min(self, client, mock_auth):
        """Test quarantine_minutes below minimum."""
        response = client.put("/api/v1/bot/settings", json={
            "cooldown_minutes": 10,
            "quarantine_minutes": 4,
        })
        assert response.status_code == 422

    def test_quarantine_validation_max(self, client, mock_auth):
        """Test quarantine_minutes above maximum."""
        response = client.put("/api/v1/bot/settings", json={
            "cooldown_minutes": 10,
            "quarantine_minutes": 121,
        })
        assert response.status_code == 422

    def test_max_failures_validation_min(self, client, mock_auth):
        """Test max_failures below minimum."""
        response = client.put("/api/v1/bot/settings", json={
            "cooldown_minutes": 10,
            "max_failures": 0,
        })
        assert response.status_code == 422

    def test_max_failures_validation_max(self, client, mock_auth):
        """Test max_failures above maximum."""
        response = client.put("/api/v1/bot/settings", json={
            "cooldown_minutes": 10,
            "max_failures": 11,
        })
        assert response.status_code == 422

    def test_update_bot_settings_controller_not_configured(self, client, mock_auth):
        """Test updating bot settings when controller not configured returns 503."""
        with patch("web.routes.bot._get_controller") as mock_get_controller:
            from fastapi import HTTPException

            mock_get_controller.side_effect = HTTPException(status_code=503)

            response = client.put("/api/v1/bot/settings", json={"cooldown_minutes": 15})

            assert response.status_code == 503
            data = response.json()
            assert data["type"] == "urn:vfsbot:error:service-unavailable"
            assert data["title"] == "Service Unavailable"
            assert data["status"] == 503
            assert "detail" in data

    def test_start_bot_controller_not_configured(self, client, mock_auth):
        """Test starting bot when controller not configured returns 503."""
        with patch("web.routes.bot._get_controller") as mock_get_controller:
            from fastapi import HTTPException

            mock_get_controller.side_effect = HTTPException(status_code=503)
            response = client.post("/api/v1/bot/start")
            assert response.status_code == 503
            data = response.json()
            assert data["type"] == "urn:vfsbot:error:service-unavailable"
            assert data["status"] == 503

    def test_stop_bot_controller_not_configured(self, client, mock_auth):
        """Test stopping bot when controller not configured returns 503."""
        with patch("web.routes.bot._get_controller") as mock_get_controller:
            from fastapi import HTTPException

            mock_get_controller.side_effect = HTTPException(status_code=503)
            response = client.post("/api/v1/bot/stop")
            assert response.status_code == 503
            data = response.json()
            assert data["type"] == "urn:vfsbot:error:service-unavailable"
            assert data["status"] == 503

    def test_restart_bot_controller_not_configured(self, client, mock_auth):
        """Test restarting bot when controller not configured returns 503."""
        with patch("web.routes.bot._get_controller") as mock_get_controller:
            from fastapi import HTTPException

            mock_get_controller.side_effect = HTTPException(status_code=503)
            response = client.post("/api/v1/bot/restart")
            assert response.status_code == 503
            data = response.json()
            assert data["type"] == "urn:vfsbot:error:service-unavailable"
            assert data["status"] == 503

    def test_check_now_controller_not_configured(self, client, mock_auth):
        """Test check-now when controller not configured returns 503."""
        with patch("web.routes.bot._get_controller") as mock_get_controller:
            from fastapi import HTTPException

            mock_get_controller.side_effect = HTTPException(status_code=503)
            response = client.post("/api/v1/bot/check-now")
            assert response.status_code == 503
            data = response.json()
            assert data["type"] == "urn:vfsbot:error:service-unavailable"
            assert data["status"] == 503
