"""Extended tests for proxy manager functionality."""

import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.security.proxy_manager import ProxyManager


class TestProxyManagerExtended:
    """Extended tests for proxy manager functionality."""

    def test_init_disabled(self):
        """Test ProxyManager initialization when disabled."""
        config = {"enabled": False}
        manager = ProxyManager(config)

        assert manager.enabled is False
        assert manager.proxies == []
        assert manager.failed_proxies == []

    def test_init_enabled_no_file(self):
        """Test ProxyManager initialization when enabled but file doesn't exist."""
        config = {"enabled": True, "file": "/nonexistent/proxies.txt"}
        manager = ProxyManager(config)

        assert manager.enabled is True
        assert manager.proxies == []

    def test_load_proxies_from_file(self):
        """Test loading proxies from a file."""
        # Create temporary proxy file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("192.168.1.1:8080\n")
            f.write("proxy.example.com:3128\n")
            f.write("# Comment line\n")
            f.write("\n")
            f.write("user:pass@proxy2.example.com:8080\n")
            proxy_file = f.name

        try:
            config = {"enabled": True, "file": proxy_file}
            manager = ProxyManager(config)

            assert len(manager.proxies) == 3
        finally:
            Path(proxy_file).unlink()

    def test_parse_proxy_with_protocol_variations(self):
        """Test proxy parsing with various protocol formats."""
        manager = ProxyManager()

        # HTTP proxy
        proxy = manager._parse_proxy("http://proxy.example.com:8080")
        assert proxy is not None
        assert proxy["protocol"] == "http"
        assert proxy["server"] == "http://proxy.example.com:8080"

        # SOCKS5 proxy
        proxy = manager._parse_proxy("socks5://proxy.example.com:1080")
        assert proxy is not None
        assert proxy["protocol"] == "socks5"

        # No protocol (defaults to HTTP)
        proxy = manager._parse_proxy("proxy.example.com:8080")
        assert proxy is not None
        assert proxy["protocol"] == "http"

    def test_parse_proxy_with_full_auth(self):
        """Test proxy parsing with username and password."""
        manager = ProxyManager()

        proxy = manager._parse_proxy("http://myuser:mypassword@proxy.example.com:8080")

        assert proxy is not None
        assert proxy["username"] == "myuser"
        assert proxy["password"] == "mypassword"
        assert proxy["host"] == "proxy.example.com"
        assert proxy["port"] == 8080

    def test_parse_proxy_default_ports(self):
        """Test proxy parsing uses default ports when not specified."""
        manager = ProxyManager()

        # HTTP default port
        proxy = manager._parse_proxy("http://proxy.example.com")
        assert proxy is not None
        assert proxy["port"] == 8080

        # SOCKS5 default port
        proxy = manager._parse_proxy("socks5://proxy.example.com")
        assert proxy is not None
        assert proxy["port"] == 1080

    def test_parse_proxy_invalid_format(self):
        """Test proxy parsing with invalid format."""
        manager = ProxyManager()

        # Invalid port
        proxy = manager._parse_proxy("proxy.example.com:invalid")
        assert proxy is None

    def test_get_random_proxy_when_enabled(self):
        """Test get_random_proxy returns a proxy when enabled."""
        config = {"enabled": True}
        manager = ProxyManager(config)

        # Add proxies manually
        proxy1 = manager._parse_proxy("192.168.1.1:8080")
        proxy2 = manager._parse_proxy("192.168.1.2:8080")
        manager.proxies = [proxy1, proxy2]

        selected = manager.get_random_proxy()

        assert selected is not None
        assert selected in manager.proxies

    def test_get_random_proxy_excludes_failed(self):
        """Test get_random_proxy excludes failed proxies."""
        config = {"enabled": True}
        manager = ProxyManager(config)

        proxy1 = manager._parse_proxy("192.168.1.1:8080")
        proxy2 = manager._parse_proxy("192.168.1.2:8080")
        manager.proxies = [proxy1, proxy2]

        # Mark first proxy as failed
        manager.mark_proxy_failed(proxy1)

        # Should only return non-failed proxy
        for _ in range(10):
            selected = manager.get_random_proxy()
            assert selected == proxy2

    def test_get_random_proxy_resets_when_all_failed(self):
        """Test get_random_proxy resets failed list when all proxies failed."""
        config = {"enabled": True}
        manager = ProxyManager(config)

        proxy1 = manager._parse_proxy("192.168.1.1:8080")
        proxy2 = manager._parse_proxy("192.168.1.2:8080")
        manager.proxies = [proxy1, proxy2]

        # Mark all as failed
        manager.mark_proxy_failed(proxy1)
        manager.mark_proxy_failed(proxy2)

        # Should reset and return a proxy
        selected = manager.get_random_proxy()
        assert selected is not None
        assert len(manager.failed_proxies) == 0

    def test_rotate_proxy(self):
        """Test proxy rotation."""
        config = {"enabled": True}
        manager = ProxyManager(config)

        proxy1 = manager._parse_proxy("192.168.1.1:8080")
        proxy2 = manager._parse_proxy("192.168.1.2:8080")
        proxy3 = manager._parse_proxy("192.168.1.3:8080")
        manager.proxies = [proxy1, proxy2, proxy3]

        # First rotation
        rotated = manager.rotate_proxy()
        assert rotated == proxy2

        # Second rotation
        rotated = manager.rotate_proxy()
        assert rotated == proxy3

        # Third rotation (wraps around)
        rotated = manager.rotate_proxy()
        assert rotated == proxy1

    def test_rotate_proxy_skips_failed(self):
        """Test rotate_proxy skips failed proxies."""
        config = {"enabled": True}
        manager = ProxyManager(config)

        proxy1 = manager._parse_proxy("192.168.1.1:8080")
        proxy2 = manager._parse_proxy("192.168.1.2:8080")
        manager.proxies = [proxy1, proxy2]

        # Mark next proxy as failed
        manager.mark_proxy_failed(proxy2)

        # Rotation should skip to available proxy
        rotated = manager.rotate_proxy()
        assert rotated != proxy2

    def test_get_playwright_proxy_format(self):
        """Test Playwright proxy format conversion."""
        config = {"enabled": True}
        manager = ProxyManager(config)

        proxy = manager._parse_proxy("http://user:pass@192.168.1.1:8080")
        manager.proxies = [proxy]

        playwright_proxy = manager.get_playwright_proxy(proxy)

        assert playwright_proxy is not None
        assert playwright_proxy["server"] == "http://192.168.1.1:8080"
        assert playwright_proxy["username"] == "user"
        assert playwright_proxy["password"] == "pass"

    def test_get_playwright_proxy_without_auth(self):
        """Test Playwright proxy format without authentication."""
        config = {"enabled": True}
        manager = ProxyManager(config)

        proxy = manager._parse_proxy("http://192.168.1.1:8080")
        manager.proxies = [proxy]

        playwright_proxy = manager.get_playwright_proxy(proxy)

        assert playwright_proxy is not None
        assert playwright_proxy["server"] == "http://192.168.1.1:8080"
        assert "username" not in playwright_proxy
        assert "password" not in playwright_proxy

    def test_get_playwright_proxy_uses_random_when_none(self):
        """Test get_playwright_proxy uses random proxy when none specified."""
        config = {"enabled": True}
        manager = ProxyManager(config)

        proxy1 = manager._parse_proxy("192.168.1.1:8080")
        manager.proxies = [proxy1]

        playwright_proxy = manager.get_playwright_proxy()

        assert playwright_proxy is not None
        assert playwright_proxy["server"] == "http://192.168.1.1:8080"

    def test_get_current_proxy(self):
        """Test getting current proxy."""
        config = {"enabled": True}
        manager = ProxyManager(config)

        proxy1 = manager._parse_proxy("192.168.1.1:8080")
        proxy2 = manager._parse_proxy("192.168.1.2:8080")
        manager.proxies = [proxy1, proxy2]

        # Initially at index 0
        current = manager.get_current_proxy()
        assert current == proxy1

        # After rotation
        manager.rotate_proxy()
        current = manager.get_current_proxy()
        assert current == proxy2

    def test_clear_failed_proxies(self):
        """Test clearing failed proxies list."""
        manager = ProxyManager()

        proxy1 = manager._parse_proxy("192.168.1.1:8080")
        proxy2 = manager._parse_proxy("192.168.1.2:8080")

        manager.mark_proxy_failed(proxy1)
        manager.mark_proxy_failed(proxy2)

        assert len(manager.failed_proxies) == 2

        manager.clear_failed_proxies()

        assert len(manager.failed_proxies) == 0

    def test_mark_proxy_failed_duplicate(self):
        """Test marking same proxy as failed multiple times."""
        manager = ProxyManager()

        proxy = manager._parse_proxy("192.168.1.1:8080")

        manager.mark_proxy_failed(proxy)
        manager.mark_proxy_failed(proxy)

        # Should only be in list once
        assert manager.failed_proxies.count(proxy["server"]) == 1

    def test_rotate_on_error_config(self):
        """Test rotate_on_error configuration option."""
        config = {"enabled": True, "rotate_on_error": True}
        manager = ProxyManager(config)

        assert manager.rotate_on_error is True

        config = {"enabled": True, "rotate_on_error": False}
        manager = ProxyManager(config)

        assert manager.rotate_on_error is False

    def test_load_proxies_skips_comments_and_empty_lines(self):
        """Test that proxy loading skips comments and empty lines."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("# This is a comment\n")
            f.write("\n")
            f.write("  \n")
            f.write("192.168.1.1:8080\n")
            f.write("# Another comment\n")
            f.write("192.168.1.2:8080\n")
            proxy_file = f.name

        try:
            config = {"enabled": True, "file": proxy_file}
            manager = ProxyManager(config)

            # Should only load non-comment, non-empty lines
            assert len(manager.proxies) == 2
        finally:
            Path(proxy_file).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
