"""Tests for utils/user_agent_rotator module."""

import pytest
from src.utils.user_agent_rotator import UserAgentRotator


class TestUserAgentRotator:
    """Tests for UserAgentRotator."""

    def test_get_random_user_agent_format(self):
        """Test that get_random_user_agent returns valid format."""
        ua = UserAgentRotator.get_random_user_agent()
        assert isinstance(ua, str)
        assert "Mozilla/5.0" in ua
        assert "AppleWebKit/537.36" in ua
        assert "Chrome/" in ua
        assert "Safari/537.36" in ua

    def test_get_random_user_agent_varies(self):
        """Test that get_random_user_agent returns different values."""
        user_agents = [UserAgentRotator.get_random_user_agent() for _ in range(20)]
        # With 4 platforms and 5 versions, we should get some variety
        unique_agents = set(user_agents)
        assert len(unique_agents) > 1

    def test_get_random_user_agent_contains_platform(self):
        """Test that user agent contains one of the platforms."""
        ua = UserAgentRotator.get_random_user_agent()
        platforms = UserAgentRotator.PLATFORMS
        assert any(platform in ua for platform in platforms)

    def test_get_random_user_agent_contains_version(self):
        """Test that user agent contains one of the Chrome versions."""
        ua = UserAgentRotator.get_random_user_agent()
        versions = UserAgentRotator.CHROME_VERSIONS
        assert any(version in ua for version in versions)

    def test_get_user_agents_list_count(self):
        """Test that get_user_agents_list returns correct count."""
        agents = UserAgentRotator.get_user_agents_list()
        expected_count = len(UserAgentRotator.PLATFORMS) * len(UserAgentRotator.CHROME_VERSIONS)
        assert len(agents) == expected_count

    def test_get_user_agents_list_all_unique(self):
        """Test that all user agents in list are unique."""
        agents = UserAgentRotator.get_user_agents_list()
        assert len(agents) == len(set(agents))

    def test_get_user_agents_list_format(self):
        """Test that all user agents have correct format."""
        agents = UserAgentRotator.get_user_agents_list()
        for agent in agents:
            assert "Mozilla/5.0" in agent
            assert "AppleWebKit/537.36" in agent
            assert "Chrome/" in agent
            assert "Safari/537.36" in agent

    def test_get_user_agents_list_contains_all_platforms(self):
        """Test that list contains all platforms."""
        agents = UserAgentRotator.get_user_agents_list()
        for platform in UserAgentRotator.PLATFORMS:
            assert any(platform in agent for agent in agents)

    def test_get_user_agents_list_contains_all_versions(self):
        """Test that list contains all Chrome versions."""
        agents = UserAgentRotator.get_user_agents_list()
        for version in UserAgentRotator.CHROME_VERSIONS:
            assert any(version in agent for agent in agents)

    def test_chrome_versions_constant(self):
        """Test that CHROME_VERSIONS constant is defined."""
        assert hasattr(UserAgentRotator, "CHROME_VERSIONS")
        assert isinstance(UserAgentRotator.CHROME_VERSIONS, list)
        assert len(UserAgentRotator.CHROME_VERSIONS) > 0

    def test_platforms_constant(self):
        """Test that PLATFORMS constant is defined."""
        assert hasattr(UserAgentRotator, "PLATFORMS")
        assert isinstance(UserAgentRotator.PLATFORMS, list)
        assert len(UserAgentRotator.PLATFORMS) > 0

    def test_user_agent_includes_windows(self):
        """Test that some user agents include Windows platform."""
        agents = UserAgentRotator.get_user_agents_list()
        windows_agents = [a for a in agents if "Windows NT" in a]
        assert len(windows_agents) > 0

    def test_user_agent_includes_mac(self):
        """Test that some user agents include Mac platform."""
        agents = UserAgentRotator.get_user_agents_list()
        mac_agents = [a for a in agents if "Macintosh" in a]
        assert len(mac_agents) > 0
