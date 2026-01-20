"""Utility functions for masking sensitive data in logs and outputs."""

import re
from typing import Any, Dict, List, Set


def mask_email(email: str) -> str:
    """
    Mask email address for logging purposes.
    
    Example: user@example.com -> u***@e***.com
    
    Args:
        email: Email address to mask
    
    Returns:
        Masked email address
    """
    if not email or "@" not in email:
        return "***"
    
    parts = email.split("@")
    if len(parts) != 2:
        return "***"
    
    local, domain = parts
    
    # Mask local part: keep first character
    if len(local) > 0:
        masked_local = local[0] + "***"
    else:
        masked_local = "***"
    
    # Mask domain: keep first character before dot
    domain_parts = domain.split(".")
    if len(domain_parts) >= 2:
        masked_domain = domain_parts[0][0] + "***" if len(domain_parts[0]) > 0 else "***"
        masked_domain += "." + ".".join(domain_parts[1:])
    else:
        masked_domain = "***"
    
    return f"{masked_local}@{masked_domain}"


def mask_phone(phone: str) -> str:
    """
    Mask phone number for logging purposes.
    
    Example: +905551234567 -> +***4567
    
    Args:
        phone: Phone number to mask
    
    Returns:
        Masked phone number
    """
    if not phone or len(phone) < 4:
        return "***"
    
    # Keep country code (if starts with +) and last 4 digits
    if phone.startswith("+"):
        # Find where country code ends (varies: +1, +44, +971, etc.)
        # Safe approach: show only the + and last 4 digits
        return "+" + "***" + phone[-4:]
    else:
        # No country code - just show last 4 digits
        return "***" + phone[-4:]


def mask_password(_password: str) -> str:
    """
    Completely mask password.
    
    Args:
        _password: Password to mask (unused, parameter for API consistency)
    
    Returns:
        Masked password (always ******** - 8 asterisks)
    """
    return "********"


def mask_card_number(card_number: str) -> str:
    """
    Mask credit card number showing only last 4 digits.
    
    Example: 1234567890123456 -> ************3456
    
    Args:
        card_number: Credit card number to mask
    
    Returns:
        Masked card number showing only last 4 digits
    """
    if not card_number or len(card_number) < 4:
        return "****"
    return "*" * (len(card_number) - 4) + card_number[-4:]


def mask_otp(otp: str) -> str:
    """
    Mask OTP code completely.
    
    Args:
        otp: OTP code to mask
    
    Returns:
        Completely masked OTP (all asterisks)
    """
    if not otp:
        return "****"
    return "*" * len(otp)


def mask_sensitive_dict(
    data: Dict[str, Any],
    sensitive_keys: Set[str] = None
) -> Dict[str, Any]:
    """
    Mask sensitive values in a dictionary for logging.
    
    Default sensitive keys: password, cvv, card_number, api_key, secret, token
    
    Args:
        data: Dictionary with potentially sensitive data
        sensitive_keys: Set of keys to mask (uses defaults if None)
    
    Returns:
        New dictionary with masked sensitive values
    """
    if sensitive_keys is None:
        sensitive_keys = {
            "password", "cvv", "card_number", "api_key", "secret", 
            "token", "access_token", "refresh_token", "encryption_key",
            "otp", "otp_code"
        }
    
    masked_data = {}
    
    for key, value in data.items():
        if key.lower() in sensitive_keys:
            # Completely mask sensitive fields
            masked_data[key] = "********"
        elif key.lower() == "email" and isinstance(value, str):
            # Mask email addresses
            masked_data[key] = mask_email(value)
        elif key.lower() in {"phone", "mobile", "mobile_number", "phone_number"} and isinstance(value, str):
            # Mask phone numbers
            masked_data[key] = mask_phone(value)
        elif isinstance(value, dict):
            # Recursively mask nested dictionaries
            masked_data[key] = mask_sensitive_dict(value, sensitive_keys)
        elif isinstance(value, list):
            # Mask items in lists (if they are dicts)
            masked_data[key] = [
                mask_sensitive_dict(item, sensitive_keys) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            masked_data[key] = value
    
    return masked_data


def safe_log_user(user_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare user dictionary for safe logging by masking sensitive fields.
    
    Args:
        user_dict: User dictionary from database
    
    Returns:
        Dictionary safe for logging
    """
    return mask_sensitive_dict(user_dict)
