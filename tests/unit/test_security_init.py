"""Tests for security module initialization and lazy loading."""


import pytest



def test_security_module_all_exports():
    """Test that __all__ contains expected exports."""
    from src.utils.security import __all__

    assert "HeaderManager" in __all__
    assert "ProxyManager" in __all__
    assert "SessionManager" in __all__
    assert "RateLimiter" in __all__
    assert "get_rate_limiter" in __all__


def test_lazy_import_header_manager():
    """Test lazy import of HeaderManager."""
    from src.utils import security

    HeaderManager = security.HeaderManager
    assert HeaderManager is not None
    assert HeaderManager.__name__ == "HeaderManager"


def test_lazy_import_proxy_manager():
    """Test lazy import of ProxyManager."""
    from src.utils import security

    ProxyManager = security.ProxyManager
    assert ProxyManager is not None
    assert ProxyManager.__name__ == "ProxyManager"


def test_lazy_import_session_manager():
    """Test lazy import of SessionManager."""
    from src.utils import security

    SessionManager = security.SessionManager
    assert SessionManager is not None
    assert SessionManager.__name__ == "SessionManager"


def test_lazy_import_rate_limiter():
    """Test lazy import of RateLimiter."""
    from src.utils import security

    RateLimiter = security.RateLimiter
    assert RateLimiter is not None
    assert RateLimiter.__name__ == "RateLimiter"


def test_lazy_import_get_rate_limiter():
    """Test lazy import of get_rate_limiter function."""
    from src.utils import security

    get_rate_limiter = security.get_rate_limiter
    assert get_rate_limiter is not None
    assert callable(get_rate_limiter)


def test_invalid_attribute_raises_error():
    """Test that accessing invalid attribute raises AttributeError."""
    from src.utils import security

    with pytest.raises(AttributeError) as exc_info:
        _ = security.InvalidAttribute

    assert "has no attribute 'InvalidAttribute'" in str(exc_info.value)


def test_multiple_imports_same_class():
    """Test that multiple imports return the same class."""
    from src.utils import security

    HeaderManager1 = security.HeaderManager
    HeaderManager2 = security.HeaderManager
    assert HeaderManager1 is HeaderManager2


def test_can_instantiate_header_manager():
    """Test that HeaderManager can be instantiated."""
    from src.utils.security import HeaderManager

    manager = HeaderManager()
    assert manager is not None


def test_can_instantiate_proxy_manager():
    """Test that ProxyManager can be instantiated."""
    from src.utils.security import ProxyManager

    manager = ProxyManager()
    assert manager is not None


def test_can_instantiate_rate_limiter():
    """Test that RateLimiter can be instantiated."""
    from src.utils.security import RateLimiter

    limiter = RateLimiter(max_requests=10, time_window=60)
    assert limiter is not None


def test_get_rate_limiter_returns_instance():
    """Test that get_rate_limiter returns a RateLimiter instance."""
    from src.utils.security import get_rate_limiter

    limiter = get_rate_limiter()
    assert limiter is not None


def test_get_rate_limiter_singleton():
    """Test that get_rate_limiter returns same instance."""
    from src.utils.security import get_rate_limiter

    limiter1 = get_rate_limiter()
    limiter2 = get_rate_limiter()
    assert limiter1 is limiter2


def test_direct_import_header_manager():
    """Test direct import from header_manager module."""
    from src.utils.security.header_manager import HeaderManager

    assert HeaderManager is not None
    manager = HeaderManager()
    assert hasattr(manager, "get_headers")


def test_direct_import_proxy_manager():
    """Test direct import from proxy_manager module."""
    from src.utils.security.proxy_manager import ProxyManager

    assert ProxyManager is not None
    manager = ProxyManager()
    assert hasattr(manager, "proxies")


def test_direct_import_session_manager():
    """Test direct import from session_manager module."""
    from src.utils.security.session_manager import SessionManager

    assert SessionManager is not None
    manager = SessionManager()
    assert hasattr(manager, "access_token")


def test_direct_import_rate_limiter():
    """Test direct import from rate_limiter module."""
    from src.utils.security.rate_limiter import RateLimiter

    assert RateLimiter is not None
    limiter = RateLimiter(max_requests=10, time_window=60)
    assert hasattr(limiter, "acquire")
