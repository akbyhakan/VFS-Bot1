"""Tests for security module lazy imports."""

import pytest
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSecurityLazyImports:
    """Test security module lazy import functionality."""

    def test_import_header_manager(self):
        """Test lazy import of HeaderManager."""
        from src.utils.security import HeaderManager

        assert HeaderManager is not None
        assert HeaderManager.__name__ == "HeaderManager"

    def test_import_proxy_manager(self):
        """Test lazy import of ProxyManager."""
        from src.utils.security import ProxyManager

        assert ProxyManager is not None
        assert ProxyManager.__name__ == "ProxyManager"

    def test_import_session_manager(self):
        """Test lazy import of SessionManager."""
        from src.utils.security import SessionManager

        assert SessionManager is not None
        assert SessionManager.__name__ == "SessionManager"

    def test_import_rate_limiter(self):
        """Test lazy import of RateLimiter."""
        from src.utils.security import RateLimiter

        assert RateLimiter is not None
        assert RateLimiter.__name__ == "RateLimiter"

    def test_import_get_rate_limiter(self):
        """Test lazy import of get_rate_limiter."""
        from src.utils.security import get_rate_limiter

        assert get_rate_limiter is not None
        assert callable(get_rate_limiter)

    def test_import_invalid_attribute(self):
        """Test importing invalid attribute raises AttributeError."""
        import src.utils.security

        with pytest.raises(AttributeError, match="has no attribute"):
            _ = src.utils.security.InvalidAttribute

    def test_all_exports(self):
        """Test __all__ exports are correct."""
        from src.utils.security import __all__

        expected = [
            "HeaderManager",
            "ProxyManager",
            "SessionManager",
            "RateLimiter",
            "get_rate_limiter",
        ]
        assert set(__all__) == set(expected)

    def test_header_manager_instantiation(self):
        """Test HeaderManager can be instantiated after import."""
        from src.utils.security import HeaderManager

        hm = HeaderManager()
        assert hm is not None

    def test_proxy_manager_instantiation(self):
        """Test ProxyManager can be instantiated after import."""
        from src.utils.security import ProxyManager

        pm = ProxyManager()
        assert pm is not None

    def test_session_manager_instantiation(self):
        """Test SessionManager can be instantiated after import."""
        from src.utils.security import SessionManager

        sm = SessionManager()
        assert sm is not None

    def test_rate_limiter_instantiation(self):
        """Test RateLimiter can be instantiated after import."""
        from src.utils.security import RateLimiter

        rl = RateLimiter()
        assert rl is not None

    def test_get_rate_limiter_function(self):
        """Test get_rate_limiter function works."""
        from src.utils.security import get_rate_limiter

        limiter = get_rate_limiter()
        assert limiter is not None
