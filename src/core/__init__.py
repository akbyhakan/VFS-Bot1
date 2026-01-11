"""Core infrastructure module."""

from .config_loader import load_config
from .config_validator import ConfigValidator
from .env_validator import EnvValidator
from .logger import setup_structured_logging, JSONFormatter
from .security import generate_api_key, hash_api_key, verify_api_key
from .auth import create_access_token, verify_token, hash_password, verify_password
from .exceptions import (
    VFSBotError,
    LoginError,
    CaptchaError,
    SlotCheckError,
    BookingError,
    NetworkError,
    SelectorNotFoundError,
    RateLimitError,
    ConfigurationError,
    AuthenticationError,
)
from .retry import (
    get_login_retry,
    get_captcha_retry,
    get_slot_check_retry,
    get_network_retry,
    get_rate_limit_retry,
)

__all__ = [
    "load_config",
    "ConfigValidator",
    "EnvValidator",
    "setup_structured_logging",
    "JSONFormatter",
    "generate_api_key",
    "hash_api_key",
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
]
