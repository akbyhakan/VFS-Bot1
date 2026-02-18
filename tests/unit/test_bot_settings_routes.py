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

    # Mock update_cooldown method
    async def mock_update_cooldown(cooldown_seconds):
        return {"status": "success", "cooldown_seconds": cooldown_seconds}

    controller.update_cooldown = AsyncMock(side_effect=mock_update_cooldown)

    return controller


@pytest.fixture
def mock_auth(monkeypatch):
    """Mock authentication."""

    async def mock_verify_hybrid_auth():
        return {"sub": "test_user", "name": "Test User"}

    from web import routes

    monkeypatch.setattr(routes.bot, "verify_hybrid_auth", lambda: mock_verify_hybrid_auth())


class TestBotSettingsRoutes:
    """Test bot settings routes."""

    def test_get_bot_settings_default(self, client, mock_auth):
        """Test getting bot settings returns default values when controller not configured."""
        # Patch BotController.get_instance to raise HTTPException
        with patch("web.routes.bot._get_controller") as mock_get_controller:
            from fastapi import HTTPException

            mock_get_controller.side_effect = HTTPException(status_code=503)

            response = client.get("/api/bot/settings")

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

            response = client.get("/api/bot/settings")

            assert response.status_code == 200
            data = response.json()
            assert data["cooldown_seconds"] == 600
            assert data["cooldown_minutes"] == 10
            assert data["quarantine_minutes"] == 30
            assert data["max_failures"] == 3

    @pytest.mark.asyncio
    async def test_update_bot_settings_success(self, client, mock_auth, mock_bot_controller):
        """Test updating bot settings successfully."""
        with patch("web.routes.bot._get_controller") as mock_get_controller:
            mock_get_controller.return_value = mock_bot_controller

            response = client.put("/api/bot/settings", json={"cooldown_minutes": 15})

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "15 dakikaya güncellendi" in data["message"]

            # Verify update_cooldown was called with correct seconds
            mock_bot_controller.update_cooldown.assert_called_once()
            call_args = mock_bot_controller.update_cooldown.call_args
            assert call_args[0][0] == 900  # 15 minutes * 60 seconds

    def test_update_bot_settings_validation_min(self, client, mock_auth):
        """Test updating bot settings with value below minimum."""
        response = client.put("/api/bot/settings", json={"cooldown_minutes": 4})

        assert response.status_code == 422  # Validation error

    def test_update_bot_settings_validation_max(self, client, mock_auth):
        """Test updating bot settings with value above maximum."""
        response = client.put("/api/bot/settings", json={"cooldown_minutes": 61})

        assert response.status_code == 422  # Validation error

    def test_update_bot_settings_controller_not_configured(self, client, mock_auth):
        """Test updating bot settings when controller not configured."""
        with patch("web.routes.bot._get_controller") as mock_get_controller:
            from fastapi import HTTPException

            mock_get_controller.side_effect = HTTPException(status_code=503)

            response = client.put("/api/bot/settings", json={"cooldown_minutes": 15})

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error"
            assert "not configured" in data["message"]
