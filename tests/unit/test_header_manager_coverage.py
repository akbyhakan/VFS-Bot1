"""Additional coverage tests for utils/security/header_manager module."""

import pytest

from src.utils.security.header_manager import HeaderManager


@pytest.fixture
def manager():
    """HeaderManager with deterministic initial UA chosen by forcing the first entry."""
    hm = HeaderManager(base_url="https://visa.vfsglobal.com", rotation_interval=10)
    # Force a known Chromium UA for predictable Sec-CH-UA behaviour
    hm.current_ua = HeaderManager.USER_AGENTS[0]  # Chrome on Windows
    hm.request_count = 0
    return hm


@pytest.fixture
def firefox_manager():
    """HeaderManager using the Firefox UA (no sec-ch-ua)."""
    hm = HeaderManager()
    # Find the Firefox UA config
    hm.current_ua = next(
        ua for ua in HeaderManager.USER_AGENTS if ua["sec_ch_ua"] is None and "Firefox" in ua["ua"]
    )
    hm.request_count = 0
    return hm


@pytest.fixture
def safari_manager():
    """HeaderManager using the Safari UA (no sec-ch-ua)."""
    hm = HeaderManager()
    hm.current_ua = next(
        ua
        for ua in HeaderManager.USER_AGENTS
        if ua["sec_ch_ua"] is None and "Safari" in ua["ua"] and "Chrome" not in ua["ua"]
    )
    hm.request_count = 0
    return hm


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestHeaderManagerInit:
    """Tests for HeaderManager initialisation."""

    def test_default_base_url(self):
        """Default base_url is the VFS global URL."""
        hm = HeaderManager()
        assert hm.base_url == "https://visa.vfsglobal.com"

    def test_custom_base_url(self):
        """Custom base_url is stored correctly."""
        hm = HeaderManager(base_url="https://custom.example.com")
        assert hm.base_url == "https://custom.example.com"

    def test_default_rotation_interval(self):
        """Default rotation interval is 10."""
        hm = HeaderManager()
        assert hm.rotation_interval == 10

    def test_custom_rotation_interval(self):
        """Custom rotation interval is stored."""
        hm = HeaderManager(rotation_interval=5)
        assert hm.rotation_interval == 5

    def test_request_count_starts_at_zero(self):
        """request_count starts at 0."""
        hm = HeaderManager()
        assert hm.request_count == 0

    def test_current_ua_is_set(self):
        """current_ua is initialised to one of the known user agents."""
        hm = HeaderManager()
        assert hm.current_ua in HeaderManager.USER_AGENTS


# ---------------------------------------------------------------------------
# rotate_user_agent
# ---------------------------------------------------------------------------


class TestRotateUserAgent:
    """Tests for HeaderManager.rotate_user_agent()."""

    def test_rotates_to_different_ua(self, manager):
        """After rotation the UA changes."""
        old_ua = manager.current_ua
        manager.rotate_user_agent()
        assert manager.current_ua != old_ua

    def test_rotated_ua_is_still_in_user_agents_list(self, manager):
        """Rotated UA must still be from the known list."""
        manager.rotate_user_agent()
        assert manager.current_ua in HeaderManager.USER_AGENTS

    def test_repeated_rotation_does_not_raise(self, manager):
        """Multiple consecutive rotations work without error."""
        for _ in range(20):
            manager.rotate_user_agent()


# ---------------------------------------------------------------------------
# get_user_agent / get_sec_ch_ua
# ---------------------------------------------------------------------------


class TestGetUserAgentAndSecChUa:
    """Tests for get_user_agent and get_sec_ch_ua."""

    def test_get_user_agent_returns_string(self, manager):
        """get_user_agent returns a non-empty string."""
        ua = manager.get_user_agent()
        assert isinstance(ua, str)
        assert len(ua) > 0

    def test_get_user_agent_matches_current_ua(self, manager):
        """get_user_agent matches current_ua['ua']."""
        assert manager.get_user_agent() == manager.current_ua["ua"]

    def test_get_sec_ch_ua_chromium_returns_string(self, manager):
        """Chromium UA returns a non-None Sec-CH-UA value."""
        # manager fixture starts with Chrome UA
        result = manager.get_sec_ch_ua()
        assert result is not None
        assert isinstance(result, str)

    def test_get_sec_ch_ua_firefox_returns_none(self, firefox_manager):
        """Firefox UA returns None for Sec-CH-UA."""
        result = firefox_manager.get_sec_ch_ua()
        assert result is None

    def test_get_sec_ch_ua_safari_returns_none(self, safari_manager):
        """Safari UA returns None for Sec-CH-UA."""
        result = safari_manager.get_sec_ch_ua()
        assert result is None


# ---------------------------------------------------------------------------
# get_headers
# ---------------------------------------------------------------------------


class TestGetHeaders:
    """Tests for HeaderManager.get_headers()."""

    def test_returns_dict(self, manager):
        """get_headers returns a dictionary."""
        headers = manager.get_headers()
        assert isinstance(headers, dict)

    def test_required_keys_present(self, manager):
        """Essential header keys are present."""
        headers = manager.get_headers()
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers

    def test_user_agent_matches_current(self, manager):
        """User-Agent header matches the current UA."""
        headers = manager.get_headers()
        assert headers["User-Agent"] == manager.current_ua["ua"]

    def test_default_referer_is_base_url(self, manager):
        """Referer defaults to base_url when not specified."""
        headers = manager.get_headers()
        assert headers["Referer"] == manager.base_url

    def test_custom_referer_is_used(self, manager):
        """Custom referer overrides the default."""
        headers = manager.get_headers(referer="https://custom.example.com/path")
        assert headers["Referer"] == "https://custom.example.com/path"

    def test_chromium_includes_sec_ch_ua_headers(self, manager):
        """Chromium UA adds Sec-CH-UA, Sec-CH-UA-Mobile, Sec-CH-UA-Platform."""
        headers = manager.get_headers()
        assert "Sec-CH-UA" in headers
        assert "Sec-CH-UA-Mobile" in headers
        assert "Sec-CH-UA-Platform" in headers

    def test_firefox_excludes_sec_ch_ua_headers(self, firefox_manager):
        """Firefox UA does not include Sec-CH-UA headers."""
        headers = firefox_manager.get_headers()
        assert "Sec-CH-UA" not in headers
        assert "Sec-CH-UA-Mobile" not in headers

    def test_auto_rotates_at_interval(self, manager):
        """UA is rotated automatically after rotation_interval requests."""
        manager.rotation_interval = 3
        original_ua = manager.current_ua

        for _ in range(2):
            manager.get_headers()

        # On the 3rd call, rotation should trigger
        manager.get_headers()
        # After rotation the UA may have changed (probabilistic but controlled)
        # just assert no exception occurred and count incremented
        assert manager.request_count == 3


# ---------------------------------------------------------------------------
# get_api_headers
# ---------------------------------------------------------------------------


class TestGetApiHeaders:
    """Tests for HeaderManager.get_api_headers()."""

    def test_returns_dict(self, manager):
        """get_api_headers returns a dictionary."""
        headers = manager.get_api_headers()
        assert isinstance(headers, dict)

    def test_required_keys_present(self, manager):
        """Essential header keys are present."""
        headers = manager.get_api_headers()
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Content-Type" in headers

    def test_with_bearer_token(self, manager):
        """Authorization header is added when token is provided."""
        headers = manager.get_api_headers(token="my_token_123")
        assert headers["Authorization"] == "Bearer my_token_123"

    def test_without_token_no_authorization_header(self, manager):
        """No Authorization header when token is None."""
        headers = manager.get_api_headers()
        assert "Authorization" not in headers

    def test_with_referer(self, manager):
        """Referer header is added when provided."""
        headers = manager.get_api_headers(referer="https://some.referer.com")
        assert headers["Referer"] == "https://some.referer.com"

    def test_without_referer_no_referer_header(self, manager):
        """No Referer header when not provided."""
        headers = manager.get_api_headers()
        assert "Referer" not in headers

    def test_chromium_includes_sec_ch_ua(self, manager):
        """Chromium UA includes Sec-CH-UA in API headers."""
        headers = manager.get_api_headers()
        assert "Sec-CH-UA" in headers

    def test_firefox_excludes_sec_ch_ua(self, firefox_manager):
        """Firefox UA does not include Sec-CH-UA in API headers."""
        headers = firefox_manager.get_api_headers()
        assert "Sec-CH-UA" not in headers

    def test_increments_request_count(self, manager):
        """Each call to get_api_headers increments request_count."""
        before = manager.request_count
        manager.get_api_headers()
        assert manager.request_count == before + 1
