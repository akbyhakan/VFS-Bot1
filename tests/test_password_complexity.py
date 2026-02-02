"""Tests for password complexity validation in auth module."""

import pytest
from src.core.auth import validate_password_complexity
from src.core.exceptions import ValidationError


class TestPasswordComplexity:
    """Tests for password complexity validation."""

    def test_valid_password(self):
        """Test that a valid password passes validation."""
        # Should not raise any exception
        validate_password_complexity("MyP@ssw0rd123!")

    def test_valid_complex_password(self):
        """Test that a complex valid password passes."""
        validate_password_complexity("Tr0ng!P@ssw0rd2024")

    def test_password_too_short(self):
        """Test that password shorter than 12 characters fails."""
        with pytest.raises(ValidationError) as exc_info:
            validate_password_complexity("Short1!")
        
        assert "at least 12 characters" in str(exc_info.value)

    def test_password_no_uppercase(self):
        """Test that password without uppercase fails."""
        with pytest.raises(ValidationError) as exc_info:
            validate_password_complexity("myp@ssw0rd123")
        
        assert "uppercase letter" in str(exc_info.value)

    def test_password_no_lowercase(self):
        """Test that password without lowercase fails."""
        with pytest.raises(ValidationError) as exc_info:
            validate_password_complexity("MYP@SSW0RD123")
        
        assert "lowercase letter" in str(exc_info.value)

    def test_password_no_digit(self):
        """Test that password without digit fails."""
        with pytest.raises(ValidationError) as exc_info:
            validate_password_complexity("MyP@ssword!!!")
        
        assert "digit" in str(exc_info.value)

    def test_password_no_special_char(self):
        """Test that password without special character fails."""
        with pytest.raises(ValidationError) as exc_info:
            validate_password_complexity("MyPassword123")
        
        assert "special character" in str(exc_info.value)

    def test_password_multiple_violations(self):
        """Test that password with multiple violations reports all."""
        with pytest.raises(ValidationError) as exc_info:
            validate_password_complexity("short")
        
        error_msg = str(exc_info.value)
        assert "12 characters" in error_msg
        assert "uppercase" in error_msg
        assert "digit" in error_msg
        assert "special character" in error_msg

    def test_password_exactly_12_chars_valid(self):
        """Test that password with exactly 12 characters passes if complex."""
        # Should not raise
        validate_password_complexity("MyP@ssw0rd12")

    def test_password_various_special_chars(self):
        """Test that various special characters are accepted."""
        special_chars = "!@#$%^&*(),.?\":{}|<>"
        
        for char in special_chars:
            password = f"MyPassw0rd12{char}"
            # Should not raise for any of these
            validate_password_complexity(password)

    def test_password_unicode_characters(self):
        """Test password with unicode characters."""
        # Unicode characters should still require standard complexity
        with pytest.raises(ValidationError):
            validate_password_complexity("пароль123")  # No uppercase, no special char

    def test_password_spaces_allowed(self):
        """Test that passwords with spaces are allowed if other requirements met."""
        # Spaces are not special chars, so this should fail
        with pytest.raises(ValidationError) as exc_info:
            validate_password_complexity("My Pass Word 123")
        
        assert "special character" in str(exc_info.value)

    def test_password_with_spaces_and_special(self):
        """Test that passwords with both spaces and special chars pass."""
        # Should pass - has all requirements including special char
        validate_password_complexity("My P@ssw0rd 123")
