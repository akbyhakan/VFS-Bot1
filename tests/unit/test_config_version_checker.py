"""Unit tests for configuration version checking."""

import pytest

from src.core.config_version_checker import (
    CURRENT_CONFIG_VERSION,
    SUPPORTED_CONFIG_VERSIONS,
    check_config_version,
)
from src.core.exceptions import ConfigurationError


class TestConfigVersionChecker:
    """Test suite for config version validation."""

    def test_current_version_is_supported(self):
        """Test that current version is in supported versions."""
        assert CURRENT_CONFIG_VERSION in SUPPORTED_CONFIG_VERSIONS

    def test_current_version_value(self):
        """Test that current version has expected value."""
        assert CURRENT_CONFIG_VERSION == "2.0"

    def test_supported_versions_contains_expected(self):
        """Test that supported versions include all expected versions."""
        assert "1.0" in SUPPORTED_CONFIG_VERSIONS
        assert "2.0" in SUPPORTED_CONFIG_VERSIONS

    def test_check_version_current_version(self, caplog):
        """Test validation passes for current version."""
        config = {"config_version": "2.0", "vfs": {}}
        check_config_version(config)  # Should not raise

    def test_check_version_supported_old_version(self, caplog):
        """Test validation passes for old but supported version with warning."""
        config = {"config_version": "1.0", "vfs": {}}
        check_config_version(config)  # Should not raise
        assert "outdated" in caplog.text.lower()

    def test_check_version_missing_field(self, caplog):
        """Test validation handles missing version field gracefully."""
        config = {"vfs": {}, "notification": {}}
        check_config_version(config)  # Should not raise
        assert "does not have a 'config_version' field" in caplog.text

    def test_check_version_unsupported_version(self):
        """Test validation raises error for unsupported version."""
        config = {"config_version": "3.0", "vfs": {}}
        with pytest.raises(ConfigurationError) as exc_info:
            check_config_version(config)

        error = exc_info.value
        assert "Unsupported configuration version: 3.0" in str(error)
        assert "3.0" in error.details.get("config_version", "")

    def test_check_version_invalid_type(self):
        """Test validation raises error for non-string version."""
        config = {"config_version": 2.0, "vfs": {}}
        with pytest.raises(ConfigurationError) as exc_info:
            check_config_version(config)

        error = exc_info.value
        assert "must be a string" in str(error)

    def test_check_version_none_value(self, caplog):
        """Test validation handles None value gracefully."""
        config = {"config_version": None, "vfs": {}}
        check_config_version(config)  # Should not raise
        assert "does not have a 'config_version' field" in caplog.text

    def test_check_version_empty_config(self, caplog):
        """Test validation handles empty config gracefully."""
        config = {}
        check_config_version(config)  # Should not raise
        assert "does not have a 'config_version' field" in caplog.text

    def test_error_details_for_unsupported_version(self):
        """Test error details are properly populated."""
        config = {"config_version": "99.0", "vfs": {}}
        with pytest.raises(ConfigurationError) as exc_info:
            check_config_version(config)

        error = exc_info.value
        assert error.details["config_version"] == "99.0"
        assert "supported_versions" in error.details
        assert "current_version" in error.details
        assert error.details["current_version"] == CURRENT_CONFIG_VERSION

    def test_version_list_type(self):
        """Test that SUPPORTED_CONFIG_VERSIONS is a frozenset."""
        assert isinstance(SUPPORTED_CONFIG_VERSIONS, frozenset)

    def test_version_constant_is_final(self):
        """Test that version constants are properly typed."""
        assert isinstance(CURRENT_CONFIG_VERSION, str)
