"""Input validation utilities for VFS-Bot."""

import re
from typing import List


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
