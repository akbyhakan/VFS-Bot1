"""Security utilities."""

import importlib as _importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.rate_limiting import RateLimiter as RateLimiter
    from src.core.rate_limiting import get_rate_limiter as get_rate_limiter

    from .header_manager import HeaderManager as HeaderManager
    from .proxy_manager import ProxyManager as ProxyManager
    from .session_manager import SessionManager as SessionManager

_LAZY_MODULE_MAP = {
    "HeaderManager": ("src.utils.security.header_manager", "HeaderManager"),
    "ProxyManager": ("src.utils.security.proxy_manager", "ProxyManager"),
    "SessionManager": ("src.utils.security.session_manager", "SessionManager"),
    "RateLimiter": ("src.core.rate_limiting", "RateLimiter"),
    "get_rate_limiter": ("src.core.rate_limiting", "get_rate_limiter"),
}

__all__ = list(_LAZY_MODULE_MAP.keys())


def __getattr__(name: str) -> Any:
    """Lazy import with explicit mapping - importlib based."""
    if name in _LAZY_MODULE_MAP:
        module_path, attr_name = _LAZY_MODULE_MAP[name]
        module = _importlib.import_module(module_path)
        attr = getattr(module, attr_name)
        globals()[name] = attr
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
