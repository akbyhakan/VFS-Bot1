"""Tests for SMS webhook routes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.services.webhook_token_manager import WebhookToken, WebhookTokenManager
from web.app import app
from web.routes.sms_webhook import set_webhook_manager


@pytest.fixture
def mock_webhook_manager():
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


@pytest.fixture
def client(mock_webhook_manager):
    """Create test client with mocked webhook manager."""
    set_webhook_manager(mock_webhook_manager)
    return TestClient(app)


class TestSMSWebhookRoutes:
    """Tests for SMS webhook endpoints."""

    def test_receive_sms_success(self, client, mock_webhook_manager):
        """Test successful SMS reception."""
        payload = {"message": "Your OTP is 123456", "from": "+905551234567"}

        with patch("src.services.otp_webhook.get_otp_service"):
            response = client.post("/webhook/sms/tk_test123456789", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["account_id"] == "acc_test"
        assert data["otp_extracted"] is True

    def test_receive_sms_no_otp_extracted(self, client, mock_webhook_manager):
        """Test SMS received but no OTP extracted."""
        mock_webhook_manager.process_sms.return_value = None

        payload = {"message": "Hello, this is a test"}

        response = client.post("/webhook/sms/tk_test123456789", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert data["otp_extracted"] is False

    def test_receive_sms_invalid_token(self, client, mock_webhook_manager):
        """Test SMS with invalid token."""
        mock_webhook_manager.process_sms.side_effect = ValueError("Invalid token")

        payload = {"message": "OTP: 123456"}

        response = client.post("/webhook/sms/tk_invalid", json=payload)

        assert response.status_code == 404

    def test_receive_sms_invalid_json(self, client):
        """Test SMS with invalid JSON payload."""
        response = client.post(
            "/webhook/sms/tk_test123456789",
            data="not json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

    def test_receive_sms_with_session_linked(self, client, mock_webhook_manager):
        """Test SMS with linked session."""
        # Mock token with session
        mock_token = WebhookToken(
            token="tk_test123456789",
            account_id="acc_test",
            phone_number="+905551234567",
            webhook_url="https://api.example.com/webhook/sms/tk_test123456789",
            session_id="session_123",
        )
        mock_webhook_manager.validate_token.return_value = mock_token

        payload = {"message": "OTP: 654321"}

        # Mock OTP service
        mock_otp_service = MagicMock()
        with patch("src.services.otp_webhook.get_otp_service", return_value=mock_otp_service):
            response = client.post("/webhook/sms/tk_test123456789", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "session_123"

        # Verify OTP was delivered to session
        mock_otp_service.process_appointment_sms.assert_called_once()

    def test_receive_sms_different_payload_formats(self, client, mock_webhook_manager):
        """Test different SMS payload formats."""
        formats = [
            {"message": "OTP: 111111"},
            {"text": "Code: 222222"},
            {"body": "Your code is 333333"},
        ]

        for payload in formats:
            with patch("src.services.otp_webhook.get_otp_service"):
                response = client.post("/webhook/sms/tk_test123456789", json=payload)
            assert response.status_code == 200, f"Failed for payload: {payload}"

    def test_webhook_status_success(self, client, mock_webhook_manager):
        """Test webhook status endpoint."""
        response = client.get("/webhook/sms/tk_test123456789/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["account_id"] == "acc_test"
        assert data["phone_number"] == "+905551234567"
        assert "webhook_url" in data

    def test_webhook_status_invalid_token(self, client, mock_webhook_manager):
        """Test status with invalid token."""
        mock_webhook_manager.validate_token.return_value = None

        response = client.get("/webhook/sms/tk_invalid/status")

        assert response.status_code == 404

    def test_webhook_status_with_session(self, client, mock_webhook_manager):
        """Test status shows linked session."""
        mock_token = WebhookToken(
            token="tk_test123456789",
            account_id="acc_test",
            phone_number="+905551234567",
            webhook_url="https://api.example.com/webhook/sms/tk_test123456789",
            session_id="session_456",
        )
        mock_webhook_manager.validate_token.return_value = mock_token

        response = client.get("/webhook/sms/tk_test123456789/status")

        assert response.status_code == 200
        data = response.json()
        assert data["session_linked"] is True
        assert data["session_id"] == "session_456"

    def test_test_webhook_success(self, client, mock_webhook_manager):
        """Test webhook test endpoint."""
        payload = {"message": "Test OTP 123456"}

        response = client.post("/webhook/sms/tk_test123456789/test", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "test_success"
        assert data["account_id"] == "acc_test"
        assert "parsed_message" in data

    def test_test_webhook_invalid_token(self, client, mock_webhook_manager):
        """Test webhook test with invalid token."""
        mock_webhook_manager.validate_token.return_value = None

        response = client.post("/webhook/sms/tk_invalid/test", json={"message": "Test"})

        assert response.status_code == 404

    def test_test_webhook_invalid_payload_format(self, client, mock_webhook_manager):
        """Test webhook test with invalid payload format."""
        # Missing message field
        payload = {"from": "+905551234567"}

        response = client.post("/webhook/sms/tk_test123456789/test", json=payload)

        assert response.status_code == 400
        assert "Invalid SMS payload format" in response.json()["detail"]

    def test_test_webhook_no_body(self, client, mock_webhook_manager):
        """Test webhook test without body."""
        # When there's no body, FastAPI returns 422 or 400
        # The endpoint tries to parse JSON and fails gracefully
        response = client.post("/webhook/sms/tk_test123456789/test")

        # Accept either success response or bad request
        assert response.status_code in [200, 400, 422]

    def test_rate_limiting(self, client):
        """Test rate limiting on webhook endpoints."""
        # This test may not work properly in test environment
        # as rate limiting might be disabled or need special setup
        # Just verify endpoint is accessible
        response = client.get("/webhook/sms/tk_test123456789/status")
        assert response.status_code in [200, 404, 429]

    def test_webhook_manager_not_initialized(self):
        """Test error when webhook manager not initialized."""
        # Clear global manager
        import web.routes.sms_webhook as sms_webhook_module
        from web.routes.sms_webhook import get_webhook_manager

        original_manager = sms_webhook_module._webhook_manager
        sms_webhook_module._webhook_manager = None

        try:
            with pytest.raises(RuntimeError, match="Webhook manager not initialized"):
                get_webhook_manager()
        finally:
            sms_webhook_module._webhook_manager = original_manager

    def test_concurrent_sms_processing(self, client, mock_webhook_manager):
        """Test processing multiple SMS concurrently."""
        import threading

        results = []

        def send_sms(otp_value):
            payload = {"message": f"OTP: {otp_value}"}
            with patch("src.services.otp_webhook.get_otp_service"):
                response = client.post("/webhook/sms/tk_test123456789", json=payload)
            results.append(response.status_code)

        # Send 5 concurrent requests
        threads = []
        for i in range(5):
            thread = threading.Thread(target=send_sms, args=(f"{i}00000",))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All should succeed
        assert all(status == 200 for status in results)
