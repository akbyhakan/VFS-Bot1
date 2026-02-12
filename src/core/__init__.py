"""Core infrastructure module."""

from .auth import create_access_token, hash_password, verify_password, verify_token
from .bot_controller import BotController
from .config.config_loader import load_config
from .config.config_validator import ConfigValidator
from .config.config_version_checker import CURRENT_CONFIG_VERSION, check_config_version
from .config.env_validator import EnvValidator
from .exceptions import (
    AuthenticationError,
    BookingError,
    CaptchaError,
    ConfigurationError,
    LoginError,
    NetworkError,
    RateLimitError,
    SelectorNotFoundError,
    SlotCheckError,
    VFSBotError,
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
from .logger import JSONFormatter, setup_structured_logging
from .security import APIKeyManager, generate_api_key, verify_api_key

__all__ = [
    "load_config",
    "ConfigValidator",
    "EnvValidator",
    "BotController",
    "setup_structured_logging",
    "JSONFormatter",
    "APIKeyManager",
    "generate_api_key",
    "verify_api_key",
    "create_access_token",
    "verify_token",
    "hash_password",
    "verify_password",
    "VFSBotError",
    "LoginError",
    "CaptchaError",
    "SlotCheckError",
    "BookingError",
    "NetworkError",
    "SelectorNotFoundError",
    "RateLimitError",
    "ConfigurationError",
    "AuthenticationError",
    "get_login_retry",
    "get_captcha_retry",
    "get_slot_check_retry",
    "get_network_retry",
    "get_rate_limit_retry",
    "validate_environment",
    "verify_critical_dependencies",
    "SHUTDOWN_TIMEOUT",
    "get_shutdown_event",
    "set_shutdown_event",
    "setup_signal_handlers",
    "graceful_shutdown",
    "graceful_shutdown_with_timeout",
    "safe_shutdown_cleanup",
    "fast_emergency_cleanup",
    "check_config_version",
    "CURRENT_CONFIG_VERSION",
]
