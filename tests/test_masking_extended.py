"""Tests for masking utilities."""

import pytest
from src.utils.masking import (
    mask_email,
    mask_phone,
    mask_password,
    mask_card_number,
    mask_otp,
    mask_expiry_date,
    mask_cvv,
    mask_sensitive_dict,
)


def test_mask_email():
    """Test email masking."""
    assert mask_email("user@example.com") == "u***@e***.com"
    assert mask_email("john.doe@company.org") == "j***@c***.org"
    assert mask_email("") == "***"
    assert mask_email("invalid") == "***"


def test_mask_phone():
    """Test phone number masking."""
    assert mask_phone("+905551234567") == "+***4567"
    assert mask_phone("5551234567") == "***4567"
    assert mask_phone("123") == "***"


def test_mask_password():
    """Test password masking."""
    assert mask_password("secret123") == "********"
    assert mask_password("") == "********"
    assert mask_password("verylongpasswordhere") == "********"


def test_mask_card_number():
    """Test credit card number masking."""
    assert mask_card_number("1234567890123456") == "************3456"
    assert mask_card_number("4111111111111111") == "************1111"
    assert mask_card_number("123") == "****"
    assert mask_card_number("") == "****"


def test_mask_otp():
    """Test OTP masking."""
    assert mask_otp("123456") == "******"
    assert mask_otp("0000") == "****"
    assert mask_otp("") == "****"


def test_mask_expiry_date():
    """Test credit card expiry date masking."""
    # 4-digit year
    assert mask_expiry_date("12", "2025") == "**/****"
    
    # 2-digit year
    assert mask_expiry_date("06", "25") == "**/**"
    
    # Edge cases
    assert mask_expiry_date("01", "2030") == "**/****"


def test_mask_cvv():
    """Test CVV masking."""
    assert mask_cvv("123") == "***"
    assert mask_cvv("4567") == "***"
    assert mask_cvv("") == "***"


def test_mask_sensitive_dict():
    """Test masking sensitive values in dictionaries."""
    data = {
        "email": "user@example.com",
        "password": "secret123",
        "card_number": "1234567890123456",
        "cvv": "123",
        "otp_code": "456789",
        "phone": "+905551234567",
        "name": "John Doe",  # Should not be masked
    }
    
    masked = mask_sensitive_dict(data)
    
    assert masked["email"] == "u***@e***.com"
    assert masked["password"] == "********"
    assert masked["card_number"] == "********"
    assert masked["cvv"] == "********"
    assert masked["otp_code"] == "********"
    assert masked["phone"] == "+***4567"
    assert masked["name"] == "John Doe"


def test_mask_sensitive_dict_nested():
    """Test masking nested dictionaries."""
    data = {
        "user": {
            "email": "user@example.com",
            "password": "secret",
        },
        "payment": {
            "card_number": "1234567890123456",
            "cvv": "123",
        },
    }
    
    masked = mask_sensitive_dict(data)
    
    assert masked["user"]["email"] == "u***@e***.com"
    assert masked["user"]["password"] == "********"
    assert masked["payment"]["card_number"] == "********"
    assert masked["payment"]["cvv"] == "********"


def test_mask_sensitive_dict_with_lists():
    """Test masking dictionaries containing lists."""
    data = {
        "users": [
            {"email": "user1@example.com", "password": "pass1"},
            {"email": "user2@example.com", "password": "pass2"},
        ]
    }
    
    masked = mask_sensitive_dict(data)
    
    assert masked["users"][0]["email"] == "u***@e***.com"
    assert masked["users"][0]["password"] == "********"
    assert masked["users"][1]["email"] == "u***@e***.com"
    assert masked["users"][1]["password"] == "********"


def test_mask_sensitive_dict_custom_keys():
    """Test masking with custom sensitive keys."""
    data = {
        "api_key": "secret-api-key-123",
        "token": "bearer-token-xyz",
        "normal_field": "visible",
    }
    
    masked = mask_sensitive_dict(data, sensitive_keys={"api_key", "token"})
    
    assert masked["api_key"] == "********"
    assert masked["token"] == "********"
    assert masked["normal_field"] == "visible"
