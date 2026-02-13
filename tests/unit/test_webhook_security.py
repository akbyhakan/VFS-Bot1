"""Tests for webhook signature verification security."""

import json
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.utils.webhook_utils import generate_webhook_signature

# Import create_app
from web.app import create_app


class TestWebhookSecurity:
    """Webhook security tests."""

    def setup_method(self):
        """Setup test client."""
        app = create_app(run_security_validation=False, env_override="testing")
        self.client = TestClient(app)

    def test_webhook_rejects_missing_signature_in_production(self):
        """Production mode should reject webhook without signature."""
        payload = {"from": "+905551234567", "text": "Your code is 123456"}

        with patch.dict(
            os.environ,
            {"ENV": "production", "SMS_WEBHOOK_SECRET": "test-secret-32-chars-minimum-here"},
        ):
            response = self.client.post("/api/webhook/sms", json=payload)
            assert response.status_code == 401
            assert "X-Webhook-Signature" in response.json()["detail"]

    def test_webhook_rejects_invalid_signature_in_production(self):
        """Production mode should reject webhook with invalid signature."""
        payload = {"from": "+905551234567", "text": "Your code is 123456"}

        with patch.dict(
            os.environ,
            {"ENV": "production", "SMS_WEBHOOK_SECRET": "test-secret-32-chars-minimum-here"},
        ):
            response = self.client.post(
                "/api/webhook/sms",
                json=payload,
                headers={"X-Webhook-Signature": "invalid-signature"},
            )
            assert response.status_code == 401

    def test_webhook_accepts_valid_signature_in_production(self):
        """Production mode should accept webhook with valid signature."""
        payload = {"from": "+905551234567", "text": "Your code is 123456"}
        secret = "test-secret-32-chars-minimum-here"
        signature = generate_webhook_signature(json.dumps(payload), secret)

        with patch.dict(os.environ, {"ENV": "production", "SMS_WEBHOOK_SECRET": secret}):
            response = self.client.post(
                "/api/webhook/sms", json=payload, headers={"X-Webhook-Signature": signature}
            )
            # Should not be 401 (may be 422 if no OTP found, or 200 if OTP processed)
            assert response.status_code in [200, 422], f"Unexpected status: {response.status_code}"

    def test_webhook_requires_secret_in_production(self):
        """Production mode should fail if SMS_WEBHOOK_SECRET is not set."""
        payload = {"from": "+905551234567", "text": "Your code is 123456"}

        with patch.dict(os.environ, {"ENV": "production"}, clear=False):
            # Remove SMS_WEBHOOK_SECRET if it exists
            if "SMS_WEBHOOK_SECRET" in os.environ:
                del os.environ["SMS_WEBHOOK_SECRET"]

            response = self.client.post("/api/webhook/sms", json=payload)
            assert response.status_code == 500
            assert "SMS_WEBHOOK_SECRET must be configured" in response.json()["detail"]

    def test_webhook_enforces_signature_in_dev_when_secret_configured(self):
        """Dev mode should enforce signature when secret is configured."""
        payload = {"from": "+905551234567", "text": "Your code is 123456"}

        with patch.dict(
            os.environ,
            {"ENV": "development", "SMS_WEBHOOK_SECRET": "test-secret-32-chars-minimum-here"},
        ):
            # Missing signature should be rejected
            response = self.client.post("/api/webhook/sms", json=payload)
            assert response.status_code == 401
            assert "X-Webhook-Signature" in response.json()["detail"]

    def test_webhook_rejects_invalid_signature_in_dev(self):
        """Dev mode should reject invalid signature when secret is configured."""
        payload = {"from": "+905551234567", "text": "Your code is 123456"}

        with patch.dict(
            os.environ,
            {"ENV": "development", "SMS_WEBHOOK_SECRET": "test-secret-32-chars-minimum-here"},
        ):
            response = self.client.post(
                "/api/webhook/sms",
                json=payload,
                headers={"X-Webhook-Signature": "invalid-signature"},
            )
            assert response.status_code == 401

    def test_webhook_accepts_valid_signature_in_dev(self):
        """Dev mode should accept valid signature."""
        payload = {"from": "+905551234567", "text": "Your code is 123456"}
        secret = "test-secret-32-chars-minimum-here"
        signature = generate_webhook_signature(json.dumps(payload), secret)

        with patch.dict(os.environ, {"ENV": "development", "SMS_WEBHOOK_SECRET": secret}):
            response = self.client.post(
                "/api/webhook/sms", json=payload, headers={"X-Webhook-Signature": signature}
            )
            # Should not be 401
            assert response.status_code in [200, 422], f"Unexpected status: {response.status_code}"

    def test_webhook_works_without_secret_in_dev(self):
        """Dev mode without secret should allow unsigned requests (with warning)."""
        payload = {"from": "+905551234567", "text": "Your code is 123456"}

        with patch.dict(os.environ, {"ENV": "development"}, clear=False):
            # Remove SMS_WEBHOOK_SECRET if it exists
            if "SMS_WEBHOOK_SECRET" in os.environ:
                del os.environ["SMS_WEBHOOK_SECRET"]

            response = self.client.post("/api/webhook/sms", json=payload)
            # Should work without signature (may return 422 if no OTP found)
            assert response.status_code in [200, 422], f"Unexpected status: {response.status_code}"

    def test_webhook_payment_endpoint_security(self):
        """Payment webhook should have same security as SMS webhook."""
        payload = {"from": "+905551234567", "text": "Your bank code is 123456"}

        with patch.dict(
            os.environ,
            {"ENV": "production", "SMS_WEBHOOK_SECRET": "test-secret-32-chars-minimum-here"},
        ):
            # Missing signature should be rejected
            response = self.client.post("/api/webhook/sms/payment", json=payload)
            assert response.status_code == 401

    def test_webhook_appointment_endpoint_security(self):
        """Appointment webhook should have same security as SMS webhook."""
        payload = {"from": "+905551234567", "text": "Your appointment code is 123456"}

        with patch.dict(
            os.environ,
            {"ENV": "production", "SMS_WEBHOOK_SECRET": "test-secret-32-chars-minimum-here"},
        ):
            # Missing signature should be rejected
            response = self.client.post("/api/webhook/sms/appointment", json=payload)
            assert response.status_code == 401
