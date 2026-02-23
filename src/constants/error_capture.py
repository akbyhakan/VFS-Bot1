"""Error capture configuration."""

from typing import Final


class ErrorCaptureConfig:
    """Error capture configuration."""

    MAX_IN_MEMORY: Final[int] = 100
    CLEANUP_DAYS: Final[int] = 3
    CLEANUP_INTERVAL_SECONDS: Final[int] = 3600
    SCREENSHOTS_DIR: Final[str] = "screenshots/errors"
    MAX_DISK_FILES: Final[int] = 500
    RAPID_ERROR_COOLDOWN_SECONDS: Final[int] = 5
