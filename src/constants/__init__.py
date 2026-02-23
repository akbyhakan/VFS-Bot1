"""Unified constants and configuration values for VFS-Bot.

This package provides organized constants split across multiple modules
while maintaining backward compatibility with the original flat structure.

All classes and constants can be imported directly from this package:
    from src.constants import Timeouts, Security, TURKISH_MONTHS, etc.
"""

# Captcha
from .captcha import CaptchaConfig

# Countries
from .countries import (
    SOURCE_COUNTRY_CODE,
    SOURCE_LANGUAGE,
    SUPPORTED_COUNTRIES,
    CountryInfo,
    MissionCode,
    get_all_supported_codes,
    get_country_info,
    get_route,
    validate_mission_code,
)

# Database and pools
from .database import (
    Database,
    Pools,
)

# Error capture config
from .error_capture import ErrorCaptureConfig

# Locale
from .locale import (
    DOUBLE_MATCH_PATTERNS,
    TURKISH_MONTHS,
)

# Logging
from .logging import LogEmoji

# OTP
from .otp import (
    OTP,
    BookingOTPSelectors,
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

# Timing-related
from .timing import (
    BookingDelays,
    BookingTimeouts,
    Delays,
    Intervals,
    Timeouts,
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
    "ErrorCaptureConfig",
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
