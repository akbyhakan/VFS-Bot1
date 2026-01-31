"""Input validation utilities for VFS-Bot."""

import re
import unicodedata
from typing import List, Optional


# Maximum lengths for different field types
MAX_LENGTHS = {
    "email": 254,
    "phone": 20,
    "name": 100,
    "passport": 20,
    "address": 500,
    "default": 255,
}


def sanitize_input(
    value: str,
    field_type: str = "default",
    max_length: Optional[int] = None,
    allow_unicode: bool = True,
) -> str:
    """
    Sanitize user input to prevent injection attacks.

    Args:
        value: Input value to sanitize
        field_type: Type of field for length validation
        max_length: Override max length (optional)
        allow_unicode: Allow unicode characters (default: True)

    Returns:
        Sanitized string

    Raises:
        ValueError: If value contains dangerous characters
    """
    if not value:
        return ""

    # Remove null bytes (SQL injection prevention)
    value = value.replace("\x00", "")

    # Remove other control characters (except newlines for text fields)
    value = "".join(
        char for char in value if unicodedata.category(char) != "Cc" or char in "\n\r\t"
    )

    # Normalize unicode (prevents homograph attacks)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        # ASCII only
        value = value.encode("ascii", "ignore").decode("ascii")

    # Truncate to max length
    max_len = max_length or MAX_LENGTHS.get(field_type, MAX_LENGTHS["default"])
    value = value[:max_len]

    # Strip whitespace
    return value.strip()


def sanitize_email(email: str) -> str:
    """Sanitize and validate email address."""
    email = sanitize_input(email, field_type="email", allow_unicode=False)
    if not validate_email(email):
        raise ValueError(f"Invalid email format: {email}")
    return email.lower()


def sanitize_phone(phone: str) -> str:
    """Sanitize and validate phone number."""
    # Remove all non-digit characters except leading +
    sanitized = phone.strip()
    if sanitized.startswith("+"):
        sanitized = "+" + "".join(c for c in sanitized[1:] if c.isdigit())
    else:
        sanitized = "".join(c for c in sanitized if c.isdigit())

    if not validate_phone(sanitized):
        raise ValueError(f"Invalid phone format: {phone}")
    return sanitized


def sanitize_name(name: str) -> str:
    """Sanitize name field (allows unicode for international names)."""
    name = sanitize_input(name, field_type="name", allow_unicode=True)

    # Check for suspicious patterns (script injection)
    suspicious_patterns = ["<", ">", "${", "{{", "javascript:", "data:"]
    name_lower = name.lower()
    for pattern in suspicious_patterns:
        if pattern in name_lower:
            raise ValueError(f"Name contains suspicious characters: {name[:50]}")

    return name


def validate_email(email: str) -> bool:
    """
    Validate email format.

    Args:
        email: Email address to validate

    Returns:
        True if email format is valid, False otherwise
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """
    Validate phone number format.

    Args:
        phone: Phone number to validate

    Returns:
        True if phone format is valid, False otherwise
    """
    # Remove common separators for validation
    clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    pattern = r"^\+?[1-9]\d{9,14}$"
    return bool(re.match(pattern, clean_phone))


def validate_centre(centre: str, allowed_centres: List[str]) -> bool:
    """
    Validate centre against allowed list.

    Args:
        centre: Centre name to validate
        allowed_centres: List of allowed centre names

    Returns:
        True if centre is in allowed list, False otherwise
    """
    return centre.strip() in allowed_centres


def validate_category(category: str, allowed_categories: List[str]) -> bool:
    """
    Validate category against allowed list.

    Args:
        category: Category to validate
        allowed_categories: List of allowed categories

    Returns:
        True if category is in allowed list, False otherwise
    """
    return category.strip() in allowed_categories
