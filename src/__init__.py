"""VFS-Bot - Automated VFS appointment booking bot."""

# Import for backward compatibility
from .core.config_loader import load_config
from .core.config_validator import ConfigValidator
from .core.env_validator import EnvValidator
from .core.logger import setup_structured_logging, JSONFormatter

from .models.database import Database

from .services.bot_service import VFSBot
from .services.captcha_solver import CaptchaSolver, CaptchaProvider
from .services.centre_fetcher import CentreFetcher
from .services.notification import NotificationService

from .utils.anti_detection import (
    CloudflareHandler,
    FingerprintBypass,
    HumanSimulator,
    StealthConfig,
    TLSHandler,
)

from .utils.security import (
    HeaderManager,
    ProxyManager,
    SessionManager,
    RateLimiter,
    get_rate_limiter,
)

__version__ = "2.0.0"
__author__ = "Md. Ariful Islam"
__license__ = "MIT"

__all__ = [
    # Core
    "load_config",
    "ConfigValidator",
    "EnvValidator",
    "setup_structured_logging",
    "JSONFormatter",
    # Models
    "Database",
    # Services
    "VFSBot",
    "CaptchaSolver",
    "CaptchaProvider",
    "CentreFetcher",
    "NotificationService",
    # Anti-detection
    "CloudflareHandler",
    "FingerprintBypass",
    "HumanSimulator",
    "StealthConfig",
    "TLSHandler",
    # Security
    "HeaderManager",
    "ProxyManager",
    "SessionManager",
    "RateLimiter",
    "get_rate_limiter",
]

