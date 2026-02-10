"""Log sanitization utilities to prevent log injection attacks."""

import re
from typing import Optional


# Pattern to match control characters, ANSI escape sequences, and newlines
# Order matters: ANSI escape sequences must be matched before individual control chars
# - \x1b\[[0-9;]*[a-zA-Z]: ANSI escape sequences (e.g., \x1b[31m for red)
# - \r?\n: Newline characters (both Unix and Windows style)
# - [\x00-\x08\x0b\x0c\x0e-\x1f\x7f]: Control characters (excluding \x09 tab and \x0a newline)
#   - \x00-\x08: NULL through BACKSPACE
#   - \x0b: Vertical tab
#   - \x0c: Form feed
#   - \x0e-\x1f: Shift Out through Unit Separator (includes \x1b ESC)
#   - \x7f: DELETE
_LOG_SANITIZER_PATTERN = re.compile(
    r"\x1b\[[0-9;]*[a-zA-Z]|\r?\n|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
)


def sanitize_log_value(value: Optional[str], max_length: int = 100) -> str:
    """
    Sanitize a string value for safe logging by removing control characters,
    ANSI escape sequences, and newlines to prevent log injection attacks.

    Args:
        value: The string value to sanitize (can be None)
        max_length: Maximum length of the sanitized string (default: 100)

    Returns:
        Sanitized string safe for logging

    Examples:
        >>> sanitize_log_value("normal text")
        'normal text'
        >>> sanitize_log_value("\\x1b[31mred\\x1b[0m")
        'red'
        >>> sanitize_log_value("line1\\nline2")
        'line1line2'
        >>> sanitize_log_value("a" * 200, max_length=50)
        'aaaaa...' (truncated to 50 chars with ellipsis)
    """
    # Handle None or empty values
    if value is None:
        return "None"
    
    if not isinstance(value, str):
        # For non-string values, use safe repr()
        value = repr(value)
    
    if not value:
        return "''"
    
    # Remove control characters, ANSI escape sequences, and newlines
    sanitized = _LOG_SANITIZER_PATTERN.sub("", value)
    
    # Truncate if exceeds max_length
    if len(sanitized) > max_length:
        # Reserve 3 characters for ellipsis
        sanitized = sanitized[: max_length - 3] + "..."
    
    return sanitized
