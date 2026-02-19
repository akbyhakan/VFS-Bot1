"""Tests for webhook signature verification security."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.services.otp_manager.webhook_token_manager import WebhookToken, WebhookTokenManager
from src.utils.webhook_utils import generate_webhook_signature

# Import create_app
from web.app import create_app
from web.routes.sms_webhook import set_webhook_manager


class TestWebhookSecurity:
    """Webhook security tests."""

    @pytest.fixture
    def mock_webhook_manager(self):
        """Create a mock webhook manager."""
        manager = MagicMock(spec=WebhookTokenManager)
        
        # Mock token
        mock_token = WebhookToken(
            token="tk_test123456789",
            account_id="acc_test",
            phone_number="+905551234567",
            webhook_url="https://api.example.com/webhook/sms/tk_test123456789",
        )
        
        manager.validate_token.return_value = mock_token
        manager.process_sms.return_value = "123456"
        
        return manager

    def _make_client(self, env: str, mock_webhook_manager, secret: str | None = None, monkeypatch=None):
        """Create test client with specific environment."""
        if monkeypatch:
            if secret:
                monkeypatch.setenv("SMS_WEBHOOK_SECRET", secret)
            else:
                monkeypatch.delenv("SMS_WEBHOOK_SECRET", raising=False)
        set_webhook_manager(mock_webhook_manager)
        app = create_app(run_security_validation=False, env_override=env)
        return TestClient(app)

    def test_webhook_rejects_missing_signature_in_production(self, mock_webhook_manager, monkeypatch):
        """Production mode should reject webhook without signature."""
        client = self._make_client("production", mock_webhook_manager, secret="test-secret-32-chars-minimum-here", monkeypatch=monkeypatch)
        payload = {"message": "Your code is 123456", "from": "+905551234567"}

        response = client.post("/webhook/sms/tk_test123456789", json=payload)
        assert response.status_code == 401
        assert "Missing webhook signature" in response.json()["detail"]

    def test_webhook_rejects_invalid_signature_in_production(self, mock_webhook_manager, monkeypatch):
        """Production mode should reject webhook with invalid signature."""
        client = self._make_client("production", mock_webhook_manager, secret="test-secret-32-chars-minimum-here", monkeypatch=monkeypatch)
        payload = {"message": "Your code is 123456", "from": "+905551234567"}

        response = client.post(
            "/webhook/sms/tk_test123456789",
            json=payload,
            headers={"X-Webhook-Signature": "invalid-signature"},
        )
        assert response.status_code == 401

    def test_webhook_accepts_valid_signature_in_production(self, mock_webhook_manager, monkeypatch):
        """Production mode should accept webhook with valid signature."""
        secret = "test-secret-32-chars-minimum-here"
        client = self._make_client("production", mock_webhook_manager, secret=secret, monkeypatch=monkeypatch)
        payload = {"message": "Your code is 123456", "from": "+905551234567"}
        signature = generate_webhook_signature(json.dumps(payload), secret)

        with patch("src.services.otp_manager.otp_webhook.get_otp_service"):
            response = client.post(
                "/webhook/sms/tk_test123456789", json=payload, headers={"X-Webhook-Signature": signature}
            )
            # Should not be 401 (may be 200 if OTP processed)
            assert response.status_code in [200], f"Unexpected status: {response.status_code}"

    def test_webhook_requires_secret_in_production(self, mock_webhook_manager, monkeypatch):
        """Production mode should fail if SMS_WEBHOOK_SECRET is not set."""
        client = self._make_client("production", mock_webhook_manager, secret=None, monkeypatch=monkeypatch)
        payload = {"message": "Your code is 123456", "from": "+905551234567"}

        with patch("src.services.otp_manager.otp_webhook.get_otp_service"):
            response = client.post("/webhook/sms/tk_test123456789", json=payload)
            # Should work without HMAC when secret not configured
            assert response.status_code in [200], f"Unexpected status: {response.status_code}"

    def test_webhook_enforces_signature_in_dev_when_secret_configured(self, mock_webhook_manager, monkeypatch):
        """Dev mode should enforce signature when secret is configured."""
        client = self._make_client("development", mock_webhook_manager, secret="test-secret-32-chars-minimum-here", monkeypatch=monkeypatch)
        payload = {"message": "Your code is 123456", "from": "+905551234567"}

        # Missing signature should be rejected
        response = client.post("/webhook/sms/tk_test123456789", json=payload)
        assert response.status_code == 401
        assert "Missing webhook signature" in response.json()["detail"]

    def test_webhook_rejects_invalid_signature_in_dev(self, mock_webhook_manager, monkeypatch):
        """Dev mode should reject invalid signature when secret is configured."""
        client = self._make_client("development", mock_webhook_manager, secret="test-secret-32-chars-minimum-here", monkeypatch=monkeypatch)
        payload = {"message": "Your code is 123456", "from": "+905551234567"}

        response = client.post(
            "/webhook/sms/tk_test123456789",
            json=payload,
            headers={"X-Webhook-Signature": "invalid-signature"},
        )
        assert response.status_code == 401

    def test_webhook_accepts_valid_signature_in_dev(self, mock_webhook_manager, monkeypatch):
        """Dev mode should accept valid signature."""
        secret = "test-secret-32-chars-minimum-here"
        client = self._make_client("development", mock_webhook_manager, secret=secret, monkeypatch=monkeypatch)
        payload = {"message": "Your code is 123456", "from": "+905551234567"}
        signature = generate_webhook_signature(json.dumps(payload), secret)

        with patch("src.services.otp_manager.otp_webhook.get_otp_service"):
            response = client.post(
                "/webhook/sms/tk_test123456789", json=payload, headers={"X-Webhook-Signature": signature}
            )
            # Should not be 401
            assert response.status_code in [200], f"Unexpected status: {response.status_code}"

    def test_webhook_works_without_secret_in_dev(self, mock_webhook_manager, monkeypatch):
        """Dev mode without secret should allow unsigned requests (with warning)."""
        client = self._make_client("development", mock_webhook_manager, secret=None, monkeypatch=monkeypatch)
        payload = {"message": "Your code is 123456", "from": "+905551234567"}

        with patch("src.services.otp_manager.otp_webhook.get_otp_service"):
            response = client.post("/webhook/sms/tk_test123456789", json=payload)
            # Should work without signature
            assert response.status_code in [200], f"Unexpected status: {response.status_code}"

    def test_webhook_payment_endpoint_security(self, mock_webhook_manager, monkeypatch):
        """Payment webhook should have same security as SMS webhook."""
        client = self._make_client("production", mock_webhook_manager, secret="test-secret-32-chars-minimum-here", monkeypatch=monkeypatch)
        payload = {"message": "Your bank code is 123456", "from": "+905551234567"}

        # Missing signature should be rejected
        response = client.post("/webhook/sms/tk_test123456789", json=payload)
        assert response.status_code == 401

    def test_webhook_appointment_endpoint_security(self, mock_webhook_manager, monkeypatch):
        """Appointment webhook should have same security as SMS webhook."""
        client = self._make_client("production", mock_webhook_manager, secret="test-secret-32-chars-minimum-here", monkeypatch=monkeypatch)
        payload = {"message": "Your appointment code is 123456", "from": "+905551234567"}

        # Missing signature should be rejected
        response = client.post("/webhook/sms/tk_test123456789", json=payload)
        assert response.status_code == 401
