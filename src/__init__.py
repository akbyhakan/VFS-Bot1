"""VFS-Bot - Automated VFS appointment booking bot."""

import importlib as _importlib
from typing import TYPE_CHECKING, Any

# Application version (SemVer) - tracks code/feature changes.
# NOTE: Configuration schema version (CURRENT_CONFIG_VERSION) is maintained
# separately in src/core/config/config_version_checker.py and is intentionally
# independent. It only changes when config.yaml schema has breaking changes.
__version__ = "2.2.0"
__author__ = "Md. Ariful Islam"
__license__ = "MIT"

if TYPE_CHECKING:
    from .core.config.config_loader import load_config as load_config
    from .core.config.config_validator import ConfigValidator as ConfigValidator
    from .core.config.env_validator import EnvValidator as EnvValidator
    from .core.logger import setup_structured_logging as setup_structured_logging
    from .models.database import Database as Database
    from .selector import SelectorManager as SelectorManager
    from .selector import get_selector_manager as get_selector_manager
    from .services.bot.vfs_bot import VFSBot as VFSBot
    from .services.captcha_solver import CaptchaSolver as CaptchaSolver
    from .services.data_sync.centre_fetcher import CentreFetcher as CentreFetcher
    from .services.notification.notification import NotificationService as NotificationService
    from .utils.anti_detection import CloudflareHandler as CloudflareHandler
    from .utils.anti_detection import FingerprintBypass as FingerprintBypass
    from .utils.anti_detection import HumanSimulator as HumanSimulator
    from .utils.anti_detection import StealthConfig as StealthConfig
    from .utils.anti_detection import TLSHandler as TLSHandler
    from .utils.security import HeaderManager as HeaderManager
    from .utils.security import ProxyManager as ProxyManager
    from .utils.security import RateLimiter as RateLimiter
    from .utils.security import SessionManager as SessionManager
    from .utils.security import get_rate_limiter as get_rate_limiter

# Explicit lazy-loading map: name -> (module_path, attribute_name)
_LAZY_MODULE_MAP = {
    # Core
    "load_config": ("src.core.config.config_loader", "load_config"),
    "ConfigValidator": ("src.core.config.config_validator", "ConfigValidator"),
    "EnvValidator": ("src.core.config.env_validator", "EnvValidator"),
    "setup_structured_logging": ("src.core.logger", "setup_structured_logging"),
    # Models
    "Database": ("src.models.database", "Database"),
    # Services
    "VFSBot": ("src.services.bot.vfs_bot", "VFSBot"),
    "CaptchaSolver": ("src.services.captcha_solver", "CaptchaSolver"),
    "CentreFetcher": ("src.services.data_sync.centre_fetcher", "CentreFetcher"),
    "NotificationService": ("src.services.notification.notification", "NotificationService"),
    # Utils
    "SelectorManager": ("src.selector", "SelectorManager"),
    "get_selector_manager": ("src.selector", "get_selector_manager"),
    # Anti-detection
    "CloudflareHandler": ("src.utils.anti_detection", "CloudflareHandler"),
    "FingerprintBypass": ("src.utils.anti_detection", "FingerprintBypass"),
    "HumanSimulator": ("src.utils.anti_detection", "HumanSimulator"),
    "StealthConfig": ("src.utils.anti_detection", "StealthConfig"),
    "TLSHandler": ("src.utils.anti_detection", "TLSHandler"),
    # Security
    "HeaderManager": ("src.utils.security", "HeaderManager"),
    "ProxyManager": ("src.utils.security", "ProxyManager"),
    "SessionManager": ("src.utils.security", "SessionManager"),
    "RateLimiter": ("src.utils.security", "RateLimiter"),
    "get_rate_limiter": ("src.utils.security", "get_rate_limiter"),
}

# Auto-derive __all__ from _LAZY_MODULE_MAP to prevent manual sync issues
__all__ = list(_LAZY_MODULE_MAP.keys())


def __getattr__(name: str) -> Any:
    """Lazy import with explicit mapping - importlib based."""
    if name in _LAZY_MODULE_MAP:
        module_path, attr_name = _LAZY_MODULE_MAP[name]
        module = _importlib.import_module(module_path)
        attr = getattr(module, attr_name)
        # Cache in module globals to avoid repeated imports
        globals()[name] = attr
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
