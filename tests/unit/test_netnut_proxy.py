"""Unit tests for NetNut proxy manager."""

from pathlib import Path

import pytest

from src.utils.security.netnut_proxy import NetNutProxyManager


@pytest.fixture
def proxy_manager():
    """Create a fresh proxy manager for each test."""
    return NetNutProxyManager()


@pytest.fixture
def sample_csv_content():
    """Sample CSV content for testing."""
    return """endpoint
gw.netnut.net:5959:ntnt_8zq7s8ef-res-tr-sid-657606515:Ab4ME55ouIYefAT
gw.netnut.net:5959:ntnt_8zq7s8ef-res-tr-sid-702283134:Ab4ME55ouIYefAT
gw2.netnut.net:5960:ntnt_user123:password456"""


class TestNetNutProxyManager:
    """Test NetNut proxy manager functionality."""

    def test_parse_valid_netnut_endpoint(self, proxy_manager):
        """Test parsing a valid NetNut endpoint."""
        endpoint = "gw.netnut.net:5959:ntnt_8zq7s8ef-res-tr-sid-657606515:Ab4ME55ouIYefAT"

        proxy = proxy_manager._parse_netnut_endpoint(endpoint)

        assert proxy is not None
        assert proxy["host"] == "gw.netnut.net"
        assert proxy["port"] == 5959
        assert proxy["username"] == "ntnt_8zq7s8ef-res-tr-sid-657606515"
        assert proxy["password"] == "Ab4ME55ouIYefAT"
        assert proxy["server"] == "http://gw.netnut.net:5959"
        assert proxy["protocol"] == "http"
        assert proxy["endpoint"] == endpoint

    def test_parse_invalid_endpoint_format(self, proxy_manager):
        """Test parsing invalid endpoint format."""
        # Missing password
        endpoint = "gw.netnut.net:5959:username"
        proxy = proxy_manager._parse_netnut_endpoint(endpoint)
        assert proxy is None

        # Missing port
        endpoint = "gw.netnut.net:username:password"
        proxy = proxy_manager._parse_netnut_endpoint(endpoint)
        assert proxy is None

    def test_parse_invalid_port(self, proxy_manager):
        """Test parsing endpoint with invalid port."""
        endpoint = "gw.netnut.net:invalid:username:password"
        proxy = proxy_manager._parse_netnut_endpoint(endpoint)
        assert proxy is None

    def test_load_from_csv_content(self, proxy_manager, sample_csv_content):
        """Test loading proxies from CSV content."""
        count = proxy_manager.load_from_csv_content(sample_csv_content)

        assert count == 3
        assert len(proxy_manager.proxies) == 3
        assert proxy_manager.proxies[0]["host"] == "gw.netnut.net"
        assert proxy_manager.proxies[1]["port"] == 5959
        assert proxy_manager.proxies[2]["host"] == "gw2.netnut.net"

    def test_load_from_csv_content_without_header(self, proxy_manager):
        """Test loading proxies from CSV without header."""
        csv_content = """gw.netnut.net:5959:username1:password1
gw.netnut.net:5959:username2:password2"""

        count = proxy_manager.load_from_csv_content(csv_content)

        assert count == 2
        assert len(proxy_manager.proxies) == 2

    def test_load_from_csv_content_with_comments(self, proxy_manager):
        """Test loading proxies with comments in CSV."""
        csv_content = """endpoint
# This is a comment
gw.netnut.net:5959:username1:password1
# Another comment
gw.netnut.net:5959:username2:password2"""

        count = proxy_manager.load_from_csv_content(csv_content)

        assert count == 2
        assert len(proxy_manager.proxies) == 2

    def test_rotate_proxy(self, proxy_manager, sample_csv_content):
        """Test proxy rotation."""
        proxy_manager.load_from_csv_content(sample_csv_content)

        first_proxy = proxy_manager.proxies[0]
        rotated = proxy_manager.rotate_proxy()

        # Should get the second proxy after rotation
        assert rotated is not None
        assert rotated["endpoint"] != first_proxy["endpoint"]

    def test_mark_proxy_failed(self, proxy_manager, sample_csv_content):
        """Test marking proxy as failed."""
        proxy_manager.load_from_csv_content(sample_csv_content)
        proxy = proxy_manager.proxies[0]

        proxy_manager.mark_proxy_failed(proxy)

        assert proxy["endpoint"] in proxy_manager.failed_proxies
        assert len(proxy_manager.failed_proxies) == 1

    def test_rotate_proxy_skip_failed(self, proxy_manager, sample_csv_content):
        """Test that rotation skips failed ones sequentially."""
        proxy_manager.load_from_csv_content(sample_csv_content)

        # Mark first two as failed
        proxy_manager.mark_proxy_failed(proxy_manager.proxies[0])
        proxy_manager.mark_proxy_failed(proxy_manager.proxies[1])

        # Rotate should skip to third one
        proxy = proxy_manager.rotate_proxy()

        assert proxy is not None
        assert proxy["endpoint"] not in proxy_manager.failed_proxies
        assert proxy["endpoint"] == proxy_manager.proxies[2]["endpoint"]

    def test_rotate_proxy_all_failed_resets(self, proxy_manager, sample_csv_content):
        """Test that when all proxies fail, the failed list resets."""
        proxy_manager.load_from_csv_content(sample_csv_content)

        # Mark all as failed
        for proxy in proxy_manager.proxies:
            proxy_manager.mark_proxy_failed(proxy)

        assert len(proxy_manager.failed_proxies) == 3

        # Rotating should reset failed list
        proxy = proxy_manager.rotate_proxy()

        assert proxy is not None
        assert len(proxy_manager.failed_proxies) == 0

    def test_get_playwright_proxy(self, proxy_manager, sample_csv_content):
        """Test getting Playwright-compatible proxy format."""
        proxy_manager.load_from_csv_content(sample_csv_content)

        playwright_proxy = proxy_manager.get_playwright_proxy()

        assert playwright_proxy is not None
        assert "server" in playwright_proxy
        assert "username" in playwright_proxy
        assert "password" in playwright_proxy
        assert playwright_proxy["server"].startswith("http://")

    def test_get_stats(self, proxy_manager, sample_csv_content):
        """Test getting proxy statistics."""
        proxy_manager.load_from_csv_content(sample_csv_content)

        # Mark one as failed
        proxy_manager.mark_proxy_failed(proxy_manager.proxies[0])

        stats = proxy_manager.get_stats()

        assert stats["total"] == 3
        assert stats["active"] == 2
        assert stats["failed"] == 1

    def test_get_stats_empty(self, proxy_manager):
        """Test getting stats with no proxies."""
        stats = proxy_manager.get_stats()

        assert stats["total"] == 0
        assert stats["active"] == 0
        assert stats["failed"] == 0

    def test_get_proxy_list(self, proxy_manager, sample_csv_content):
        """Test getting proxy list with status."""
        proxy_manager.load_from_csv_content(sample_csv_content)

        # Mark one as failed
        proxy_manager.mark_proxy_failed(proxy_manager.proxies[0])

        proxy_list = proxy_manager.get_proxy_list()

        assert len(proxy_list) == 3
        assert proxy_list[0]["status"] == "failed"
        assert proxy_list[1]["status"] == "active"
        assert proxy_list[2]["status"] == "active"

        # Check required fields
        for proxy_info in proxy_list:
            assert "endpoint" in proxy_info
            assert "host" in proxy_info
            assert "port" in proxy_info
            assert "username" in proxy_info
            assert "status" in proxy_info

    def test_clear_all(self, proxy_manager, sample_csv_content):
        """Test clearing all proxies."""
        proxy_manager.load_from_csv_content(sample_csv_content)
        proxy_manager.mark_proxy_failed(proxy_manager.proxies[0])

        proxy_manager.clear_all()

        assert len(proxy_manager.proxies) == 0
        assert len(proxy_manager.failed_proxies) == 0
        assert proxy_manager.current_proxy_index == 0

    def test_clear_failed_proxies(self, proxy_manager, sample_csv_content):
        """Test clearing only failed proxies."""
        proxy_manager.load_from_csv_content(sample_csv_content)
        proxy_manager.mark_proxy_failed(proxy_manager.proxies[0])

        proxy_manager.clear_failed_proxies()

        assert len(proxy_manager.proxies) == 3  # Proxies still there
        assert len(proxy_manager.failed_proxies) == 0  # Failed list cleared

    def test_load_from_csv_file(self, proxy_manager, tmp_path):
        """Test loading proxies from actual CSV file."""
        # Create temporary CSV file
        csv_file = tmp_path / "test_proxies.csv"
        csv_file.write_text("""endpoint
gw.netnut.net:5959:user1:pass1
gw.netnut.net:5959:user2:pass2
""")

        count = proxy_manager.load_from_csv(csv_file)

        assert count == 2
        assert len(proxy_manager.proxies) == 2

    def test_load_from_csv_file_not_found(self, proxy_manager):
        """Test loading from non-existent file."""
        count = proxy_manager.load_from_csv(Path("nonexistent.csv"))
        assert count == 0
        assert len(proxy_manager.proxies) == 0


class TestNetNutProxyManagerAllocateNext:
    """Test NetNut proxy manager allocate_next functionality."""

    def test_allocate_next_sequential(self, sample_csv_content):
        """Test sequential proxy allocation."""
        manager = NetNutProxyManager()
        manager.load_from_csv_content(sample_csv_content)

        # Test sequential allocation
        proxy1 = manager.allocate_next()
        assert proxy1 is not None
        assert proxy1["host"] == "gw.netnut.net"
        assert manager._allocation_index == 1

        proxy2 = manager.allocate_next()
        assert proxy2 is not None
        assert manager._allocation_index == 2

        proxy3 = manager.allocate_next()
        assert proxy3 is not None
        assert proxy3["host"] == "gw2.netnut.net"
        assert manager._allocation_index == 0  # Wrapped around

    def test_allocate_next_wraps_around(self, sample_csv_content):
        """Test that allocation wraps around to beginning."""
        manager = NetNutProxyManager()
        manager.load_from_csv_content(sample_csv_content)

        # Allocate all 3 proxies
        manager.allocate_next()
        manager.allocate_next()
        manager.allocate_next()

        # Should wrap around to first proxy
        proxy = manager.allocate_next()
        assert proxy is not None
        assert proxy["host"] == "gw.netnut.net"

    def test_allocate_next_skips_failed(self, sample_csv_content):
        """Test that allocate_next skips failed proxies."""
        manager = NetNutProxyManager()
        manager.load_from_csv_content(sample_csv_content)

        # Mark second proxy as failed
        second_endpoint = manager.proxies[1]["endpoint"]
        manager.failed_proxies.append(second_endpoint)

        # First allocation
        proxy1 = manager.allocate_next()
        assert proxy1["endpoint"] == manager.proxies[0]["endpoint"]

        # Second allocation should skip the failed one and get third
        proxy2 = manager.allocate_next()
        assert proxy2["endpoint"] == manager.proxies[2]["endpoint"]
        assert proxy2["endpoint"] != second_endpoint

    def test_allocate_next_all_failed_resets(self, sample_csv_content):
        """Test that when all proxies are failed, the failed list resets."""
        manager = NetNutProxyManager()
        manager.load_from_csv_content(sample_csv_content)

        # Mark all as failed
        for proxy in manager.proxies:
            manager.mark_proxy_failed(proxy)

        assert len(manager.failed_proxies) == 3

        # Next allocation should reset failed list
        proxy = manager.allocate_next()

        assert proxy is not None
        assert len(manager.failed_proxies) == 0

    def test_allocate_next_no_proxies(self):
        """Test allocate_next with no proxies loaded."""
        manager = NetNutProxyManager()

        proxy = manager.allocate_next()
        assert proxy is None

    def test_reset_allocation_index(self, sample_csv_content):
        """Test resetting allocation index."""
        manager = NetNutProxyManager()
        manager.load_from_csv_content(sample_csv_content)

        # Allocate a few proxies
        manager.allocate_next()
        manager.allocate_next()
        assert manager._allocation_index == 2

        # Reset index
        manager.reset_allocation_index()
        assert manager._allocation_index == 0

        # Next allocation should start from beginning
        proxy = manager.allocate_next()
        assert proxy["endpoint"] == manager.proxies[0]["endpoint"]
