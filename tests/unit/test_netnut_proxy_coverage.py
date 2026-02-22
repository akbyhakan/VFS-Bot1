"""Additional coverage tests for utils/security/netnut_proxy module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.security.netnut_proxy import NetNutProxyManager, mask_proxy_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CSV_THREE_PROXIES = (
    "endpoint\n"
    "gw.netnut.net:5959:user1:pass1\n"
    "gw.netnut.net:5959:user2:pass2\n"
    "gw2.netnut.net:6060:user3:pass3\n"
)


@pytest.fixture
def mgr():
    """Fresh NetNutProxyManager for each test."""
    return NetNutProxyManager()


@pytest.fixture
def mgr_with_proxies():
    """NetNutProxyManager pre-loaded with 3 proxies."""
    m = NetNutProxyManager()
    m.load_from_csv_content(CSV_THREE_PROXIES)
    return m


# ---------------------------------------------------------------------------
# mask_proxy_password
# ---------------------------------------------------------------------------


class TestMaskProxyPassword:
    """Tests for the standalone mask_proxy_password helper."""

    def test_full_four_part_format_masked(self):
        """Password field (4th segment) is replaced with ***."""
        result = mask_proxy_password("gw.netnut.net:5959:user:mysecret")
        assert result == "gw.netnut.net:5959:user:***"

    def test_short_format_returned_as_is(self):
        """Input with fewer than 4 colon-separated parts is returned unchanged."""
        result = mask_proxy_password("gw.netnut.net:5959:user")
        assert result == "gw.netnut.net:5959:user"

    def test_empty_string_returned_as_is(self):
        """Empty string is returned unchanged."""
        result = mask_proxy_password("")
        assert result == ""


# ---------------------------------------------------------------------------
# load_from_csv (file-based)
# ---------------------------------------------------------------------------


class TestLoadFromCsv:
    """Tests for NetNutProxyManager.load_from_csv()."""

    def test_file_not_found_returns_zero(self, mgr):
        """load_from_csv returns 0 when file does not exist."""
        count = mgr.load_from_csv(Path("/nonexistent/path/proxies.csv"))
        assert count == 0
        assert len(mgr.proxies) == 0

    def test_successful_load_from_file(self, mgr, tmp_path):
        """load_from_csv loads proxies from a real file."""
        csv_file = tmp_path / "proxies.csv"
        csv_file.write_text("endpoint\ngw.netnut.net:5959:uA:pA\ngw.netnut.net:5959:uB:pB\n")

        count = mgr.load_from_csv(csv_file)

        assert count == 2
        assert len(mgr.proxies) == 2

    def test_load_csv_exception_returns_zero(self, mgr, tmp_path):
        """load_from_csv returns 0 when an unexpected read error occurs."""
        csv_file = tmp_path / "bad.csv"
        csv_file.write_text("endpoint\ngw.netnut.net:5959:u:p\n")

        with patch("builtins.open", side_effect=OSError("read error")):
            count = mgr.load_from_csv(csv_file)

        assert count == 0


# ---------------------------------------------------------------------------
# rotate_proxy
# ---------------------------------------------------------------------------


class TestRotateProxy:
    """Tests for NetNutProxyManager.rotate_proxy()."""

    def test_empty_proxies_returns_none(self, mgr):
        """rotate_proxy returns None when no proxies are loaded."""
        result = mgr.rotate_proxy()
        assert result is None

    def test_single_proxy_all_failed_resets(self, mgr):
        """Single-proxy manager resets failed list and returns proxy."""
        mgr.load_from_csv_content("endpoint\ngw.netnut.net:5959:u:p\n")
        mgr.mark_proxy_failed(mgr.proxies[0])

        result = mgr.rotate_proxy()

        assert result is not None
        assert len(mgr.failed_proxies) == 0

    def test_all_failed_resets_and_returns(self, mgr_with_proxies):
        """When all proxies are failed, list resets and a proxy is returned."""
        for p in mgr_with_proxies.proxies:
            mgr_with_proxies.mark_proxy_failed(p)

        result = mgr_with_proxies.rotate_proxy()

        assert result is not None
        assert len(mgr_with_proxies.failed_proxies) == 0


# ---------------------------------------------------------------------------
# mark_proxy_failed
# ---------------------------------------------------------------------------


class TestMarkProxyFailed:
    """Tests for NetNutProxyManager.mark_proxy_failed()."""

    def test_marks_new_proxy_as_failed(self, mgr_with_proxies):
        """A fresh proxy is added to the failed list."""
        proxy = mgr_with_proxies.proxies[0]
        mgr_with_proxies.mark_proxy_failed(proxy)
        assert proxy["endpoint"] in mgr_with_proxies.failed_proxies

    def test_does_not_duplicate_failed_entry(self, mgr_with_proxies):
        """Calling mark_proxy_failed twice does not duplicate the entry."""
        proxy = mgr_with_proxies.proxies[0]
        mgr_with_proxies.mark_proxy_failed(proxy)
        mgr_with_proxies.mark_proxy_failed(proxy)
        assert mgr_with_proxies.failed_proxies.count(proxy["endpoint"]) == 1


# ---------------------------------------------------------------------------
# get_playwright_proxy
# ---------------------------------------------------------------------------


class TestGetPlaywrightProxy:
    """Tests for NetNutProxyManager.get_playwright_proxy()."""

    def test_with_proxy_dict_returns_playwright_format(self, mgr_with_proxies):
        """Passing an explicit proxy dict returns playwright-compatible dict."""
        proxy = mgr_with_proxies.proxies[0]
        result = mgr_with_proxies.get_playwright_proxy(proxy)

        assert result is not None
        assert "server" in result
        assert "username" in result
        assert "password" in result
        assert result["server"].startswith("http://")

    def test_none_calls_rotate_proxy(self, mgr_with_proxies):
        """Passing None triggers rotate_proxy internally."""
        with patch.object(
            mgr_with_proxies, "rotate_proxy", return_value=mgr_with_proxies.proxies[0]
        ) as mock_rotate:
            result = mgr_with_proxies.get_playwright_proxy(None)

        mock_rotate.assert_called_once()
        assert result is not None

    def test_no_proxies_returns_none(self, mgr):
        """get_playwright_proxy returns None when no proxies are available."""
        result = mgr.get_playwright_proxy()
        assert result is None


# ---------------------------------------------------------------------------
# get_stats / get_proxy_list
# ---------------------------------------------------------------------------


class TestGetStats:
    """Tests for NetNutProxyManager.get_stats()."""

    def test_counts_active_and_failed(self, mgr_with_proxies):
        """Counts reflect current state correctly."""
        mgr_with_proxies.mark_proxy_failed(mgr_with_proxies.proxies[0])
        stats = mgr_with_proxies.get_stats()

        assert stats["total"] == 3
        assert stats["failed"] == 1
        assert stats["active"] == 2

    def test_empty_manager_all_zeros(self, mgr):
        """All counters are 0 when no proxies loaded."""
        stats = mgr.get_stats()
        assert stats == {"total": 0, "active": 0, "failed": 0}


class TestGetProxyList:
    """Tests for NetNutProxyManager.get_proxy_list()."""

    def test_active_and_failed_statuses(self, mgr_with_proxies):
        """Failed proxies show status='failed'; others show 'active'."""
        mgr_with_proxies.mark_proxy_failed(mgr_with_proxies.proxies[1])
        proxy_list = mgr_with_proxies.get_proxy_list()

        statuses = [p["status"] for p in proxy_list]
        assert statuses[0] == "active"
        assert statuses[1] == "failed"
        assert statuses[2] == "active"

    def test_required_fields_present(self, mgr_with_proxies):
        """Each entry has the required keys."""
        for item in mgr_with_proxies.get_proxy_list():
            assert "endpoint" in item
            assert "host" in item
            assert "port" in item
            assert "username" in item
            assert "status" in item


# ---------------------------------------------------------------------------
# clear_all / clear_failed_proxies
# ---------------------------------------------------------------------------


class TestClearMethods:
    """Tests for clear_all and clear_failed_proxies."""

    def test_clear_all_removes_everything(self, mgr_with_proxies):
        """clear_all empties proxies, failed list, and resets index."""
        mgr_with_proxies.mark_proxy_failed(mgr_with_proxies.proxies[0])
        mgr_with_proxies.clear_all()

        assert len(mgr_with_proxies.proxies) == 0
        assert len(mgr_with_proxies.failed_proxies) == 0
        assert mgr_with_proxies.current_proxy_index == 0

    def test_clear_failed_preserves_proxies(self, mgr_with_proxies):
        """clear_failed_proxies clears only the failed list."""
        mgr_with_proxies.mark_proxy_failed(mgr_with_proxies.proxies[0])
        mgr_with_proxies.clear_failed_proxies()

        assert len(mgr_with_proxies.proxies) == 3
        assert len(mgr_with_proxies.failed_proxies) == 0


# ---------------------------------------------------------------------------
# allocate_next / reset_allocation_index
# ---------------------------------------------------------------------------


class TestAllocateNext:
    """Tests for NetNutProxyManager.allocate_next()."""

    def test_empty_proxies_returns_none(self, mgr):
        """allocate_next returns None with no proxies."""
        assert mgr.allocate_next() is None

    def test_sequential_allocation(self, mgr_with_proxies):
        """allocate_next returns proxies in order."""
        p1 = mgr_with_proxies.allocate_next()
        p2 = mgr_with_proxies.allocate_next()

        assert p1["endpoint"] == mgr_with_proxies.proxies[0]["endpoint"]
        assert p2["endpoint"] == mgr_with_proxies.proxies[1]["endpoint"]

    def test_skip_failed_proxy(self, mgr_with_proxies):
        """allocate_next skips proxies in the failed list."""
        mgr_with_proxies.failed_proxies.append(mgr_with_proxies.proxies[1]["endpoint"])
        p1 = mgr_with_proxies.allocate_next()
        p2 = mgr_with_proxies.allocate_next()

        assert p1["endpoint"] == mgr_with_proxies.proxies[0]["endpoint"]
        assert p2["endpoint"] == mgr_with_proxies.proxies[2]["endpoint"]

    def test_all_failed_resets_and_returns(self, mgr_with_proxies):
        """allocate_next resets failed list when all proxies are failed."""
        for p in mgr_with_proxies.proxies:
            mgr_with_proxies.mark_proxy_failed(p)

        result = mgr_with_proxies.allocate_next()

        assert result is not None
        assert len(mgr_with_proxies.failed_proxies) == 0


class TestResetAllocationIndex:
    """Tests for NetNutProxyManager.reset_allocation_index()."""

    def test_resets_to_zero(self, mgr_with_proxies):
        """reset_allocation_index sets _allocation_index back to 0."""
        mgr_with_proxies.allocate_next()
        mgr_with_proxies.allocate_next()
        assert mgr_with_proxies._allocation_index == 2

        mgr_with_proxies.reset_allocation_index()

        assert mgr_with_proxies._allocation_index == 0


# ---------------------------------------------------------------------------
# load_from_database
# ---------------------------------------------------------------------------


class TestLoadFromDatabase:
    """Tests for NetNutProxyManager.load_from_database()."""

    @pytest.mark.asyncio
    async def test_successful_load_from_database(self, mgr):
        """Proxies from database are loaded into the manager."""
        db_proxies = [
            {"id": 1, "server": "gw.netnut.net", "port": 5959, "username": "u1", "password": "p1"},
            {"id": 2, "server": "gw2.netnut.net", "port": 6060, "username": "u2", "password": "p2"},
        ]

        mock_repo = MagicMock()
        mock_repo.get_active = AsyncMock(return_value=db_proxies)

        mock_repo_class = MagicMock(return_value=mock_repo)

        with patch.dict(
            "sys.modules",
            {"src.repositories.proxy_repository": MagicMock(ProxyRepository=mock_repo_class)},
        ):
            db = MagicMock()
            count = await mgr.load_from_database(db)

        assert count == 2
        assert len(mgr.proxies) == 2

    @pytest.mark.asyncio
    async def test_load_from_database_exception_returns_zero(self, mgr):
        """Exception during database load returns 0."""
        mock_module = MagicMock()
        mock_module.ProxyRepository = MagicMock(side_effect=Exception("db error"))

        with patch.dict("sys.modules", {"src.repositories.proxy_repository": mock_module}):
            db = MagicMock()
            count = await mgr.load_from_database(db)

        assert count == 0
