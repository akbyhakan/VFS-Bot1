"""Utility functions for masking sensitive data in logs and outputs."""

from typing import Any, Dict, Optional, Set
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def mask_database_url(url: str) -> str:
    """
    Mask sensitive information in connection URLs for safe logging.

    Masks both credentials in the netloc (user:password@host) and
    sensitive query parameters like password, sslpassword, tokens, etc.

    This function works with any connection URL (database, Redis, etc.)
    that may contain sensitive credentials.

    Args:
        url: Connection URL potentially containing credentials

    Returns:
        Masked URL safe for logging

    Examples:
        >>> mask_database_url("postgresql://user:pass@localhost:5432/mydb")
        'postgresql://***:***@localhost:5432/mydb'
        >>> mask_database_url("postgresql://user:pass@localhost/db?password=secret&sslmode=require")
        'postgresql://***:***@localhost/db?password=***&sslmode=require'
        >>> mask_database_url("redis://user:pass@localhost:6379")
        'redis://***:***@localhost:6379'
        >>> mask_database_url("sqlite:///path/to/db.sqlite")
        'sqlite://***'
        >>> mask_database_url("invalid-url")
        '<unparseable-url>'
    """
    try:
        parsed = urlparse(url)

        # Handle empty or missing scheme
        if not parsed.scheme:
            return "<unparseable-url>"

        # Handle non-network URLs (SQLite, etc.) - show only scheme
        if not parsed.netloc:
            return f"{parsed.scheme}://***"

        # For network URLs, mask credentials if present
        if parsed.username or parsed.password:
            # Rebuild netloc with masked credentials
            host_port = parsed.hostname or "unknown"
            if parsed.port:
                host_port = f"{host_port}:{parsed.port}"
            masked_netloc = f"***:***@{host_port}"
        else:
            # No credentials, keep original netloc
            masked_netloc = parsed.netloc

        # Mask sensitive query parameters
        masked_query = parsed.query
        if parsed.query:
            # Sensitive parameter names to mask (lowercase for case-insensitive matching)
            sensitive_params = {
                "password",
                "sslpassword",
                "sslkey",
                "sslcert",
                "sslrootcert",
                "secret",
                "token",
                "api_key",
                "apikey",
                "access_key",
                "auth",
            }

            # Parse query string
            params = parse_qs(parsed.query, keep_blank_values=True)

            # Mask sensitive parameters (optimized with set membership check)
            for key in params:
                key_lower = key.lower()
                if any(sensitive in key_lower for sensitive in sensitive_params):
                    params[key] = ["***"] * len(params[key])

            # Rebuild query string without URL-encoding the asterisks
            masked_query = urlencode(params, doseq=True, safe="*")

        # Rebuild URL with masked netloc and query
        masked = parsed._replace(netloc=masked_netloc, query=masked_query)
        return urlunparse(masked)

    except Exception:
        # If parsing fails entirely, return safe placeholder
        return "<unparseable-url>"


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


def mask_expiry_date(month: str, year: str) -> str:
    """
    Mask credit card expiry date.

    Args:
        month: Expiry month (MM)
        year: Expiry year (YYYY or YY)

    Returns:
        Masked expiry date (e.g., "**/****")
    """
    # Validate inputs
    if not month or not year:
        return "**/**"

    # Determine year format based on length
    try:
        year_mask = "****" if len(year) == 4 else "**"
    except (TypeError, AttributeError):
        year_mask = "**"

    return f"**/{year_mask}"


def mask_cvv(cvv: str) -> str:
    """
    Mask CVV code completely.

    Args:
        cvv: CVV code to mask

    Returns:
        Completely masked CVV (always "***")
    """
    return "***"


def mask_sensitive_dict(
    data: Dict[str, Any], sensitive_keys: Optional[Set[str]] = None
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
            "password",
            "cvv",
            "card_number",
            "api_key",
            "secret",
            "token",
            "access_token",
            "refresh_token",
            "encryption_key",
            "otp",
            "otp_code",
        }

    masked_data: Dict[str, Any] = {}

    for key, value in data.items():
        if key.lower() in sensitive_keys:
            # Completely mask sensitive fields
            masked_data[key] = "********"
        elif key.lower() == "email" and isinstance(value, str):
            # Mask email addresses
            masked_data[key] = mask_email(value)
        elif key.lower() in {"phone", "mobile", "mobile_number", "phone_number"} and isinstance(
            value, str
        ):
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
