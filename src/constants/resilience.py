"""Resilience-related constants (retries, rate limits, circuit breakers, account pool)."""

from typing import Final


class Retries:
    """Retry configuration."""

    MAX_PROCESS_USER: Final[int] = 3
    MAX_LOGIN: Final[int] = 3
    MAX_BOOKING: Final[int] = 2
    MAX_NETWORK: Final[int] = 3
    BACKOFF_MULTIPLIER: Final[int] = 1
    BACKOFF_MIN_SECONDS: Final[int] = 4
    BACKOFF_MAX_SECONDS: Final[int] = 10


class RateLimits:
    """Rate limiting configuration."""

    MAX_REQUESTS: Final[int] = 60
    TIME_WINDOW_SECONDS: Final[int] = 60
    CONCURRENT_USERS: Final[int] = 5
    LOGIN_MAX_REQUESTS: Final[int] = 5
    LOGIN_WINDOW_SECONDS: Final[int] = 300
    LOGIN_LOCKOUT_SECONDS: Final[int] = 900

    # Authentication rate limiting (brute-force protection)
    AUTH_RATE_LIMIT_ATTEMPTS: Final[int] = 5
    AUTH_RATE_LIMIT_WINDOW: Final[int] = 60


class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    FAIL_THRESHOLD: Final[int] = 5
    TIMEOUT_SECONDS: Final[float] = 60.0
    HALF_OPEN_SUCCESS_THRESHOLD: Final[int] = 3
    MAX_ERRORS_PER_HOUR: Final[int] = 20
    ERROR_WINDOW_SECONDS: Final[int] = 3600
    RESET_TIMEOUT_SECONDS: Final[int] = 60
    HALF_OPEN_MAX_CALLS: Final[int] = 3
    BACKOFF_BASE_SECONDS: Final[int] = 60
    BACKOFF_MAX_SECONDS: Final[int] = 600
    BATCH_ERROR_RATE_THRESHOLD: Final[float] = 0.5


class AccountPoolConfig:
    """Account pool configuration for shared VFS account management."""

    COOLDOWN_SECONDS: Final[int] = 600  # 10 minutes
    QUARANTINE_SECONDS: Final[int] = 1800  # 30 minutes
    MAX_FAILURES: Final[int] = 3
    MAX_CONCURRENT_MISSIONS: Final[int] = 5
    WAIT_FOR_ACCOUNT_TIMEOUT: Final[float] = 60.0  # seconds
