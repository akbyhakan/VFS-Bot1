"""Custom exception classes for VFS Bot."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class VFSBotError(Exception):
    """Base exception for VFS Bot."""

    def __init__(
        self, message: str, recoverable: bool = True, details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize VFS Bot error.

        Args:
            message: Error message
            recoverable: Whether the error is recoverable with retry
            details: Additional error details
        """
        self.message = message
        self.recoverable = recoverable
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "recoverable": self.recoverable,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class LoginError(VFSBotError):
    """Login operation failed."""

    def __init__(self, message: str = "Login failed", recoverable: bool = True):
        super().__init__(message, recoverable)


class CaptchaError(VFSBotError):
    """Captcha verification failed."""

    def __init__(
        self,
        message: str = "Captcha verification failed",
        recoverable: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, recoverable, details)


class CaptchaTimeoutError(CaptchaError):
    """Captcha solving timed out."""

    def __init__(self, message: str = "Captcha solving timed out", timeout: Optional[int] = None):
        details = {"timeout": timeout} if timeout else {}
        super().__init__(message, recoverable=True, details=details)


class SlotCheckError(VFSBotError):
    """Slot availability check failed."""

    def __init__(self, message: str = "Slot check failed", recoverable: bool = True):
        super().__init__(message, recoverable)


class BookingError(VFSBotError):
    """Appointment booking failed."""

    def __init__(
        self,
        message: str = "Booking failed",
        recoverable: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, recoverable, details)


class SessionError(VFSBotError):
    """Session-related error."""

    def __init__(
        self,
        message: str = "Session error occurred",
        recoverable: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, recoverable, details)


class SessionExpiredError(SessionError):
    """Session has expired."""

    def __init__(self, message: str = "Session has expired"):
        super().__init__(message, recoverable=True)


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

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        wait_time: Optional[int] = None,
        retry_after: Optional[int] = None,
    ):
        """
        Initialize rate limit error.

        Args:
            message: Error message
            wait_time: Recommended wait time in seconds (deprecated, use retry_after)
            retry_after: Recommended wait time in seconds before retry
        """
        # Support both wait_time (old) and retry_after (new)
        self.retry_after = retry_after or wait_time
        self.wait_time = self.retry_after  # Keep for backward compatibility

        if self.retry_after:
            message += f". Please wait {self.retry_after} seconds."
        super().__init__(message, recoverable=True, details={"retry_after": self.retry_after})


class CircuitBreakerOpenError(VFSBotError):
    """Circuit breaker is open."""

    def __init__(
        self, message: str = "Circuit breaker is open", reset_time: Optional[datetime] = None
    ):
        """
        Initialize circuit breaker error.

        Args:
            message: Error message
            reset_time: Time when circuit breaker will reset
        """
        self.reset_time = reset_time
        details = {"reset_time": reset_time.isoformat() if reset_time else None}
        super().__init__(message, recoverable=True, details=details)


# Configuration Errors
class ConfigurationError(VFSBotError):
    """Configuration error occurred."""

    def __init__(
        self,
        message: str = "Configuration error",
        recoverable: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, recoverable, details)


class MissingEnvironmentVariableError(ConfigurationError):
    """Raised when a required environment variable is missing."""

    def __init__(self, variable_name: str):
        super().__init__(
            f"Required environment variable '{variable_name}' is not set",
            recoverable=False,
            details={"variable": variable_name},
        )


# Authentication Errors
class AuthenticationError(VFSBotError):
    """Authentication failed."""

    def __init__(
        self,
        message: str = "Authentication failed",
        recoverable: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, recoverable, details)


class InvalidCredentialsError(AuthenticationError):
    """Raised when credentials are invalid."""

    def __init__(self):
        super().__init__("Invalid username or password", recoverable=False)


class TokenExpiredError(AuthenticationError):
    """Raised when JWT token has expired."""

    def __init__(self):
        super().__init__("Authentication token has expired", recoverable=True)


class InsufficientPermissionsError(AuthenticationError):
    """Raised when user lacks required permissions."""

    def __init__(self, required_permission: str):
        super().__init__(
            f"Insufficient permissions. Required: {required_permission}",
            recoverable=False,
            details={"required_permission": required_permission},
        )


# VFS API Errors
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


class SlotNotAvailableError(VFSSlotNotFoundError):
    """Alias for VFSSlotNotFoundError - No appointment slots available."""

    pass


class VFSSessionExpiredError(VFSApiError):
    """VFS session or token has expired."""

    def __init__(self, message: str = "VFS session expired", recoverable: bool = True):
        super().__init__(message, recoverable)


class CaptchaRequiredError(VFSApiError):
    """Raised when captcha solving is required."""

    def __init__(self, message: str = "Captcha solving is required"):
        super().__init__(message, recoverable=True)


# Validation Errors
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
        super().__init__(message, recoverable=False, details={"field": field} if field else {})


# Database Errors
class DatabaseError(VFSBotError):
    """Base class for database-related errors."""

    def __init__(
        self,
        message: str = "Database error occurred",
        recoverable: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, recoverable, details)


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""

    def __init__(self, message: str = "Failed to connect to database"):
        super().__init__(message, recoverable=True)


class DatabaseNotConnectedError(DatabaseError):
    """Raised when operation attempted without connection."""

    def __init__(self):
        super().__init__(
            "Database connection is not established. Call connect() first.", recoverable=False
        )


class DatabasePoolTimeoutError(DatabaseError):
    """Raised when database connection pool is exhausted and timeout occurs."""

    def __init__(self, timeout: float, pool_size: int):
        super().__init__(
            f"Database connection pool exhausted after {timeout}s (pool size: {pool_size}). "
            "Consider increasing DB_POOL_SIZE or optimizing database queries.",
            recoverable=True,
            details={"timeout": timeout, "pool_size": pool_size},
        )


class RecordNotFoundError(DatabaseError):
    """Raised when a database record is not found."""

    def __init__(self, resource_type: str, resource_id: Any):
        super().__init__(
            f"{resource_type} with id '{resource_id}' not found",
            recoverable=False,
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


# Payment Errors
class PaymentError(VFSBotError):
    """Base class for payment-related errors."""

    def __init__(
        self,
        message: str = "Payment error occurred",
        recoverable: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, recoverable, details)


class PaymentCardNotFoundError(PaymentError):
    """Raised when no payment card is saved."""

    def __init__(self):
        super().__init__("No payment card found. Please save a card first.", recoverable=False)


class PaymentProcessingError(PaymentError):
    """Raised when payment processing fails."""

    def __init__(self, message: str = "Payment processing failed"):
        super().__init__(message, recoverable=True)


class PaymentFailedError(PaymentProcessingError):
    """Alias for PaymentProcessingError - Payment transaction failed."""

    pass


# OTP Errors
class OTPError(VFSBotError):
    """Base class for OTP-related errors."""

    def __init__(
        self,
        message: str = "OTP error occurred",
        recoverable: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, recoverable, details)


class OTPTimeoutError(OTPError):
    """Raised when OTP is not received within timeout."""

    def __init__(self, timeout_seconds: int):
        super().__init__(
            f"OTP not received within {timeout_seconds} seconds",
            recoverable=True,
            details={"timeout_seconds": timeout_seconds},
        )


class OTPInvalidError(OTPError):
    """Raised when OTP verification fails."""

    def __init__(self, message: str = "OTP verification failed"):
        super().__init__(message, recoverable=True)


# Session Security Errors
class SessionBindingError(SessionError):
    """Session binding validation failed."""

    def __init__(
        self,
        message: str = "Session binding validation failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, recoverable=False, details=details)


# Shutdown Errors
class ShutdownTimeoutError(VFSBotError):
    """Graceful shutdown timed out."""

    def __init__(self, message: str = "Graceful shutdown timed out", timeout: Optional[int] = None):
        """
        Initialize shutdown timeout error.

        Args:
            message: Error message
            timeout: Timeout value in seconds
        """
        self.timeout = timeout
        details = {"timeout": timeout} if timeout else {}
        super().__init__(message, recoverable=False, details=details)


# Batch Operation Errors
class BatchOperationError(DatabaseError):
    """Batch database operation failed."""

    def __init__(
        self,
        message: str = "Batch operation failed",
        operation: Optional[str] = None,
        failed_count: Optional[int] = None,
        total_count: Optional[int] = None,
    ):
        """
        Initialize batch operation error.

        Args:
            message: Error message
            operation: Name of the batch operation
            failed_count: Number of items that failed
            total_count: Total number of items in batch
        """
        self.operation = operation
        self.failed_count = failed_count
        self.total_count = total_count

        details: Dict[str, Any] = {}
        if operation:
            details["operation"] = operation
        if failed_count is not None:
            details["failed_count"] = failed_count
        if total_count is not None:
            details["total_count"] = total_count
            if failed_count is not None:
                details["success_count"] = total_count - failed_count
            else:
                details["success_count"] = total_count

        super().__init__(message, recoverable=False, details=details)
