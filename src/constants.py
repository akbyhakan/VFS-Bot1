"""Constants and configuration values for VFS-Bot."""

import os


class Timeouts:
    """Timeout values in milliseconds."""

    PAGE_LOAD = 30000  # 30 seconds
    NAVIGATION = 30000  # 30 seconds
    SELECTOR_WAIT = 10000  # 10 seconds
    NETWORK_IDLE = 30000  # 30 seconds
    CAPTCHA_MANUAL = 120000  # 2 minutes
    CLOUDFLARE_CHALLENGE = 30000  # 30 seconds


class Intervals:
    """Interval values in seconds."""

    CHECK_SLOTS_MIN = 10  # Minimum slot check interval
    CHECK_SLOTS_DEFAULT = 30  # Default slot check interval
    CHECK_SLOTS_MAX = 3600  # Maximum slot check interval (1 hour)

    HUMAN_DELAY_MIN = 0.1  # Minimum human-like delay
    HUMAN_DELAY_MAX = 0.5  # Maximum human-like delay

    TYPING_DELAY_MIN = 0.05  # Minimum typing delay
    TYPING_DELAY_MAX = 0.15  # Maximum typing delay

    ERROR_RECOVERY = 60  # Error recovery wait time
    CIRCUIT_BREAKER_RECOVERY = 300  # Circuit breaker recovery time (5 minutes)


class Retries:
    """Retry configuration."""

    MAX_PROCESS_USER_ATTEMPTS = 3  # Max retries for processing single user
    MAX_LOGIN_ATTEMPTS = 3  # Max login attempts
    MAX_BOOKING_ATTEMPTS = 2  # Max booking attempts

    EXPONENTIAL_MULTIPLIER = 1  # Exponential backoff multiplier
    EXPONENTIAL_MIN = 4  # Minimum exponential backoff (seconds)
    EXPONENTIAL_MAX = 10  # Maximum exponential backoff (seconds)


class RateLimits:
    """Rate limiting configuration."""

    MAX_REQUESTS = 60  # Maximum requests per time window
    TIME_WINDOW = 60  # Time window in seconds

    CONCURRENT_USERS = 5  # Maximum concurrent user processing
    
    # Login-specific rate limits (more restrictive)
    LOGIN_MAX_REQUESTS = 5  # Maximum login attempts per window
    LOGIN_TIME_WINDOW = 300  # 5 minutes
    LOGIN_LOCKOUT_DURATION = 900  # 15 minutes lockout after max attempts


class CaptchaConfig:
    """Captcha configuration."""
    
    MANUAL_TIMEOUT = 120  # Timeout for manual captcha solving (seconds)
    TWOCAPTCHA_TIMEOUT = 180  # Timeout for 2Captcha API (seconds)
    TURNSTILE_TIMEOUT = 120  # Timeout for Cloudflare Turnstile (seconds)


class CircuitBreaker:
    """Circuit breaker configuration."""

    MAX_CONSECUTIVE_ERRORS = 5  # Maximum consecutive errors before opening circuit
    MAX_TOTAL_ERRORS_PER_HOUR = 20  # Maximum total errors per hour
    ERROR_TRACKING_WINDOW = 3600  # Error tracking window in seconds (1 hour)

    # Exponential backoff: min(60 * 2^(errors-1), 600)
    BACKOFF_BASE = 60  # Base backoff time in seconds
    BACKOFF_MAX = 600  # Maximum backoff time in seconds (10 minutes)


class ErrorCapture:
    """Error capture configuration."""

    MAX_ERRORS_IN_MEMORY = 100  # Maximum errors to keep in memory
    CLEANUP_DAYS = 7  # Days to keep error files before cleanup
    CLEANUP_INTERVAL_SECONDS = 3600  # Cleanup check interval (1 hour)
    SCREENSHOTS_DIR = "screenshots/errors"  # Directory for error screenshots


class Database:
    """Database configuration."""

    DEFAULT_PATH = os.getenv("DATABASE_PATH", "vfs_bot.db")  # Configurable database path
    POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))  # Configurable pool size
    TEST_PATH = "test.db"  # Test database path
    CONNECTION_TIMEOUT = float(os.getenv("DB_CONNECTION_TIMEOUT", "30.0"))  # Configurable timeout


class API:
    """API configuration."""

    DEFAULT_PORT = 8000  # Default API port
    DEFAULT_HOST = "0.0.0.0"  # Default API host
    RATE_LIMIT = "100/minute"  # API rate limit


class Metrics:
    """Metrics configuration."""

    RETENTION_DAYS = 30  # Days to keep metrics data


class Limits:
    """Application limits."""

    MAX_LOG_ENTRIES = 500  # Maximum log entries to keep
    MAX_ERRORS_IN_MEMORY = 100  # Maximum errors to keep in memory
    DB_CONNECTION_TIMEOUT = Database.CONNECTION_TIMEOUT  # Database connection timeout (reference)


class Delays:
    """UI interaction delays in seconds."""

    DROPDOWN_WAIT = 2.0  # Wait after dropdown selection
    BUTTON_CLICK_WAIT = 0.5  # Wait after button click
    FORM_SUBMIT_WAIT = 3.0  # Wait after form submission
    PAGE_LOAD_BUFFER = 1.0  # Extra buffer for page loads

    # Random delay ranges for human-like behavior
    SHORT_MIN = 0.3
    SHORT_MAX = 0.7
    MEDIUM_MIN = 1.5
    MEDIUM_MAX = 3.0
    LONG_MIN = 2.5
    LONG_MAX = 5.0

    # Specific action delays (min, max)
    AFTER_LOGIN_FIELD = (0.3, 0.7)
    AFTER_SELECT_OPTION = (1.5, 3.0)
    AFTER_CLICK_CHECK = (2.5, 4.0)


class Defaults:
    """Default configuration values."""

    API_TIMEOUT = 30  # API request timeout in seconds
    DB_POOL_SIZE = Database.POOL_SIZE  # Database connection pool size (references Database.POOL_SIZE for consistency)
    RATE_LIMIT_REQUESTS = 60  # Maximum requests per time window
    RATE_LIMIT_WINDOW = 60  # Rate limit time window in seconds
    TOKEN_REFRESH_BUFFER_MINUTES = 5  # Token refresh buffer in minutes
    GRACEFUL_SHUTDOWN_TIMEOUT = 5  # Graceful shutdown timeout in seconds


class BookingTimeouts:
    """Timeout constants for booking operations (in seconds or milliseconds)."""
    
    TIME_SLOTS_LOAD = 2.0  # Time to wait for slot data to load (seconds)
    DROPDOWN_ANIMATION = 0.5  # Wait for dropdown animations (seconds)
    ELEMENT_WAIT_MS = 10000  # Element wait timeout (milliseconds)
    PAGE_LOAD_MS = 30000  # Page load timeout (milliseconds)
    PAYMENT_CONFIRMATION = 60  # Payment confirmation wait (seconds)
    OTP_WAIT = 120  # OTP wait timeout (seconds)


class BookingDelays:
    """Delay constants for human-like behavior (in seconds or milliseconds)."""
    
    # Typing simulation
    TYPING_MIN_MS = 50  # Minimum typing delay per character (milliseconds)
    TYPING_MAX_MS = 150  # Maximum typing delay per character (milliseconds)
    
    # Random pauses during typing
    PAUSE_CHANCE = 0.1  # 10% chance of pause during typing
    PAUSE_MIN = 0.1  # Minimum pause duration (seconds)
    PAUSE_MAX = 0.3  # Maximum pause duration (seconds)
    
    # Delays between form fields
    BETWEEN_FIELDS_MIN = 0.3  # Minimum delay between fields (seconds)
    BETWEEN_FIELDS_MAX = 0.8  # Maximum delay between fields (seconds)
