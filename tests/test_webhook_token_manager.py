"""Tests for WebhookTokenManager."""

import pytest
from datetime import datetime, timezone

from src.services.webhook_token_manager import (
    WebhookTokenManager,
    WebhookToken,
    SMSPayload,
    SMSPayloadParser
)


class TestSMSPayloadParser:
    """Tests for SMS payload parsing."""
    
    def test_parse_standard_format(self):
        """Test parsing standard SMS Forwarder format."""
        payload = {
            "message": "Your OTP is 123456",
            "from": "+905551234567",
            "timestamp": "2026-01-29T15:00:00Z"
        }
        
        result = SMSPayloadParser.parse(payload)
        
        assert isinstance(result, SMSPayload)
        assert result.message == "Your OTP is 123456"
        assert result.phone_number == "+905551234567"
        assert result.timestamp == "2026-01-29T15:00:00Z"
        assert result.raw_payload == payload
    
    def test_parse_alternative_format(self):
        """Test parsing alternative field names."""
        payload = {
            "text": "Code: 654321",
            "phone": "+905559876543"
        }
        
        result = SMSPayloadParser.parse(payload)
        
        assert result.message == "Code: 654321"
        assert result.phone_number == "+905559876543"
    
    def test_parse_minimal_format(self):
        """Test parsing minimal payload with just body."""
        payload = {"body": "OTP 111222"}
        
        result = SMSPayloadParser.parse(payload)
        
        assert result.message == "OTP 111222"
        assert result.phone_number is None
    
    def test_parse_with_sim_slot(self):
        """Test parsing payload with SIM slot information."""
        payload = {
            "message": "Test OTP",
            "sim_slot": 1
        }
        
        result = SMSPayloadParser.parse(payload)
        
        assert result.message == "Test OTP"
        assert result.sim_slot == 1
    
    def test_parse_no_message_raises_error(self):
        """Test that missing message raises ValueError."""
        payload = {"from": "+905551234567"}
        
        with pytest.raises(ValueError, match="No message content found"):
            SMSPayloadParser.parse(payload)
    
    def test_parse_empty_payload_raises_error(self):
        """Test that empty payload raises ValueError."""
        with pytest.raises(ValueError):
            SMSPayloadParser.parse({})


class TestWebhookTokenManager:
    """Tests for WebhookTokenManager."""
    
    def test_initialization(self):
        """Test manager initialization."""
        manager = WebhookTokenManager(base_url="https://api.example.com")
        
        assert manager.base_url == "https://api.example.com"
        assert len(manager._tokens) == 0
    
    def test_generate_token(self):
        """Test token generation."""
        manager = WebhookTokenManager()
        
        token = manager.generate_token("test_account")
        
        assert token.startswith("tk_")
        assert len(token) == 3 + 24  # "tk_" + 24 hex chars
    
    def test_generate_unique_tokens(self):
        """Test that generated tokens are unique."""
        manager = WebhookTokenManager()
        
        tokens = [manager.generate_token(f"account_{i}") for i in range(100)]
        
        assert len(tokens) == len(set(tokens))  # All unique
    
    def test_register_token(self):
        """Test token registration."""
        manager = WebhookTokenManager()
        
        token = manager.generate_token("test_account")
        webhook_token = manager.register_token(
            token=token,
            account_id="test_account",
            phone_number="+905551234567"
        )
        
        assert webhook_token.token == token
        assert webhook_token.account_id == "test_account"
        assert webhook_token.phone_number == "+905551234567"
        assert webhook_token.is_active is True
        assert webhook_token.webhook_url.endswith(f"/webhook/sms/{token}")
    
    def test_register_duplicate_token_raises_error(self):
        """Test that registering duplicate token raises error."""
        manager = WebhookTokenManager()
        
        token = manager.generate_token("account1")
        manager.register_token(token, "account1", "+905551234567")
        
        with pytest.raises(ValueError, match="Token already exists"):
            manager.register_token(token, "account2", "+905559876543")
    
    def test_validate_token(self):
        """Test token validation."""
        manager = WebhookTokenManager()
        
        token = manager.generate_token("test_account")
        manager.register_token(token, "test_account", "+905551234567")
        
        result = manager.validate_token(token)
        
        assert result is not None
        assert result.token == token
        assert result.is_active is True
    
    def test_validate_invalid_token(self):
        """Test validation of non-existent token."""
        manager = WebhookTokenManager()
        
        result = manager.validate_token("tk_nonexistent")
        
        assert result is None
    
    def test_validate_inactive_token(self):
        """Test validation of inactive token."""
        manager = WebhookTokenManager()
        
        token = manager.generate_token("test_account")
        webhook_token = manager.register_token(token, "test_account", "+905551234567")
        webhook_token.is_active = False
        
        result = manager.validate_token(token)
        
        assert result is None
    
    def test_link_session(self):
        """Test linking token to session."""
        manager = WebhookTokenManager()
        
        token = manager.generate_token("test_account")
        manager.register_token(token, "test_account", "+905551234567")
        
        manager.link_session(token, "session_123")
        
        webhook_token = manager.validate_token(token)
        assert webhook_token.session_id == "session_123"
    
    def test_link_session_invalid_token_raises_error(self):
        """Test linking invalid token raises error."""
        manager = WebhookTokenManager()
        
        with pytest.raises(ValueError, match="Invalid token"):
            manager.link_session("tk_invalid", "session_123")
    
    def test_unlink_session(self):
        """Test unlinking session from token."""
        manager = WebhookTokenManager()
        
        token = manager.generate_token("test_account")
        manager.register_token(token, "test_account", "+905551234567")
        manager.link_session(token, "session_123")
        
        manager.unlink_session(token)
        
        webhook_token = manager.validate_token(token)
        assert webhook_token.session_id is None
    
    def test_process_sms(self):
        """Test SMS processing and OTP extraction."""
        manager = WebhookTokenManager()
        
        token = manager.generate_token("test_account")
        manager.register_token(token, "test_account", "+905551234567")
        
        payload = {"message": "Your OTP is 123456"}
        otp = manager.process_sms(token, payload)
        
        assert otp == "123456"
    
    def test_process_sms_updates_last_used(self):
        """Test that processing SMS updates last_used_at."""
        manager = WebhookTokenManager()
        
        token = manager.generate_token("test_account")
        webhook_token = manager.register_token(token, "test_account", "+905551234567")
        
        assert webhook_token.last_used_at is None
        
        payload = {"message": "Code: 999888"}
        manager.process_sms(token, payload)
        
        assert webhook_token.last_used_at is not None
    
    def test_process_sms_various_otp_formats(self):
        """Test OTP extraction from various message formats."""
        manager = WebhookTokenManager()
        
        token = manager.generate_token("test_account")
        manager.register_token(token, "test_account", "+905551234567")
        
        test_cases = [
            ("Your OTP is 123456", "123456"),
            ("OTP: 654321", "654321"),
            ("Code is 111222", "111222"),
            ("Verification code: 333444", "333444"),
            ("Your passcode is 9876", "9876"),
        ]
        
        for message, expected_otp in test_cases:
            payload = {"message": message}
            otp = manager.process_sms(token, payload)
            assert otp == expected_otp, f"Failed for message: {message}"
    
    def test_process_sms_no_otp_found(self):
        """Test processing SMS without OTP."""
        manager = WebhookTokenManager()
        
        token = manager.generate_token("test_account")
        manager.register_token(token, "test_account", "+905551234567")
        
        payload = {"message": "Hello, this is a test message"}
        otp = manager.process_sms(token, payload)
        
        assert otp is None
    
    def test_process_sms_invalid_token_raises_error(self):
        """Test processing SMS with invalid token."""
        manager = WebhookTokenManager()
        
        payload = {"message": "OTP: 123456"}
        
        with pytest.raises(ValueError, match="Invalid token"):
            manager.process_sms("tk_invalid", payload)
    
    def test_revoke_token(self):
        """Test token revocation."""
        manager = WebhookTokenManager()
        
        token = manager.generate_token("test_account")
        manager.register_token(token, "test_account", "+905551234567")
        
        manager.revoke_token(token)
        
        # Token should still exist but be inactive
        webhook_token = manager._tokens[token]
        assert webhook_token.is_active is False
        
        # Validation should fail
        assert manager.validate_token(token) is None
    
    def test_list_tokens(self):
        """Test listing all tokens."""
        manager = WebhookTokenManager()
        
        for i in range(3):
            token = manager.generate_token(f"account_{i}")
            manager.register_token(token, f"account_{i}", f"+90555123456{i}")
        
        tokens = manager.list_tokens()
        
        assert len(tokens) == 3
        assert all(isinstance(t, WebhookToken) for t in tokens)
    
    def test_list_tokens_filtered_by_account(self):
        """Test listing tokens filtered by account ID."""
        manager = WebhookTokenManager()
        
        token1 = manager.generate_token("account_1")
        manager.register_token(token1, "account_1", "+905551234561")
        
        token2 = manager.generate_token("account_2")
        manager.register_token(token2, "account_2", "+905551234562")
        
        tokens = manager.list_tokens(account_id="account_1")
        
        assert len(tokens) == 1
        assert tokens[0].account_id == "account_1"
    
    def test_get_token_by_account(self):
        """Test getting token by account ID."""
        manager = WebhookTokenManager()
        
        token = manager.generate_token("test_account")
        manager.register_token(token, "test_account", "+905551234567")
        
        result = manager.get_token_by_account("test_account")
        
        assert result is not None
        assert result.token == token
    
    def test_get_token_by_phone(self):
        """Test getting token by phone number."""
        manager = WebhookTokenManager()
        
        token = manager.generate_token("test_account")
        manager.register_token(token, "test_account", "+905551234567")
        
        result = manager.get_token_by_phone("+905551234567")
        
        assert result is not None
        assert result.token == token
    
    def test_get_webhook_url(self):
        """Test getting webhook URL."""
        manager = WebhookTokenManager(base_url="https://api.example.com")
        
        token = manager.generate_token("test_account")
        manager.register_token(token, "test_account", "+905551234567")
        
        url = manager.get_webhook_url(token)
        
        assert url == f"https://api.example.com/webhook/sms/{token}"
    
    def test_get_webhook_url_invalid_token_raises_error(self):
        """Test getting webhook URL with invalid token."""
        manager = WebhookTokenManager()
        
        with pytest.raises(ValueError, match="Invalid token"):
            manager.get_webhook_url("tk_invalid")
