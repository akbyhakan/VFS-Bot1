"""Tests for log sanitizer utilities."""

import pytest

from src.utils.log_sanitizer import sanitize_log_value


def test_sanitize_normal_value():
    """Test that normal strings are not modified."""
    normal_text = "This is a normal log message"
    result = sanitize_log_value(normal_text)
    assert result == normal_text


def test_sanitize_ansi_escape():
    """Test that ANSI escape sequences are removed."""
    # ANSI color codes: red text
    ansi_text = "\x1b[31mred\x1b[0m"
    result = sanitize_log_value(ansi_text)
    assert result == "red"
    assert "\x1b" not in result

    # Multiple ANSI sequences
    complex_ansi = "\x1b[1m\x1b[32mBold Green\x1b[0m\x1b[33mYellow\x1b[0m"
    result = sanitize_log_value(complex_ansi)
    assert result == "Bold GreenYellow"
    assert "\x1b" not in result


def test_sanitize_newline_injection():
    """Test that newline characters are removed to prevent log forging."""
    # Unix newline
    unix_newline = "value\nINJECTED LOG LINE"
    result = sanitize_log_value(unix_newline)
    assert result == "valueINJECTED LOG LINE"
    assert "\n" not in result

    # Windows newline
    windows_newline = "value\r\nINJECTED LOG LINE"
    result = sanitize_log_value(windows_newline)
    assert result == "valueINJECTED LOG LINE"
    assert "\r" not in result
    assert "\n" not in result

    # Multiple newlines
    multi_newline = "line1\nline2\nline3\n"
    result = sanitize_log_value(multi_newline)
    assert result == "line1line2line3"


def test_sanitize_control_characters():
    """Test that control characters are removed."""
    # NULL, SOH, STX control characters
    control_chars = "\x00\x01\x02test"
    result = sanitize_log_value(control_chars)
    assert result == "test"

    # Vertical tab, form feed
    vt_ff = "text\x0b\x0cmore"
    result = sanitize_log_value(vt_ff)
    assert result == "textmore"

    # DELETE character
    delete_char = "text\x7fmore"
    result = sanitize_log_value(delete_char)
    assert result == "textmore"


def test_sanitize_truncation():
    """Test that strings exceeding max_length are truncated."""
    # Create a string longer than max_length
    long_text = "a" * 200
    result = sanitize_log_value(long_text, max_length=50)
    
    # Should be truncated to 50 characters (47 'a's + '...')
    assert len(result) == 50
    assert result.endswith("...")
    assert result.startswith("aaa")

    # Test with custom max_length
    result = sanitize_log_value(long_text, max_length=20)
    assert len(result) == 20
    assert result.endswith("...")


def test_sanitize_empty_and_none():
    """Test handling of empty strings and None values."""
    # None value
    result = sanitize_log_value(None)
    assert result == "None"

    # Empty string
    result = sanitize_log_value("")
    assert result == "''"

    # Whitespace-only string is not considered empty
    result = sanitize_log_value("   ")
    assert result == "   "


def test_sanitize_unicode_safe():
    """Test that normal Unicode characters (e.g., Turkish) are preserved."""
    # Turkish characters
    turkish_text = "Türkçe karakterler: ğüşıöç"
    result = sanitize_log_value(turkish_text)
    assert result == turkish_text

    # Other Unicode characters
    unicode_text = "Hello 世界 مرحبا"
    result = sanitize_log_value(unicode_text)
    assert result == unicode_text

    # Emoji
    emoji_text = "Test 🎉 emoji"
    result = sanitize_log_value(emoji_text)
    assert result == emoji_text


def test_sanitize_combined_attacks():
    """Test combinations of injection techniques."""
    # ANSI + newline
    combined = "\x1b[31mERROR\x1b[0m\nFAKE ERROR: System compromised"
    result = sanitize_log_value(combined)
    assert result == "ERRORFAKE ERROR: System compromised"
    assert "\x1b" not in result
    assert "\n" not in result

    # Control chars + ANSI + newline
    complex = "\x00\x1b[32mSUCCESS\x1b[0m\nFAKE: Database deleted\x7f"
    result = sanitize_log_value(complex)
    assert "SUCCESS" in result
    assert "FAKE: Database deleted" in result
    assert "\x00" not in result
    assert "\x1b" not in result
    assert "\n" not in result
    assert "\x7f" not in result


def test_sanitize_non_string_values():
    """Test that non-string values are safely converted."""
    # Integer
    result = sanitize_log_value(12345)
    assert result == "12345"

    # List
    result = sanitize_log_value([1, 2, 3])
    assert "[1, 2, 3]" in result

    # Dict
    result = sanitize_log_value({"key": "value"})
    assert "key" in result


def test_sanitize_default_max_length():
    """Test that default max_length is 100."""
    # Create a string longer than 100 characters
    long_text = "b" * 150
    result = sanitize_log_value(long_text)  # No max_length specified
    
    # Should be truncated to 100 characters (default)
    assert len(result) == 100
    assert result.endswith("...")
