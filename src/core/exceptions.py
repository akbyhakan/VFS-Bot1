"""Custom exception classes for VFS Bot."""

from typing import List, Optional


class VFSBotError(Exception):
    """Base exception for VFS Bot."""

    def __init__(self, message: str, recoverable: bool = True):
        """
        Initialize VFS Bot error.

        Args:
            message: Error message
            recoverable: Whether the error is recoverable with retry
        """
        self.message = message
        self.recoverable = recoverable
        super().__init__(self.message)


class LoginError(VFSBotError):
    """Login operation failed."""

    def __init__(self, message: str = "Login failed", recoverable: bool = True):
        super().__init__(message, recoverable)


class CaptchaError(VFSBotError):
    """Captcha verification failed."""

    def __init__(self, message: str = "Captcha verification failed", recoverable: bool = True):
        super().__init__(message, recoverable)


class SlotCheckError(VFSBotError):
    """Slot availability check failed."""

    def __init__(self, message: str = "Slot check failed", recoverable: bool = True):
        super().__init__(message, recoverable)


class BookingError(VFSBotError):
    """Appointment booking failed."""

    def __init__(self, message: str = "Booking failed", recoverable: bool = False):
        super().__init__(message, recoverable)


class NetworkError(VFSBotError):
    """Network connection error occurred."""

    def __init__(self, message: str = "Network error occurred", recoverable: bool = True):
        super().__init__(message, recoverable)


class SelectorNotFoundError(VFSBotError):
    """Selector not found - website structure may have changed."""

    def __init__(self, selector_name: str, tried_selectors: Optional[List[str]] = None):
        """
        Initialize selector not found error.

        Args:
            selector_name: Name of the selector that was not found
            tried_selectors: List of selector strings that were tried
        """
        self.selector_name = selector_name
        self.tried_selectors = tried_selectors or []
        message = f"Selector '{selector_name}' not found."
        if self.tried_selectors:
            message += f" Tried: {', '.join(self.tried_selectors)}"
        super().__init__(message, recoverable=False)


class RateLimitError(VFSBotError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", wait_time: Optional[int] = None):
        """
        Initialize rate limit error.

        Args:
            message: Error message
            wait_time: Recommended wait time in seconds
        """
        self.wait_time = wait_time
        if wait_time:
            message += f". Please wait {wait_time} seconds."
        super().__init__(message, recoverable=True)


class ConfigurationError(VFSBotError):
    """Configuration error occurred."""

    def __init__(self, message: str = "Configuration error", recoverable: bool = False):
        super().__init__(message, recoverable)


class AuthenticationError(VFSBotError):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication failed", recoverable: bool = False):
        super().__init__(message, recoverable)


class VFSApiError(VFSBotError):
    """Base class for VFS API-related errors."""

    def __init__(self, message: str = "VFS API error occurred", recoverable: bool = True):
        super().__init__(message, recoverable)


class VFSAuthenticationError(VFSApiError):
    """VFS API authentication error."""

    def __init__(self, message: str = "VFS API authentication failed", recoverable: bool = False):
        super().__init__(message, recoverable)


class VFSRateLimitError(VFSApiError):
    """VFS API rate limit error."""

    def __init__(
        self, message: str = "VFS API rate limit exceeded", wait_time: Optional[int] = None
    ):
        """
        Initialize VFS API rate limit error.

        Args:
            message: Error message
            wait_time: Recommended wait time in seconds
        """
        self.wait_time = wait_time
        if wait_time:
            message += f". Retry after {wait_time} seconds."
        super().__init__(message, recoverable=True)


class VFSSlotNotFoundError(VFSApiError):
    """VFS appointment slot not found."""

    def __init__(self, message: str = "No appointment slots available", recoverable: bool = True):
        super().__init__(message, recoverable)


class VFSSessionExpiredError(VFSApiError):
    """VFS session or token has expired."""

    def __init__(self, message: str = "VFS session expired", recoverable: bool = True):
        super().__init__(message, recoverable)


class ValidationError(VFSBotError):
    """Input validation error."""

    def __init__(self, message: str = "Validation error", field: Optional[str] = None):
        """
        Initialize validation error.

        Args:
            message: Error message
            field: Field name that failed validation
        """
        self.field = field
        if field:
            message = f"Validation error for field '{field}': {message}"
        super().__init__(message, recoverable=False)
