"""Tests for security module __init__.py lazy imports."""

import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSecurityInit:
    """Test security module lazy imports."""

    def test_import_header_manager(self):
        """Test HeaderManager lazy import."""
        from src.utils.security import HeaderManager

        assert HeaderManager is not None
        # Verify it's the right class
        assert HeaderManager.__name__ == "HeaderManager"

    def test_import_proxy_manager(self):
        """Test ProxyManager lazy import."""
        from src.utils.security import ProxyManager

        assert ProxyManager is not None
        assert ProxyManager.__name__ == "ProxyManager"

    def test_import_session_manager(self):
        """Test SessionManager lazy import."""
        from src.utils.security import SessionManager

        assert SessionManager is not None
        assert SessionManager.__name__ == "SessionManager"

    def test_import_rate_limiter(self):
        """Test RateLimiter lazy import."""
        from src.utils.security import RateLimiter

        assert RateLimiter is not None
        assert RateLimiter.__name__ == "RateLimiter"

    def test_import_get_rate_limiter(self):
        """Test get_rate_limiter function lazy import."""
        from src.utils.security import get_rate_limiter

        assert get_rate_limiter is not None
        assert callable(get_rate_limiter)

    def test_invalid_attribute(self):
        """Test that invalid attribute raises AttributeError."""
        import src.utils.security as security

        with pytest.raises(AttributeError) as exc_info:
            _ = security.NonExistentClass

        assert "has no attribute 'NonExistentClass'" in str(exc_info.value)

    def test_all_exports(self):
        """Test __all__ exports are defined."""
        from src.utils.security import __all__

        assert "__all__" is not None
        assert "HeaderManager" in __all__
        assert "ProxyManager" in __all__
        assert "SessionManager" in __all__
        assert "RateLimiter" in __all__
        assert "get_rate_limiter" in __all__

    def test_multiple_imports(self):
        """Test that multiple imports return the same class."""
        from src.utils.security import HeaderManager as HM1
        from src.utils.security import HeaderManager as HM2

        assert HM1 is HM2

    def test_can_instantiate_classes(self):
        """Test that imported classes can be instantiated."""
        from src.utils.security import HeaderManager, ProxyManager, SessionManager

        # Test instantiation
        header_mgr = HeaderManager()
        assert header_mgr is not None

        proxy_mgr = ProxyManager()
        assert proxy_mgr is not None

        # Use temporary file for session manager
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            session_mgr = SessionManager(session_file=f.name)
            assert session_mgr is not None

    def test_getattr_called_for_lazy_loading(self):
        """Test that __getattr__ is used for lazy loading."""
        # Import the module to reset its state
        import importlib

        import src.utils.security as security

        importlib.reload(security)

        # Access attribute to trigger lazy load
        hm = security.HeaderManager
        assert hm is not None

        # Second access should use cached import
        hm2 = security.HeaderManager
        assert hm is hm2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
