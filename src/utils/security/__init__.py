"""Security utilities."""

__all__ = [
    "HeaderManager",
    "ProxyManager",
    "SessionManager",
    "RateLimiter",
    "get_rate_limiter",
]


def __getattr__(name):
    """Lazy import of security utilities."""
    if name == "HeaderManager":
        from .header_manager import HeaderManager

        return HeaderManager
    elif name == "ProxyManager":
        from .proxy_manager import ProxyManager

        return ProxyManager
    elif name == "SessionManager":
        from .session_manager import SessionManager

        return SessionManager
    elif name == "RateLimiter":
        from .rate_limiter import RateLimiter

        return RateLimiter
    elif name == "get_rate_limiter":
        from .rate_limiter import get_rate_limiter

        return get_rate_limiter

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
