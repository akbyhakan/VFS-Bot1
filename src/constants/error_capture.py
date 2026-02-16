"""Error capture configuration."""

from typing import Final


class ErrorCapture:
    """Error capture configuration."""

    MAX_IN_MEMORY: Final[int] = 100
    CLEANUP_DAYS: Final[int] = 7
    CLEANUP_INTERVAL_SECONDS: Final[int] = 3600
    SCREENSHOTS_DIR: Final[str] = "screenshots/errors"
