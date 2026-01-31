"""Tests for feature flags system."""

import os
import pytest
from src.core.feature_flags import FeatureFlags, FeatureFlag


class TestFeatureFlags:
    """Test feature flags functionality."""

    def setup_method(self):
        """Clear cache before each test."""
        FeatureFlags.clear_cache()
        # Clear environment variables
        for flag in FeatureFlag:
            env_var = f"FEATURE_{flag.value.upper()}"
            if env_var in os.environ:
                del os.environ[env_var]

    def test_default_feature_states(self):
        """Test that features have correct default states."""
        # Core features should be enabled by default
        assert FeatureFlags.is_enabled(FeatureFlag.CAPTCHA_SOLVING)
        assert FeatureFlags.is_enabled(FeatureFlag.NOTIFICATIONS)
        assert FeatureFlags.is_enabled(FeatureFlag.AUTO_BOOKING)

        # AI repair should be disabled by default
        assert not FeatureFlags.is_enabled(FeatureFlag.AI_SELECTOR_REPAIR)

    def test_feature_from_environment_variable(self):
        """Test reading feature flag from environment variable."""
        os.environ["FEATURE_AUTO_BOOKING"] = "false"
        FeatureFlags.clear_cache()

        assert not FeatureFlags.is_enabled(FeatureFlag.AUTO_BOOKING)

    def test_feature_environment_variable_variations(self):
        """Test different boolean representations in environment variables."""
        # Test "true"
        os.environ["FEATURE_DETAILED_LOGGING"] = "true"
        FeatureFlags.clear_cache()
        assert FeatureFlags.is_enabled(FeatureFlag.DETAILED_LOGGING)

        # Test "1"
        os.environ["FEATURE_DETAILED_LOGGING"] = "1"
        FeatureFlags.clear_cache()
        assert FeatureFlags.is_enabled(FeatureFlag.DETAILED_LOGGING)

        # Test "yes"
        os.environ["FEATURE_DETAILED_LOGGING"] = "yes"
        FeatureFlags.clear_cache()
        assert FeatureFlags.is_enabled(FeatureFlag.DETAILED_LOGGING)

        # Test "false"
        os.environ["FEATURE_DETAILED_LOGGING"] = "false"
        FeatureFlags.clear_cache()
        assert not FeatureFlags.is_enabled(FeatureFlag.DETAILED_LOGGING)

    def test_programmatic_feature_set(self):
        """Test programmatically setting feature flags."""
        FeatureFlags.set(FeatureFlag.PARALLEL_SLOT_CHECKING, True)
        assert FeatureFlags.is_enabled(FeatureFlag.PARALLEL_SLOT_CHECKING)

        FeatureFlags.set(FeatureFlag.PARALLEL_SLOT_CHECKING, False)
        assert not FeatureFlags.is_enabled(FeatureFlag.PARALLEL_SLOT_CHECKING)

    def test_get_all_features(self):
        """Test getting all feature flags."""
        all_flags = FeatureFlags.get_all()

        assert isinstance(all_flags, dict)
        assert FeatureFlag.CAPTCHA_SOLVING.value in all_flags
        assert FeatureFlag.NOTIFICATIONS.value in all_flags
        assert all(isinstance(v, bool) for v in all_flags.values())

    def test_get_enabled_features(self):
        """Test getting list of enabled features."""
        enabled = FeatureFlags.get_enabled_features()

        assert isinstance(enabled, set)
        assert FeatureFlag.CAPTCHA_SOLVING.value in enabled

    def test_get_disabled_features(self):
        """Test getting list of disabled features."""
        disabled = FeatureFlags.get_disabled_features()

        assert isinstance(disabled, set)
        # AI repair is disabled by default
        assert FeatureFlag.AI_SELECTOR_REPAIR.value in disabled

    def test_require_feature_success(self):
        """Test requiring an enabled feature."""
        # Should not raise
        FeatureFlags.require(FeatureFlag.NOTIFICATIONS)

    def test_require_feature_failure(self):
        """Test requiring a disabled feature raises exception."""
        with pytest.raises(RuntimeError, match="Required feature"):
            FeatureFlags.require(FeatureFlag.AI_SELECTOR_REPAIR)

    def test_cache_invalidation(self):
        """Test that cache is properly invalidated."""
        # First check creates cache entry
        assert FeatureFlags.is_enabled(FeatureFlag.AUTO_BOOKING)

        # Change environment variable
        os.environ["FEATURE_AUTO_BOOKING"] = "false"

        # Without clearing cache, should still return cached value
        assert FeatureFlags.is_enabled(FeatureFlag.AUTO_BOOKING)

        # After clearing cache, should read new value
        FeatureFlags.clear_cache()
        assert not FeatureFlags.is_enabled(FeatureFlag.AUTO_BOOKING)
