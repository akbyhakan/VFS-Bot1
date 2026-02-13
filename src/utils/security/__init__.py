"""Security utilities."""

import importlib as _importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .header_manager import HeaderManager as HeaderManager
    from .proxy_manager import ProxyManager as ProxyManager
    from .rate_limiter import RateLimiter as RateLimiter
    from .rate_limiter import get_rate_limiter as get_rate_limiter
    from .session_manager import SessionManager as SessionManager

_LAZY_MODULE_MAP = {
    "HeaderManager": ("src.utils.security.header_manager", "HeaderManager"),
    "ProxyManager": ("src.utils.security.proxy_manager", "ProxyManager"),
    "SessionManager": ("src.utils.security.session_manager", "SessionManager"),
    "RateLimiter": ("src.utils.security.rate_limiter", "RateLimiter"),
    "get_rate_limiter": ("src.utils.security.rate_limiter", "get_rate_limiter"),
}

__all__ = list(_LAZY_MODULE_MAP.keys())


def __getattr__(name: str):
    """Lazy import with explicit mapping - importlib based."""
    if name in _LAZY_MODULE_MAP:
        module_path, attr_name = _LAZY_MODULE_MAP[name]
        module = _importlib.import_module(module_path)
        attr = getattr(module, attr_name)
        globals()[name] = attr
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
