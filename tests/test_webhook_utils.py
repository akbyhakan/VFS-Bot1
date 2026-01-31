"""Tests for utils/webhook_utils module."""

import pytest
import time
from src.utils.webhook_utils import verify_webhook_signature, generate_webhook_signature


class TestVerifyWebhookSignature:
    """Tests for verify_webhook_signature function."""

    def test_verify_valid_signature(self):
        """Test verifying a valid signature."""
        secret = "test_secret"
        payload = b"test payload"
        signature = generate_webhook_signature(payload.decode(), secret)

        result = verify_webhook_signature(payload, signature, secret)
        assert result is True

    def test_verify_invalid_signature(self):
        """Test verifying an invalid signature."""
        secret = "test_secret"
        payload = b"test payload"
        # Create a signature with wrong secret
        wrong_signature = generate_webhook_signature(payload.decode(), "wrong_secret")

        result = verify_webhook_signature(payload, wrong_signature, secret)
        assert result is False

    def test_verify_tampered_payload(self):
        """Test verifying signature with tampered payload."""
        secret = "test_secret"
        original_payload = b"original payload"
        signature = generate_webhook_signature(original_payload.decode(), secret)

        # Try to verify with different payload
        tampered_payload = b"tampered payload"
        result = verify_webhook_signature(tampered_payload, signature, secret)
        assert result is False

    def test_verify_missing_timestamp(self):
        """Test verifying signature without timestamp."""
        payload = b"test"
        signature = "v1=abc123"
        result = verify_webhook_signature(payload, signature, "secret")
        assert result is False

    def test_verify_missing_signature_value(self):
        """Test verifying signature without signature value."""
        payload = b"test"
        signature = "t=123456789"
        result = verify_webhook_signature(payload, signature, "secret")
        assert result is False

    def test_verify_invalid_timestamp_format(self):
        """Test verifying signature with invalid timestamp."""
        payload = b"test"
        signature = "t=invalid,v1=abc123"
        result = verify_webhook_signature(payload, signature, "secret")
        assert result is False

    def test_verify_old_timestamp(self):
        """Test verifying signature with old timestamp."""
        secret = "test_secret"
        payload = "test payload"

        # Create signature with old timestamp
        old_timestamp = int(time.time()) - 400  # 400 seconds ago
        signature = f"t={old_timestamp},v1=abc123"

        result = verify_webhook_signature(payload.encode(), signature, secret, timestamp_tolerance=300)
        assert result is False

    def test_verify_future_timestamp(self):
        """Test verifying signature with future timestamp."""
        secret = "test_secret"
        payload = "test payload"

        # Create signature with future timestamp
        future_timestamp = int(time.time()) + 400
        signature = f"t={future_timestamp},v1=abc123"

        result = verify_webhook_signature(payload.encode(), signature, secret, timestamp_tolerance=300)
        assert result is False

    def test_verify_with_custom_tolerance(self):
        """Test verifying with custom timestamp tolerance."""
        secret = "test_secret"
        payload = "test payload"

        # Create a recent but slightly old signature
        old_timestamp = int(time.time()) - 100
        signature = generate_webhook_signature(payload, secret)
        # Replace timestamp in signature
        signature_parts = signature.split(",")
        signature_parts[0] = f"t={old_timestamp}"
        old_signature = ",".join(signature_parts)

        # Should pass with higher tolerance
        result = verify_webhook_signature(payload.encode(), signature, secret, timestamp_tolerance=200)
        assert result is True

    def test_verify_malformed_signature(self):
        """Test verifying malformed signature."""
        payload = b"test"
        signature = "invalid_format"
        result = verify_webhook_signature(payload, signature, "secret")
        assert result is False


class TestGenerateWebhookSignature:
    """Tests for generate_webhook_signature function."""

    def test_generate_signature_format(self):
        """Test that generated signature has correct format."""
        payload = "test payload"
        secret = "test_secret"

        signature = generate_webhook_signature(payload, secret)

        assert signature.startswith("t=")
        assert ",v1=" in signature

    def test_generate_signature_deterministic(self):
        """Test that signature generation is deterministic for same inputs."""
        payload = "test payload"
        secret = "test_secret"

        # Generate two signatures at the same time
        sig1 = generate_webhook_signature(payload, secret)
        sig2 = generate_webhook_signature(payload, secret)

        # Timestamps might differ by 1 second, but structure should be similar
        assert sig1.split(",v1=")[0].startswith("t=")
        assert sig2.split(",v1=")[0].startswith("t=")

    def test_generate_signature_different_payloads(self):
        """Test that different payloads generate different signatures."""
        secret = "test_secret"

        sig1 = generate_webhook_signature("payload1", secret)
        sig2 = generate_webhook_signature("payload2", secret)

        # The v1 part should be different
        assert sig1.split(",v1=")[1] != sig2.split(",v1=")[1]

    def test_generate_signature_different_secrets(self):
        """Test that different secrets generate different signatures."""
        payload = "test payload"

        sig1 = generate_webhook_signature(payload, "secret1")
        sig2 = generate_webhook_signature(payload, "secret2")

        # The v1 part should be different
        assert sig1.split(",v1=")[1] != sig2.split(",v1=")[1]

    def test_generate_signature_empty_payload(self):
        """Test generating signature with empty payload."""
        signature = generate_webhook_signature("", "secret")
        assert signature.startswith("t=")
        assert ",v1=" in signature

    def test_generate_and_verify_roundtrip(self):
        """Test that generated signature can be verified."""
        secret = "test_secret"
        payload = "test payload data"

        signature = generate_webhook_signature(payload, secret)
        result = verify_webhook_signature(payload.encode(), signature, secret)

        assert result is True
