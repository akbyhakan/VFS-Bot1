"""Unified constants and configuration values for VFS-Bot.

This package provides organized constants split across multiple modules
while maintaining backward compatibility with the original flat structure.

All classes and constants can be imported directly from this package:
    from src.constants import Timeouts, Security, TURKISH_MONTHS, etc.
"""

# Timing-related
from .timing import (
    BookingDelays,
    BookingTimeouts,
    Delays,
    Intervals,
    Timeouts,
)

# Resilience-related
from .resilience import (
    AccountPoolConfig,
    CircuitBreakerConfig,
    RateLimits,
    Retries,
)

# Security-related
from .security import (
    ALLOWED_PERSONAL_DETAILS_FIELDS,
    ALLOWED_USER_UPDATE_FIELDS,
    Security,
)

# Captcha
from .captcha import CaptchaConfig

# OTP
from .otp import (
    BookingOTPSelectors,
    OTP,
)

# Database and pools
from .database import (
    Database,
    Pools,
)

# Locale
from .locale import (
    DOUBLE_MATCH_PATTERNS,
    TURKISH_MONTHS,
)

# Logging
from .logging import LogEmoji

# Error capture
from .error_capture import ErrorCapture

# Countries
from .countries import (
    CountryInfo,
    MissionCode,
    SOURCE_COUNTRY_CODE,
    SOURCE_LANGUAGE,
    SUPPORTED_COUNTRIES,
    get_all_supported_codes,
    get_country_info,
    get_route,
    validate_mission_code,
)

__all__ = [
    # Timing
    "Timeouts",
    "Intervals",
    "Delays",
    "BookingTimeouts",
    "BookingDelays",
    # Resilience
    "Retries",
    "RateLimits",
    "CircuitBreakerConfig",
    "AccountPoolConfig",
    # Security
    "Security",
    "ALLOWED_PERSONAL_DETAILS_FIELDS",
    "ALLOWED_USER_UPDATE_FIELDS",
    # Captcha
    "CaptchaConfig",
    # OTP
    "OTP",
    "BookingOTPSelectors",
    # Database
    "Database",
    "Pools",
    # Locale
    "TURKISH_MONTHS",
    "DOUBLE_MATCH_PATTERNS",
    # Logging
    "LogEmoji",
    # Error capture
    "ErrorCapture",
    # Countries
    "MissionCode",
    "CountryInfo",
    "SOURCE_COUNTRY_CODE",
    "SOURCE_LANGUAGE",
    "SUPPORTED_COUNTRIES",
    "get_route",
    "validate_mission_code",
    "get_country_info",
    "get_all_supported_codes",
]
