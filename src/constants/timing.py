"""Timing-related constants (timeouts, intervals, delays)."""

from typing import Final


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
    GRACEFUL_SHUTDOWN_GRACE_PERIOD: Final[int] = 120  # Grace period for active bookings


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


class Delays:
    """UI interaction delays in SECONDS."""

    DROPDOWN_WAIT: Final[float] = 2.0
    BUTTON_CLICK_WAIT: Final[float] = 0.5
    FORM_SUBMIT_WAIT: Final[float] = 3.0
    PAGE_LOAD_BUFFER: Final[float] = 1.0
    SHORT: Final[tuple[float, float]] = (0.3, 0.7)
    MEDIUM: Final[tuple[float, float]] = (1.5, 3.0)
    LONG: Final[tuple[float, float]] = (2.5, 5.0)
    AFTER_LOGIN_FIELD: Final[tuple[float, float]] = (0.3, 0.7)
    AFTER_SELECT_OPTION: Final[tuple[float, float]] = (1.5, 3.0)
    AFTER_CLICK_CHECK: Final[tuple[float, float]] = (2.5, 4.0)
    AFTER_CONTINUE_CLICK: Final[float] = 2.0  # Wait after clicking continue button
    RESTART_DELAY: Final[float] = 2.0  # Delay between stop and start during restart
    TIME_SLOTS_LOAD_WAIT: Final[float] = 2.0  # Wait for time slots to load after date selection
    CHALLENGE_POLL_INTERVAL: Final[float] = 2.0  # Polling interval for Cloudflare challenges


class BookingTimeouts:
    """Booking operation timeouts."""

    TIME_SLOTS_LOAD: Final[float] = 2.0
    DROPDOWN_ANIMATION: Final[float] = 0.5
    ELEMENT_WAIT_MS: Final[int] = 10000
    PAGE_LOAD_MS: Final[int] = 30000
    PAYMENT_CONFIRMATION: Final[int] = 60
    OTP_WAIT: Final[int] = (
        300  # FIXED: Consistent with OTP.TIMEOUT_SECONDS and Timeouts.OTP_WAIT_SECONDS
    )


class BookingDelays:
    """Human-like behavior delays."""

    TYPING_MIN_MS: Final[int] = 50
    TYPING_MAX_MS: Final[int] = 150
    PAUSE_CHANCE: Final[float] = 0.1
    PAUSE_MIN: Final[float] = 0.1
    PAUSE_MAX: Final[float] = 0.3
    BETWEEN_FIELDS_MIN: Final[float] = 0.3
    BETWEEN_FIELDS_MAX: Final[float] = 0.8
