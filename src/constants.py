"""Unified constants and configuration values for VFS-Bot."""

import os
import warnings
from typing import Final


# =============================================================================
# TIMEOUTS
# =============================================================================
class Timeouts:
    """Timeout values - MILLISECONDS for Playwright, SECONDS noted separately."""

    # Playwright timeouts (milliseconds)
    PAGE_LOAD: Final[int] = 30_000
    NAVIGATION: Final[int] = 30_000
    SELECTOR_WAIT: Final[int] = 10_000
    NETWORK_IDLE: Final[int] = 30_000
    CAPTCHA_MANUAL: Final[int] = 120_000
    CLOUDFLARE_CHALLENGE: Final[int] = 30_000

    # API/Service timeouts (seconds)
    HTTP_REQUEST_SECONDS: Final[int] = 30
    OTP_WAIT_SECONDS: Final[int] = 300  # FIXED: Was 120 in BookingTimeouts
    PAYMENT_WAIT_SECONDS: Final[int] = 300
    DATABASE_CONNECTION_SECONDS: Final[float] = 30.0
    WEBSOCKET_PING_SECONDS: Final[int] = 30
    GRACEFUL_SHUTDOWN_SECONDS: Final[int] = 5
    SHUTDOWN_TIMEOUT: Final[int] = 30
    MAX_MANUAL_TIMEOUT: Final[int] = 300


class Intervals:
    """Interval values in SECONDS."""

    CHECK_SLOTS_MIN: Final[int] = 10
    CHECK_SLOTS_DEFAULT: Final[int] = 30
    CHECK_SLOTS_MAX: Final[int] = 3600
    HUMAN_DELAY_MIN: Final[float] = 0.1
    HUMAN_DELAY_MAX: Final[float] = 0.5
    TYPING_DELAY_MIN: Final[float] = 0.05
    TYPING_DELAY_MAX: Final[float] = 0.15
    ERROR_RECOVERY: Final[int] = 60
    CIRCUIT_BREAKER_RECOVERY: Final[int] = 300
    CLEANUP_INTERVAL: Final[int] = 60
    DEFAULT_CHECK_INTERVAL: Final[int] = 60


class Retries:
    """Retry configuration."""

    MAX_PROCESS_USER: Final[int] = 3
    MAX_LOGIN: Final[int] = 3
    MAX_BOOKING: Final[int] = 2
    MAX_NETWORK: Final[int] = 3
    BACKOFF_MULTIPLIER: Final[int] = 1
    BACKOFF_MIN_SECONDS: Final[int] = 4
    BACKOFF_MAX_SECONDS: Final[int] = 10

    # Aliases for backward compatibility
    MAX_PROCESS_USER_ATTEMPTS: Final[int] = MAX_PROCESS_USER
    EXPONENTIAL_MULTIPLIER: Final[int] = BACKOFF_MULTIPLIER
    EXPONENTIAL_MIN: Final[int] = BACKOFF_MIN_SECONDS
    EXPONENTIAL_MAX: Final[int] = BACKOFF_MAX_SECONDS


class RateLimits:
    """Rate limiting configuration."""

    MAX_REQUESTS: Final[int] = 60
    TIME_WINDOW_SECONDS: Final[int] = 60
    CONCURRENT_USERS: Final[int] = 5
    LOGIN_MAX_REQUESTS: Final[int] = 5
    LOGIN_WINDOW_SECONDS: Final[int] = 300
    LOGIN_LOCKOUT_SECONDS: Final[int] = 900

    # Authentication rate limiting (brute-force protection) - window in seconds
    AUTH_RATE_LIMIT_ATTEMPTS: Final[int] = int(os.getenv("AUTH_RATE_LIMIT_ATTEMPTS", "5"))
    AUTH_RATE_LIMIT_WINDOW: Final[int] = int(os.getenv("AUTH_RATE_LIMIT_WINDOW", "60"))


class Security:
    """Security configuration."""

    MIN_SECRET_KEY_LENGTH: Final[int] = 64
    MIN_API_KEY_SALT_LENGTH: Final[int] = 32
    MIN_ENCRYPTION_KEY_LENGTH: Final[int] = 32
    JWT_ALGORITHM: Final[str] = "HS256"
    JWT_EXPIRY_HOURS: Final[int] = 24
    PASSWORD_HASH_ROUNDS: Final[int] = 12
    MAX_LOGIN_ATTEMPTS: Final[int] = 5
    LOCKOUT_DURATION_MINUTES: Final[int] = 15
    SESSION_FILE_PERMISSIONS: Final[int] = 0o600


class CaptchaConfig:
    """Captcha configuration."""

    MANUAL_TIMEOUT: Final[int] = 120
    TWOCAPTCHA_TIMEOUT: Final[int] = 180
    TURNSTILE_TIMEOUT: Final[int] = 120


class CircuitBreaker:
    """Circuit breaker configuration."""

    FAIL_THRESHOLD: Final[int] = 5
    FAILURE_THRESHOLD: Final[int] = 5  # Alias for compatibility
    TIMEOUT_SECONDS: Final[float] = 60.0
    HALF_OPEN_SUCCESS_THRESHOLD: Final[int] = 3
    MAX_ERRORS_PER_HOUR: Final[int] = 20
    ERROR_WINDOW_SECONDS: Final[int] = 3600
    RESET_TIMEOUT_SECONDS: Final[int] = 60
    HALF_OPEN_MAX_CALLS: Final[int] = 3
    BACKOFF_BASE_SECONDS: Final[int] = 60
    BACKOFF_MAX_SECONDS: Final[int] = 600

    # Aliases for backward compatibility
    MAX_CONSECUTIVE_ERRORS: Final[int] = FAIL_THRESHOLD
    MAX_TOTAL_ERRORS_PER_HOUR: Final[int] = MAX_ERRORS_PER_HOUR
    ERROR_TRACKING_WINDOW: Final[int] = ERROR_WINDOW_SECONDS
    BACKOFF_BASE: Final[int] = BACKOFF_BASE_SECONDS
    BACKOFF_MAX: Final[int] = BACKOFF_MAX_SECONDS


class OTP:
    """OTP service configuration."""

    MAX_ENTRIES: Final[int] = 100
    TIMEOUT_SECONDS: Final[int] = 300
    CLEANUP_INTERVAL_SECONDS: Final[int] = 60


class ErrorCapture:
    """Error capture configuration."""

    MAX_IN_MEMORY: Final[int] = 100
    CLEANUP_DAYS: Final[int] = 7
    CLEANUP_INTERVAL_SECONDS: Final[int] = 3600
    SCREENSHOTS_DIR: Final[str] = "screenshots/errors"


class Database:
    """Database configuration."""

    DEFAULT_PATH: Final[str] = os.getenv("DATABASE_PATH", "vfs_bot.db")
    TEST_PATH: Final[str] = "test.db"
    # Pool size: Default is 10, can be overridden via DB_POOL_SIZE env var
    POOL_SIZE: Final[int] = int(os.getenv("DB_POOL_SIZE", "10"))
    CONNECTION_TIMEOUT: Final[float] = float(os.getenv("DB_CONNECTION_TIMEOUT", "30.0"))
    QUERY_TIMEOUT: Final[float] = 30.0
    BUSY_TIMEOUT_MS: Final[int] = 30000
    DEFAULT_CACHE_TTL: Final[int] = int(os.getenv("CACHE_TTL_SECONDS", "3600"))


class Pools:
    """Connection pool sizes."""

    DATABASE: Final[int] = Database.POOL_SIZE
    HTTP_LIMIT: Final[int] = 50
    HTTP_LIMIT_PER_HOST: Final[int] = 20
    DNS_CACHE_TTL: Final[int] = 120
    KEEPALIVE_TIMEOUT: Final[int] = 30


class Delays:
    """UI interaction delays in SECONDS."""

    DROPDOWN_WAIT: Final[float] = 2.0
    BUTTON_CLICK_WAIT: Final[float] = 0.5
    FORM_SUBMIT_WAIT: Final[float] = 3.0
    PAGE_LOAD_BUFFER: Final[float] = 1.0
    SHORT: Final[tuple] = (0.3, 0.7)
    MEDIUM: Final[tuple] = (1.5, 3.0)
    LONG: Final[tuple] = (2.5, 5.0)
    AFTER_LOGIN_FIELD: Final[tuple] = (0.3, 0.7)
    AFTER_SELECT_OPTION: Final[tuple] = (1.5, 3.0)
    AFTER_CLICK_CHECK: Final[tuple] = (2.5, 4.0)


class BookingTimeouts:
    """Booking operation timeouts."""

    TIME_SLOTS_LOAD: Final[float] = 2.0
    DROPDOWN_ANIMATION: Final[float] = 0.5
    ELEMENT_WAIT_MS: Final[int] = 10000
    PAGE_LOAD_MS: Final[int] = 30000
    PAYMENT_CONFIRMATION: Final[int] = 60
    OTP_WAIT: Final[
        int
    ] = 300  # FIXED: Consistent with OTP.TIMEOUT_SECONDS and Timeouts.OTP_WAIT_SECONDS


class BookingDelays:
    """Human-like behavior delays."""

    TYPING_MIN_MS: Final[int] = 50
    TYPING_MAX_MS: Final[int] = 150
    PAUSE_CHANCE: Final[float] = 0.1
    PAUSE_MIN: Final[float] = 0.1
    PAUSE_MAX: Final[float] = 0.3
    BETWEEN_FIELDS_MIN: Final[float] = 0.3
    BETWEEN_FIELDS_MAX: Final[float] = 0.8


class LogEmoji:
    """Emoji constants for consistent logging."""

    SUCCESS: Final[str] = "✅"
    ERROR: Final[str] = "❌"
    WARNING: Final[str] = "⚠️"
    INFO: Final[str] = "ℹ️"
    DEBUG: Final[str] = "🔍"
    START: Final[str] = "🚀"
    STOP: Final[str] = "🛑"
    PROCESSING: Final[str] = "⚙️"
    WAITING: Final[str] = "⏳"
    RETRY: Final[str] = "🔄"
    FOUND: Final[str] = "🎯"
    COMPLETE: Final[str] = "✔️"
    LOCK: Final[str] = "🔒"
    UNLOCK: Final[str] = "🔓"
    KEY: Final[str] = "🔑"
    SHIELD: Final[str] = "🛡️"
    ALERT: Final[str] = "🚨"
    BOT: Final[str] = "🤖"
    CALENDAR: Final[str] = "📅"
    PAYMENT: Final[str] = "💳"


# =============================================================================
# BACKWARD COMPATIBILITY (Deprecated - will be removed in v3.0)
# =============================================================================
class Defaults:
    """DEPRECATED: Use specific classes instead. Will be removed in v3.0."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        warnings.warn(
            "Defaults class is deprecated. Use specific classes "
            "(Timeouts, Database, RateLimits) instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    API_TIMEOUT = Timeouts.HTTP_REQUEST_SECONDS
    DB_POOL_SIZE = Database.POOL_SIZE
    DB_CONNECTION_TIMEOUT = Database.CONNECTION_TIMEOUT
    RATE_LIMIT_REQUESTS = RateLimits.MAX_REQUESTS
    RATE_LIMIT_WINDOW = RateLimits.TIME_WINDOW_SECONDS
    TOKEN_REFRESH_BUFFER_MINUTES = 5
    GRACEFUL_SHUTDOWN_TIMEOUT = Timeouts.GRACEFUL_SHUTDOWN_SECONDS


class Limits:
    """DEPRECATED: Use specific classes instead."""

    MAX_LOG_ENTRIES = 500
    MAX_ERRORS_IN_MEMORY = ErrorCapture.MAX_IN_MEMORY
    DB_CONNECTION_TIMEOUT = Database.CONNECTION_TIMEOUT


class RateLimitDefaults:
    """Default values for rate limiting - used by rate_limiter.py."""

    MAX_REQUESTS: int = 60
    TIME_WINDOW: int = 60
