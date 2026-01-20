"""Tests for masking utility functions."""

import pytest
from src.utils.masking import (
    mask_email,
    mask_phone,
    mask_password,
    mask_sensitive_dict,
    safe_log_user,
)


class TestMaskEmail:
    """Tests for email masking."""

    def test_mask_standard_email(self):
        """Test masking a standard email address."""
        assert mask_email("user@example.com") == "u***@e***.com"

    def test_mask_short_email(self):
        """Test masking a short email address."""
        assert mask_email("a@b.com") == "a***@b***.com"

    def test_mask_long_email(self):
        """Test masking a long email address."""
        assert mask_email("verylongemail@verylongdomain.com") == "v***@v***.com"

    def test_mask_subdomain_email(self):
        """Test masking email with subdomain."""
        assert mask_email("user@mail.example.com") == "u***@m***.example.com"

    def test_mask_invalid_email_no_at(self):
        """Test masking invalid email without @ sign."""
        assert mask_email("notanemail") == "***"

    def test_mask_empty_email(self):
        """Test masking empty email."""
        assert mask_email("") == "***"

    def test_mask_multiple_at_signs(self):
        """Test masking email with multiple @ signs."""
        assert mask_email("user@@example.com") == "***"


class TestMaskPhone:
    """Tests for phone number masking."""

    def test_mask_standard_phone_with_country_code(self):
        """Test masking phone with country code."""
        assert mask_phone("+905551234567") == "+***4567"

    def test_mask_phone_without_country_code(self):
        """Test masking phone without country code."""
        assert mask_phone("5551234567") == "***4567"

    def test_mask_short_phone(self):
        """Test masking short phone number."""
        assert mask_phone("123") == "***"

    def test_mask_empty_phone(self):
        """Test masking empty phone."""
        assert mask_phone("") == "***"

    def test_mask_international_phone(self):
        """Test masking international phone."""
        assert mask_phone("+441234567890") == "+***7890"
        
    def test_mask_single_digit_country_code(self):
        """Test masking phone with single-digit country code (e.g., US +1)."""
        assert mask_phone("+15551234567") == "+***4567"


class TestMaskPassword:
    """Tests for password masking."""

    def test_mask_password_always_returns_stars(self):
        """Test that password is always completely masked."""
        assert mask_password("password123") == "********"
        assert mask_password("") == "********"
        assert mask_password("very_long_password_12345") == "********"
    
    def test_mask_password_never_reveals_characters(self):
        """Password masking should never reveal any characters."""
        test_passwords = [
            "a",
            "ab",
            "abc",
            "password",
            "verylongpassword123!@#",
            "p@$$w0rd",
        ]
        
        for password in test_passwords:
            masked = mask_password(password)
            # Masked password should not contain any original characters
            assert masked == "********", f"Password '{password}' was not properly masked"
            # Password length should not be disclosed
            assert len(masked) == 8, "Masked password length should always be 8"


class TestMaskSensitiveDict:
    """Tests for dictionary masking."""

    def test_mask_password_in_dict(self):
        """Test masking password field in dictionary."""
        data = {"username": "user1", "password": "secret123"}
        masked = mask_sensitive_dict(data)
        assert masked["username"] == "user1"
        assert masked["password"] == "********"

    def test_mask_email_in_dict(self):
        """Test masking email field in dictionary."""
        data = {"name": "John", "email": "john@example.com"}
        masked = mask_sensitive_dict(data)
        assert masked["name"] == "John"
        assert masked["email"] == "j***@e***.com"

    def test_mask_phone_in_dict(self):
        """Test masking phone field in dictionary."""
        data = {"name": "John", "phone": "+905551234567"}
        masked = mask_sensitive_dict(data)
        assert masked["name"] == "John"
        assert masked["phone"] == "+***4567"

    def test_mask_nested_dict(self):
        """Test masking nested dictionaries."""
        data = {
            "user": {
                "email": "user@example.com",
                "password": "secret",
            }
        }
        masked = mask_sensitive_dict(data)
        assert masked["user"]["email"] == "u***@e***.com"
        assert masked["user"]["password"] == "********"

    def test_mask_dict_with_lists(self):
        """Test masking dictionaries in lists."""
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

    def test_mask_sensitive_keys(self):
        """Test masking various sensitive keys."""
        data = {
            "api_key": "secret_key",
            "token": "bearer_token",
            "cvv": "123",
            "card_number": "1234567890123456",
            "normal_field": "visible",
        }
        masked = mask_sensitive_dict(data)
        assert masked["api_key"] == "********"
        assert masked["token"] == "********"
        assert masked["cvv"] == "********"
        assert masked["card_number"] == "********"
        assert masked["normal_field"] == "visible"

    def test_custom_sensitive_keys(self):
        """Test masking with custom sensitive keys."""
        data = {"secret_field": "secret", "normal_field": "visible"}
        masked = mask_sensitive_dict(data, sensitive_keys={"secret_field"})
        assert masked["secret_field"] == "********"
        assert masked["normal_field"] == "visible"

    def test_case_insensitive_matching(self):
        """Test that key matching is case-insensitive."""
        data = {"PASSWORD": "secret", "Email": "user@example.com"}
        masked = mask_sensitive_dict(data)
        assert masked["PASSWORD"] == "********"
        assert masked["Email"] == "u***@e***.com"


class TestSafeLogUser:
    """Tests for safe user logging."""

    def test_safe_log_user_masks_password(self):
        """Test that safe_log_user masks password."""
        user = {
            "id": 1,
            "email": "user@example.com",
            "password": "secret123",
            "centre": "Istanbul",
        }
        safe = safe_log_user(user)
        assert safe["id"] == 1
        assert safe["email"] == "u***@e***.com"
        assert safe["password"] == "********"
        assert safe["centre"] == "Istanbul"

    def test_safe_log_user_with_phone(self):
        """Test safe_log_user with phone number."""
        user = {
            "id": 1,
            "email": "user@example.com",
            "mobile_number": "+905551234567",
        }
        safe = safe_log_user(user)
        assert safe["email"] == "u***@e***.com"
        assert safe["mobile_number"] == "+***4567"

    def test_safe_log_user_preserves_non_sensitive(self):
        """Test that non-sensitive fields are preserved."""
        user = {
            "id": 123,
            "centre": "Istanbul",
            "category": "Tourism",
            "active": True,
        }
        safe = safe_log_user(user)
        assert safe["id"] == 123
        assert safe["centre"] == "Istanbul"
        assert safe["category"] == "Tourism"
        assert safe["active"] is True
