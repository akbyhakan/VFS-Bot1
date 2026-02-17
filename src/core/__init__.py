"""Core infrastructure module."""

from .auth import create_access_token, hash_password, verify_password, verify_token
from .bot_controller import BotController
from .config.config_loader import load_config
from .config.config_validator import ConfigValidator
from .config.config_version_checker import CURRENT_CONFIG_VERSION, check_config_version
from .config.env_validator import EnvValidator
from .exceptions import (
    # Base exception
    VFSBotError,
    # Login & Booking
    LoginError,
    BookingError,
    # Captcha
    CaptchaError,
    CaptchaTimeoutError,
    # Slot checking
    SlotCheckError,
    # Session
    SessionError,
    SessionExpiredError,
    SessionBindingError,
    # Network
    NetworkError,
    # Selector
    SelectorNotFoundError,
    # Rate limiting
    RateLimitError,
    # Circuit breaker
    CircuitBreakerOpenError,
    # Configuration
    ConfigurationError,
    MissingEnvironmentVariableError,
    # Authentication
    AuthenticationError,
    InvalidCredentialsError,
    TokenExpiredError,
    InsufficientPermissionsError,
    # VFS API
    VFSApiError,
    VFSAuthenticationError,
    VFSRateLimitError,
    VFSSlotNotFoundError,
    VFSSessionExpiredError,
    CaptchaRequiredError,
    BannedError,
    # Validation
    ValidationError,
    # Database
    DatabaseError,
    DatabaseConnectionError,
    DatabaseNotConnectedError,
    DatabasePoolTimeoutError,
    RecordNotFoundError,
    # Payment
    PaymentError,
    PaymentCardNotFoundError,
    PaymentProcessingError,
    PaymentFailedError,
    # OTP
    OTPError,
    OTPTimeoutError,
    OTPInvalidError,
    # Shutdown
    ShutdownTimeoutError,
    # Batch operations
    BatchOperationError,
)
from .infra.retry import (
    get_captcha_retry,
    get_login_retry,
    get_network_retry,
    get_rate_limit_retry,
    get_slot_check_retry,
)
from .infra.shutdown import (
    SHUTDOWN_TIMEOUT,
    fast_emergency_cleanup,
    get_shutdown_event,
    graceful_shutdown,
    graceful_shutdown_with_timeout,
    safe_shutdown_cleanup,
    set_shutdown_event,
    setup_signal_handlers,
)
from .infra.startup import validate_environment, verify_critical_dependencies
from .logger import setup_structured_logging
from .security import APIKeyManager, generate_api_key, verify_api_key

__all__ = [
    "load_config",
    "ConfigValidator",
    "EnvValidator",
    "BotController",
    "setup_structured_logging",
    "APIKeyManager",
    "generate_api_key",
    "verify_api_key",
    "create_access_token",
    "verify_token",
    "hash_password",
    "verify_password",
    # Exceptions
    "VFSBotError",
    "LoginError",
    "BookingError",
    "CaptchaError",
    "CaptchaTimeoutError",
    "SlotCheckError",
    "SessionError",
    "SessionExpiredError",
    "SessionBindingError",
    "NetworkError",
    "SelectorNotFoundError",
    "RateLimitError",
    "CircuitBreakerOpenError",
    "ConfigurationError",
    "MissingEnvironmentVariableError",
    "AuthenticationError",
    "InvalidCredentialsError",
    "TokenExpiredError",
    "InsufficientPermissionsError",
    "VFSApiError",
    "VFSAuthenticationError",
    "VFSRateLimitError",
    "VFSSlotNotFoundError",
    "VFSSessionExpiredError",
    "CaptchaRequiredError",
    "BannedError",
    "ValidationError",
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabaseNotConnectedError",
    "DatabasePoolTimeoutError",
    "RecordNotFoundError",
    "PaymentError",
    "PaymentCardNotFoundError",
    "PaymentProcessingError",
    "PaymentFailedError",
    "OTPError",
    "OTPTimeoutError",
    "OTPInvalidError",
    "ShutdownTimeoutError",
    "BatchOperationError",
    # Retry strategies
    "get_login_retry",
    "get_captcha_retry",
    "get_slot_check_retry",
    "get_network_retry",
    "get_rate_limit_retry",
    # Environment & startup
    "validate_environment",
    "verify_critical_dependencies",
    # Shutdown
    "SHUTDOWN_TIMEOUT",
    "get_shutdown_event",
    "set_shutdown_event",
    "setup_signal_handlers",
    "graceful_shutdown",
    "graceful_shutdown_with_timeout",
    "safe_shutdown_cleanup",
    "fast_emergency_cleanup",
    # Config
    "check_config_version",
    "CURRENT_CONFIG_VERSION",
]
