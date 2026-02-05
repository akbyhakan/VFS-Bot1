"""Tests for anti-detection functionality."""

import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.anti_detection.human_simulator import HumanSimulator
from src.utils.security.header_manager import HeaderManager
from src.utils.security.proxy_manager import ProxyManager
from src.utils.security.session_manager import SessionManager


class TestBezierCurve:
    """Test Bézier curve generation."""

    def test_bezier_curve_points(self):
        """Test that Bézier curve generates correct number of points."""
        start = (0, 0)
        end = (100, 100)
        steps = 20

        points = HumanSimulator.bezier_curve(start, end, steps)

        assert len(points) == steps
        assert points[0] == start or (
            abs(points[0][0] - start[0]) < 0.1 and abs(points[0][1] - start[1]) < 0.1
        )
        assert points[-1] == end or (
            abs(points[-1][0] - end[0]) < 0.1 and abs(points[-1][1] - end[1]) < 0.1
        )

    def test_bezier_curve_start_end(self):
        """Verify Bézier curve starts and ends at correct points."""
        start = (50, 75)
        end = (200, 150)

        points = HumanSimulator.bezier_curve(start, end, 30)

        # First point should be close to start
        assert abs(points[0][0] - start[0]) < 1
        assert abs(points[0][1] - start[1]) < 1

        # Last point should be close to end
        assert abs(points[-1][0] - end[0]) < 1
        assert abs(points[-1][1] - end[1]) < 1


class TestHeaderManager:
    """Test header manager functionality."""

    @staticmethod
    def _get_chrome_ua(manager: HeaderManager):
        """Helper method to get a Chrome-based user agent."""
        chrome_uas = [ua for ua in manager.USER_AGENTS if ua.get("sec_ch_ua") is not None]
        assert chrome_uas, "No Chrome-based user agents found in USER_AGENTS"
        return chrome_uas[0]

    def test_user_agent_consistency(self):
        """Test that User-Agent and Sec-CH-UA headers are consistent."""
        manager = HeaderManager()

        # Force a Chrome-based UA for consistent testing
        # (Firefox/Safari don't support Sec-CH-UA headers)
        manager.current_ua = self._get_chrome_ua(manager)

        headers = manager.get_headers()

        # Check required headers exist
        assert "User-Agent" in headers
        assert "Sec-CH-UA" in headers
        assert "Sec-CH-UA-Platform" in headers
        assert "Sec-CH-UA-Mobile" in headers

        # Verify values are not empty
        assert len(headers["User-Agent"]) > 0
        assert len(headers["Sec-CH-UA"]) > 0

    def test_header_rotation(self):
        """Test User-Agent rotation."""
        manager = HeaderManager()

        # Force a Chrome-based UA for consistent testing
        # (Firefox/Safari don't support Sec-CH-UA headers)
        manager.current_ua = self._get_chrome_ua(manager)

        _ = manager.get_user_agent()
        _ = manager.get_sec_ch_ua()

        # Rotate (may or may not change if only one UA)
        manager.rotate_user_agent()

        new_ua = manager.get_user_agent()
        new_sec_ch = manager.get_sec_ch_ua()

        # Check that UA is still valid
        assert len(new_ua) > 0
        # sec_ch_ua might be None for Firefox/Safari after rotation
        assert new_sec_ch is None or len(new_sec_ch) > 0

    def test_api_headers(self):
        """Test API header generation."""
        manager = HeaderManager()

        token = "test_token_123"
        headers = manager.get_api_headers(token=token)

        assert "Authorization" in headers
        assert headers["Authorization"] == f"Bearer {token}"
        assert headers["Content-Type"] == "application/json"

    def test_referer_header(self):
        """Test referer header addition."""
        manager = HeaderManager()

        referer = "https://example.com/page1"
        headers = manager.get_headers(referer=referer)

        assert "Referer" in headers
        assert headers["Referer"] == referer


class TestSessionManager:
    """Test session manager functionality."""

    def setup_method(self):
        """Setup test session file."""
        import tempfile

        # Use temporary file for testing
        fd, self.test_session_file = tempfile.mkstemp(suffix=".json")
        import os

        os.close(fd)  # Close the file descriptor
        self.manager = SessionManager(session_file=self.test_session_file)

    def teardown_method(self):
        """Clean up test session file."""
        import os

        session_path = Path(self.test_session_file)
        if session_path.exists():
            os.unlink(self.test_session_file)

    def test_set_tokens(self):
        """Test token setting."""
        access_token = "test_access_token"
        refresh_token = "test_refresh_token"

        self.manager.set_tokens(access_token, refresh_token)

        assert self.manager.access_token == access_token
        assert self.manager.refresh_token == refresh_token

    def test_auth_header(self):
        """Test auth header generation."""
        access_token = "test_token"
        self.manager.set_tokens(access_token)

        header = self.manager.get_auth_header()

        assert "Authorization" in header
        assert header["Authorization"] == f"Bearer {access_token}"

    def test_clear_session(self):
        """Test session clearing."""
        self.manager.set_tokens("token1", "token2")
        assert self.manager.access_token is not None

        self.manager.clear_session()

        assert self.manager.access_token is None
        assert self.manager.refresh_token is None
        assert self.manager.token_expiry is None

    def test_save_and_load_session(self):
        """Test session persistence."""
        access_token = "test_access"
        refresh_token = "test_refresh"

        self.manager.set_tokens(access_token, refresh_token)
        self.manager.save_session()

        # Create new manager and load
        new_manager = SessionManager(session_file=self.test_session_file)
        new_manager.load_session()

        assert new_manager.access_token == access_token
        assert new_manager.refresh_token == refresh_token


class TestProxyManager:
    """Test proxy manager functionality."""

    def test_proxy_parsing_simple(self):
        """Test simple proxy parsing (host:port)."""
        manager = ProxyManager()

        proxy = manager._parse_proxy("192.168.1.1:8080")

        assert proxy is not None
        assert proxy["host"] == "192.168.1.1"
        assert proxy["port"] == 8080
        assert proxy["protocol"] == "http"

    def test_proxy_parsing_with_auth(self):
        """Test proxy parsing with authentication."""
        manager = ProxyManager()

        proxy = manager._parse_proxy("user:pass@proxy.example.com:8080")

        assert proxy is not None
        assert proxy["host"] == "proxy.example.com"
        assert proxy["port"] == 8080
        assert proxy["username"] == "user"
        assert proxy["password"] == "pass"

    def test_proxy_parsing_with_protocol(self):
        """Test proxy parsing with protocol."""
        manager = ProxyManager()

        proxy = manager._parse_proxy("http://192.168.1.1:8080")

        assert proxy is not None
        assert proxy["protocol"] == "http"
        assert proxy["server"] == "http://192.168.1.1:8080"

    def test_proxy_parsing_socks5(self):
        """Test SOCKS5 proxy parsing."""
        manager = ProxyManager()

        proxy = manager._parse_proxy("socks5://proxy.example.com:1080")

        assert proxy is not None
        assert proxy["protocol"] == "socks5"
        assert proxy["port"] == 1080

    def test_playwright_proxy_format(self):
        """Test Playwright proxy format conversion."""
        # Create manager with enabled=True for testing
        config = {"enabled": True}
        manager = ProxyManager(config)

        proxy = manager._parse_proxy("user:pass@192.168.1.1:8080")

        # Manually add proxy to list since we're not loading from file
        manager.proxies = [proxy]

        playwright_proxy = manager.get_playwright_proxy(proxy)

        assert playwright_proxy is not None
        assert "server" in playwright_proxy
        assert "username" in playwright_proxy
        assert "password" in playwright_proxy

    def test_mark_proxy_failed(self):
        """Test marking proxy as failed."""
        manager = ProxyManager()

        proxy = manager._parse_proxy("192.168.1.1:8080")
        manager.mark_proxy_failed(proxy)

        assert proxy["server"] in manager.failed_proxies

    def test_disabled_proxy_manager(self):
        """Test proxy manager when disabled."""
        config = {"enabled": False}
        manager = ProxyManager(config)

        assert manager.get_random_proxy() is None
        assert manager.get_playwright_proxy() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
