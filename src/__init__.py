"""VFS-Bot - Automated VFS appointment booking bot."""

__version__ = "2.0.0"
__author__ = "Md. Ariful Islam"
__license__ = "MIT"

# Lazy imports - modules can be imported when needed
# This prevents circular dependencies and missing optional dependencies

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
    # Utils
    "SelectorManager",
    "get_selector_manager",
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


def __getattr__(name):
    """Lazy import of modules."""
    if name in __all__:
        # Core
        if name in [
            "load_config",
            "ConfigValidator",
            "EnvValidator",
            "setup_structured_logging",
            "JSONFormatter",
        ]:
            from . import core

            return getattr(core, name)
        # Models
        elif name == "Database":
            from .models import database

            return database.Database
        # Services
        elif name in [
            "VFSBot",
            "CaptchaSolver",
            "CaptchaProvider",
            "CentreFetcher",
            "NotificationService",
        ]:
            from . import services

            return getattr(services, name)
        # Utils
        elif name in ["SelectorManager", "get_selector_manager"]:
            from .utils import selectors

            return getattr(selectors, name)
        # Anti-detection
        elif name in [
            "CloudflareHandler",
            "FingerprintBypass",
            "HumanSimulator",
            "StealthConfig",
            "TLSHandler",
        ]:
            from .utils import anti_detection

            return getattr(anti_detection, name)
        # Security
        elif name in [
            "HeaderManager",
            "ProxyManager",
            "SessionManager",
            "RateLimiter",
            "get_rate_limiter",
        ]:
            from .utils import security

            return getattr(security, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
