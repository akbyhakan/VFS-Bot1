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
    """Login işlemi başarısız."""

    def __init__(self, message: str = "Login failed", recoverable: bool = True):
        super().__init__(message, recoverable)


class CaptchaError(VFSBotError):
    """Captcha çözülemedi."""

    def __init__(self, message: str = "Captcha verification failed", recoverable: bool = True):
        super().__init__(message, recoverable)


class SlotCheckError(VFSBotError):
    """Slot kontrolü başarısız."""

    def __init__(self, message: str = "Slot check failed", recoverable: bool = True):
        super().__init__(message, recoverable)


class BookingError(VFSBotError):
    """Randevu rezervasyonu başarısız."""

    def __init__(self, message: str = "Booking failed", recoverable: bool = False):
        super().__init__(message, recoverable)


class NetworkError(VFSBotError):
    """Ağ bağlantısı hatası."""

    def __init__(self, message: str = "Network error occurred", recoverable: bool = True):
        super().__init__(message, recoverable)


class SelectorNotFoundError(VFSBotError):
    """Selector bulunamadı - site yapısı değişmiş olabilir."""

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
    """Rate limit aşıldı."""

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
    """Konfigürasyon hatası."""

    def __init__(self, message: str = "Configuration error", recoverable: bool = False):
        super().__init__(message, recoverable)


class AuthenticationError(VFSBotError):
    """Kimlik doğrulama hatası."""

    def __init__(self, message: str = "Authentication failed", recoverable: bool = False):
        super().__init__(message, recoverable)
