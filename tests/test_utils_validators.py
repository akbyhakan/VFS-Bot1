"""Tests for utils.validators module."""

import pytest
from src.utils.validators import (
    validate_email,
    validate_phone,
    mask_sensitive_data,
    validate_centre,
    validate_category,
)


class TestEmailValidation:
    """Test email validation function."""

    def test_valid_emails(self):
        """Test validation accepts valid email formats."""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "user+tag@example.com",
            "user_name@example-domain.com",
            "123@test.com",
            "a@b.co",
        ]
        for email in valid_emails:
            assert validate_email(email), f"Should accept valid email: {email}"

    def test_invalid_emails(self):
        """Test validation rejects invalid email formats."""
        invalid_emails = [
            "not-an-email",
            "@example.com",
            "user@",
            "user@@example.com",
            "user@.com",
            "",
            "user@domain",
            "user.domain.com",
        ]
        for email in invalid_emails:
            assert not validate_email(email), f"Should reject invalid email: {email}"


class TestPhoneValidation:
    """Test phone number validation function."""

    def test_valid_phones(self):
        """Test validation accepts valid phone formats."""
        valid_phones = [
            "+12345678901",
            "+905551234567",
            "905551234567",
            "+1 555 123 4567",
            "+44-20-1234-5678",
            "+90 (555) 123-4567",
        ]
        for phone in valid_phones:
            assert validate_phone(phone), f"Should accept valid phone: {phone}"

    def test_invalid_phones(self):
        """Test validation rejects invalid phone formats."""
        invalid_phones = [
            "123",  # Too short
            "+0123456789",  # Starts with 0 after +
            "abc123456789",  # Contains letters
            "",
            "+",
            "12345678901234567890",  # Too long
        ]
        for phone in invalid_phones:
            assert not validate_phone(phone), f"Should reject invalid phone: {phone}"


class TestSensitiveDataMasking:
    """Test sensitive data masking function."""

    def test_mask_with_default_visible_chars(self):
        """Test masking with default 4 visible characters."""
        assert mask_sensitive_data("password123") == "pass*******"
        assert mask_sensitive_data("secret") == "secr**"

    def test_mask_with_custom_visible_chars(self):
        """Test masking with custom visible character count."""
        assert mask_sensitive_data("password123", visible_chars=8) == "password***"
        assert mask_sensitive_data("test", visible_chars=2) == "te**"

    def test_mask_short_data(self):
        """Test masking data shorter than visible chars."""
        assert mask_sensitive_data("abc", visible_chars=4) == "***"
        assert mask_sensitive_data("ab") == "**"

    def test_mask_empty_data(self):
        """Test masking empty string."""
        assert mask_sensitive_data("") == "***"


class TestCentreValidation:
    """Test centre validation function."""

    def test_valid_centre(self):
        """Test validation accepts centre in allowed list."""
        allowed = ["Istanbul", "Ankara", "Izmir"]
        assert validate_centre("Istanbul", allowed)
        assert validate_centre("Ankara", allowed)

    def test_invalid_centre(self):
        """Test validation rejects centre not in allowed list."""
        allowed = ["Istanbul", "Ankara", "Izmir"]
        assert not validate_centre("Berlin", allowed)
        assert not validate_centre("", allowed)

    def test_centre_with_whitespace(self):
        """Test validation handles whitespace correctly."""
        allowed = ["Istanbul", "Ankara"]
        assert validate_centre("  Istanbul  ", allowed)
        assert validate_centre("Ankara ", allowed)


class TestCategoryValidation:
    """Test category validation function."""

    def test_valid_category(self):
        """Test validation accepts category in allowed list."""
        allowed = ["Schengen Visa", "National Visa", "Tourist Visa"]
        assert validate_category("Schengen Visa", allowed)
        assert validate_category("Tourist Visa", allowed)

    def test_invalid_category(self):
        """Test validation rejects category not in allowed list."""
        allowed = ["Schengen Visa", "National Visa"]
        assert not validate_category("Work Visa", allowed)
        assert not validate_category("", allowed)

    def test_category_with_whitespace(self):
        """Test validation handles whitespace correctly."""
        allowed = ["Schengen Visa", "National Visa"]
        assert validate_category("  Schengen Visa  ", allowed)
        assert validate_category("National Visa ", allowed)
