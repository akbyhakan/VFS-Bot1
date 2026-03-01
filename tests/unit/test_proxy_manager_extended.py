"""Extended tests for proxy manager."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.utils.security.proxy_manager import ProxyManager


def test_proxy_manager_initialization_disabled():
    """Test proxy manager initialization when disabled."""
    manager = ProxyManager()
    assert manager.enabled is False
    assert manager.proxies == []
    assert manager.failed_proxies == []


def test_proxy_manager_initialization_enabled():
    """Test proxy manager initialization when enabled."""
    config = {"enabled": True, "file": "config/proxy-endpoints.csv"}
    with patch.object(Path, "exists", return_value=False):
        manager = ProxyManager(config)
        assert manager.enabled is True
        assert manager.rotate_on_error is True


def test_load_proxies_file_not_found():
    """Test loading proxies when file doesn't exist."""
    manager = ProxyManager()
    with patch.object(Path, "exists", return_value=False):
        count = manager.load_proxies()
        assert count == 0
        assert len(manager.proxies) == 0


def test_load_proxies_success():
    """Test successful proxy loading."""
    proxy_content = "proxy1.com:8080\nproxy2.com:3128\n# Comment line\n\nproxy3.com:9000"

    with patch("builtins.open", mock_open(read_data=proxy_content)):
        with patch.object(Path, "exists", return_value=True):
            manager = ProxyManager()
            count = manager.load_proxies()

            assert count == 3
            assert len(manager.proxies) == 3


def test_load_proxies_skip_comments_and_empty():
    """Test that comments and empty lines are skipped."""
    proxy_content = "# Comment\nproxy1.com:8080\n\n# Another comment\n  \nproxy2.com:3128"

    with patch("builtins.open", mock_open(read_data=proxy_content)):
        with patch.object(Path, "exists", return_value=True):
            manager = ProxyManager()
            count = manager.load_proxies()

            assert count == 2


def test_load_proxies_error_handling():
    """Test error handling during proxy loading."""
    with patch("builtins.open", side_effect=Exception("File read error")):
        with patch.object(Path, "exists", return_value=True):
            manager = ProxyManager()
            count = manager.load_proxies()

            assert count == 0


def test_parse_proxy_simple_format():
    """Test parsing simple host:port format."""
    manager = ProxyManager()
    proxy = manager._parse_proxy("proxy.example.com:8080")

    assert proxy is not None
    assert proxy["host"] == "proxy.example.com"
    assert proxy["port"] == 8080
    assert proxy["protocol"] == "http"
    assert "username" not in proxy


def test_parse_proxy_with_auth():
    """Test parsing proxy with authentication."""
    manager = ProxyManager()
    proxy = manager._parse_proxy("user:pass@proxy.example.com:8080")

    assert proxy is not None
    assert proxy["username"] == "user"
    assert proxy["password"] == "pass"
    assert proxy["host"] == "proxy.example.com"
    assert proxy["port"] == 8080


def test_parse_proxy_with_protocol():
    """Test parsing proxy with protocol."""
    manager = ProxyManager()
    proxy = manager._parse_proxy("http://proxy.example.com:8080")

    assert proxy is not None
    assert proxy["protocol"] == "http"
    assert proxy["server"] == "http://proxy.example.com:8080"


def test_parse_proxy_socks5():
    """Test parsing socks5 proxy."""
    manager = ProxyManager()
    proxy = manager._parse_proxy("socks5://proxy.example.com:1080")

    assert proxy is not None
    assert proxy["protocol"] == "socks5"
    assert proxy["port"] == 1080


def test_parse_proxy_with_full_auth():
    """Test parsing proxy with protocol and auth."""
    manager = ProxyManager()
    proxy = manager._parse_proxy("http://user:pass@proxy.example.com:8080")

    assert proxy is not None
    assert proxy["username"] == "user"
    assert proxy["password"] == "pass"
    assert proxy["protocol"] == "http"


def test_parse_proxy_invalid_port():
    """Test parsing proxy with invalid port."""
    manager = ProxyManager()
    proxy = manager._parse_proxy("proxy.example.com:invalid")

    assert proxy is None


def test_parse_proxy_no_port_http():
    """Test parsing proxy without port (http defaults to 8080)."""
    manager = ProxyManager()
    proxy = manager._parse_proxy("http://proxy.example.com")

    assert proxy is not None
    assert proxy["port"] == 8080


def test_parse_proxy_error_handling():
    """Test proxy parsing error handling."""
    manager = ProxyManager()
    proxy = manager._parse_proxy("invalid:::proxy:::")

    # Should handle gracefully
    assert proxy is None or isinstance(proxy, dict)


def test_mark_proxy_failed():
    """Test marking proxy as failed."""
    manager = ProxyManager()
    proxy = {
        "server": "http://proxy1.com:8080",
        "host": "proxy1.com",
        "port": 8080,
        "protocol": "http",
    }

    manager.mark_proxy_failed(proxy)
    assert "http://proxy1.com:8080" in manager.failed_proxies


def test_mark_proxy_failed_duplicate():
    """Test that marking same proxy twice doesn't duplicate."""
    manager = ProxyManager()
    proxy = {
        "server": "http://proxy1.com:8080",
        "host": "proxy1.com",
        "port": 8080,
        "protocol": "http",
    }

    manager.mark_proxy_failed(proxy)
    manager.mark_proxy_failed(proxy)

    assert manager.failed_proxies.count("http://proxy1.com:8080") == 1


def test_mark_proxy_failed_none():
    """Test marking None proxy as failed."""
    manager = ProxyManager()
    manager.mark_proxy_failed(None)

    assert len(manager.failed_proxies) == 0


def test_rotate_proxy_disabled():
    """Test rotate proxy when disabled."""
    manager = ProxyManager({"enabled": False})
    proxy = manager.rotate_proxy()

    assert proxy is None


def test_rotate_proxy_no_proxies():
    """Test rotate proxy with no proxies."""
    with patch.object(Path, "exists", return_value=False):
        manager = ProxyManager({"enabled": True})
    proxy = manager.rotate_proxy()

    assert proxy is None


def test_rotate_proxy_success():
    """Test successful proxy rotation."""
    manager = ProxyManager({"enabled": True})
    manager.proxies = [
        {
            "server": "http://proxy1.com:8080",
            "host": "proxy1.com",
            "port": 8080,
            "protocol": "http",
        },
        {
            "server": "http://proxy2.com:8080",
            "host": "proxy2.com",
            "port": 8080,
            "protocol": "http",
        },
    ]
    manager.current_proxy_index = 0

    proxy = manager.rotate_proxy()
    assert proxy is not None
    assert manager.current_proxy_index == 1


def test_rotate_proxy_wraps_around():
    """Test that rotation wraps around to beginning."""
    manager = ProxyManager({"enabled": True})
    manager.proxies = [
        {
            "server": "http://proxy1.com:8080",
            "host": "proxy1.com",
            "port": 8080,
            "protocol": "http",
        },
        {
            "server": "http://proxy2.com:8080",
            "host": "proxy2.com",
            "port": 8080,
            "protocol": "http",
        },
    ]
    manager.current_proxy_index = 1

    manager.rotate_proxy()
    assert manager.current_proxy_index == 0


def test_rotate_proxy_skip_failed():
    """Test that rotation skips failed proxies sequentially."""
    manager = ProxyManager({"enabled": True})
    manager.proxies = [
        {
            "server": "http://proxy1.com:8080",
            "host": "proxy1.com",
            "port": 8080,
            "protocol": "http",
        },
        {
            "server": "http://proxy2.com:8080",
            "host": "proxy2.com",
            "port": 8080,
            "protocol": "http",
        },
        {
            "server": "http://proxy3.com:8080",
            "host": "proxy3.com",
            "port": 8080,
            "protocol": "http",
        },
    ]
    manager.current_proxy_index = 0
    manager.failed_proxies = ["http://proxy2.com:8080"]

    # Should skip failed proxy2 and get proxy3
    proxy = manager.rotate_proxy()
    assert proxy["server"] == "http://proxy3.com:8080"


def test_rotate_proxy_all_failed_resets():
    """Test rotate_proxy when all proxies are failed."""
    manager = ProxyManager({"enabled": True})
    manager.proxies = [
        {
            "server": "http://proxy1.com:8080",
            "host": "proxy1.com",
            "port": 8080,
            "protocol": "http",
        },
        {
            "server": "http://proxy2.com:8080",
            "host": "proxy2.com",
            "port": 8080,
            "protocol": "http",
        },
    ]
    manager.current_proxy_index = 0
    manager.failed_proxies = [
        "http://proxy1.com:8080",
        "http://proxy2.com:8080",
    ]

    proxy = manager.rotate_proxy()
    # Should reset failed list and return next proxy
    assert proxy is not None
    assert len(manager.failed_proxies) == 0


def test_get_playwright_proxy_disabled():
    """Test get_playwright_proxy when disabled."""
    manager = ProxyManager({"enabled": False})
    proxy = manager.get_playwright_proxy()

    assert proxy is None


def test_get_playwright_proxy_with_auth():
    """Test get_playwright_proxy with authentication."""
    manager = ProxyManager({"enabled": True})
    proxy_dict = {
        "server": "http://proxy.com:8080",
        "host": "proxy.com",
        "port": 8080,
        "protocol": "http",
        "username": "user",
        "password": "pass",
    }

    result = manager.get_playwright_proxy(proxy_dict)
    assert result["server"] == "http://proxy.com:8080"
    assert result["username"] == "user"
    assert result["password"] == "pass"


def test_get_playwright_proxy_without_auth():
    """Test get_playwright_proxy without authentication."""
    manager = ProxyManager({"enabled": True})
    proxy_dict = {
        "server": "http://proxy.com:8080",
        "host": "proxy.com",
        "port": 8080,
        "protocol": "http",
    }

    result = manager.get_playwright_proxy(proxy_dict)
    assert result["server"] == "http://proxy.com:8080"
    assert "username" not in result
    assert "password" not in result


def test_get_playwright_proxy_auto_select():
    """Test get_playwright_proxy with automatic selection."""
    manager = ProxyManager({"enabled": True})
    manager.proxies = [
        {
            "server": "http://proxy1.com:8080",
            "host": "proxy1.com",
            "port": 8080,
            "protocol": "http",
        },
    ]

    result = manager.get_playwright_proxy()
    assert result is not None
    assert result["server"] == "http://proxy1.com:8080"


def test_get_current_proxy():
    """Test get_current_proxy."""
    manager = ProxyManager({"enabled": True})
    manager.proxies = [
        {
            "server": "http://proxy1.com:8080",
            "host": "proxy1.com",
            "port": 8080,
            "protocol": "http",
        },
        {
            "server": "http://proxy2.com:8080",
            "host": "proxy2.com",
            "port": 8080,
            "protocol": "http",
        },
    ]
    manager.current_proxy_index = 1

    proxy = manager.get_current_proxy()
    assert proxy["server"] == "http://proxy2.com:8080"


def test_get_current_proxy_disabled():
    """Test get_current_proxy when disabled."""
    manager = ProxyManager({"enabled": False})
    proxy = manager.get_current_proxy()

    assert proxy is None


def test_clear_failed_proxies():
    """Test clearing failed proxies list."""
    manager = ProxyManager()
    manager.failed_proxies = ["http://proxy1.com:8080", "http://proxy2.com:8080"]

    manager.clear_failed_proxies()
    assert len(manager.failed_proxies) == 0


def test_proxy_file_path_default():
    """Test default proxy file path is config/proxy-endpoints.csv."""
    manager = ProxyManager()

    assert str(manager.proxy_file) == "config/proxy-endpoints.csv"


def test_proxy_file_path_custom():
    """Test custom proxy file path."""
    config = {"enabled": True, "file": "custom/path/proxy-endpoints.csv"}
    manager = ProxyManager(config)

    assert str(manager.proxy_file) == "custom/path/proxy-endpoints.csv"


def test_rotate_on_error_config():
    """Test rotate_on_error configuration."""
    config = {"rotate_on_error": False}
    manager = ProxyManager(config)

    assert manager.rotate_on_error is False


def test_allocate_next_sequential():
    """Test sequential proxy allocation."""
    manager = ProxyManager({"enabled": True})
    manager.proxies = [
        {
            "server": "http://proxy1.com:8080",
            "host": "proxy1.com",
            "port": 8080,
            "protocol": "http",
        },
        {
            "server": "http://proxy2.com:8080",
            "host": "proxy2.com",
            "port": 8080,
            "protocol": "http",
        },
        {
            "server": "http://proxy3.com:8080",
            "host": "proxy3.com",
            "port": 8080,
            "protocol": "http",
        },
    ]

    # Test sequential allocation
    proxy1 = manager.allocate_next()
    assert proxy1["server"] == "http://proxy1.com:8080"
    assert manager._allocation_index == 1

    proxy2 = manager.allocate_next()
    assert proxy2["server"] == "http://proxy2.com:8080"
    assert manager._allocation_index == 2

    proxy3 = manager.allocate_next()
    assert proxy3["server"] == "http://proxy3.com:8080"
    assert manager._allocation_index == 0  # Wrapped around


def test_allocate_next_wraps_around():
    """Test that allocation wraps around to beginning."""
    manager = ProxyManager({"enabled": True})
    manager.proxies = [
        {
            "server": "http://proxy1.com:8080",
            "host": "proxy1.com",
            "port": 8080,
            "protocol": "http",
        },
        {
            "server": "http://proxy2.com:8080",
            "host": "proxy2.com",
            "port": 8080,
            "protocol": "http",
        },
    ]

    # Allocate all proxies
    manager.allocate_next()  # proxy1
    manager.allocate_next()  # proxy2

    # Should wrap around to proxy1
    proxy = manager.allocate_next()
    assert proxy["server"] == "http://proxy1.com:8080"


def test_allocate_next_skips_failed():
    """Test that allocate_next skips failed proxies."""
    manager = ProxyManager({"enabled": True})
    manager.proxies = [
        {
            "server": "http://proxy1.com:8080",
            "host": "proxy1.com",
            "port": 8080,
            "protocol": "http",
        },
        {
            "server": "http://proxy2.com:8080",
            "host": "proxy2.com",
            "port": 8080,
            "protocol": "http",
        },
        {
            "server": "http://proxy3.com:8080",
            "host": "proxy3.com",
            "port": 8080,
            "protocol": "http",
        },
    ]
    # Mark proxy2 as failed
    manager.failed_proxies = ["http://proxy2.com:8080"]

    # First allocation should get proxy1
    proxy1 = manager.allocate_next()
    assert proxy1["server"] == "http://proxy1.com:8080"

    # Second allocation should skip proxy2 and get proxy3
    proxy2 = manager.allocate_next()
    assert proxy2["server"] == "http://proxy3.com:8080"


def test_allocate_next_all_failed_resets():
    """Test that when all proxies are failed, the failed list resets."""
    manager = ProxyManager({"enabled": True})
    manager.proxies = [
        {
            "server": "http://proxy1.com:8080",
            "host": "proxy1.com",
            "port": 8080,
            "protocol": "http",
        },
        {
            "server": "http://proxy2.com:8080",
            "host": "proxy2.com",
            "port": 8080,
            "protocol": "http",
        },
    ]
    # Mark all as failed
    manager.failed_proxies = [
        "http://proxy1.com:8080",
        "http://proxy2.com:8080",
    ]

    proxy = manager.allocate_next()

    # Should reset failed list and return a proxy
    assert proxy is not None
    assert len(manager.failed_proxies) == 0


def test_allocate_next_disabled():
    """Test allocate_next when proxy manager is disabled."""
    manager = ProxyManager({"enabled": False})
    manager.proxies = [
        {
            "server": "http://proxy1.com:8080",
            "host": "proxy1.com",
            "port": 8080,
            "protocol": "http",
        },
    ]

    proxy = manager.allocate_next()
    assert proxy is None


def test_allocate_next_no_proxies():
    """Test allocate_next with no proxies loaded."""
    with patch.object(Path, "exists", return_value=False):
        manager = ProxyManager({"enabled": True})

    proxy = manager.allocate_next()
    assert proxy is None


def test_reset_allocation_index():
    """Test resetting allocation index."""
    manager = ProxyManager({"enabled": True})
    manager.proxies = [
        {
            "server": "http://proxy1.com:8080",
            "host": "proxy1.com",
            "port": 8080,
            "protocol": "http",
        },
        {
            "server": "http://proxy2.com:8080",
            "host": "proxy2.com",
            "port": 8080,
            "protocol": "http",
        },
    ]

    # Allocate a few proxies
    manager.allocate_next()
    manager.allocate_next()
    assert manager._allocation_index == 0  # Wrapped around

    # Reset index
    manager.reset_allocation_index()
    assert manager._allocation_index == 0

    # Next allocation should start from beginning
    proxy = manager.allocate_next()
    assert proxy["server"] == "http://proxy1.com:8080"
