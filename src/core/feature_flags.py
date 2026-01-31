"""Feature flags for graceful degradation and A/B testing."""

import logging
import os
from typing import Dict, Set
from enum import Enum

logger = logging.getLogger(__name__)


class FeatureFlag(str, Enum):
    """Available feature flags."""

    # Core features
    CAPTCHA_SOLVING = "captcha_solving"
    NOTIFICATIONS = "notifications"
    AUTO_BOOKING = "auto_booking"

    # Advanced features
    WEBHOOK_SIGNATURE_VALIDATION = "webhook_signature_validation"
    RATE_LIMIT_HEADERS = "rate_limit_headers"
    AI_SELECTOR_REPAIR = "ai_selector_repair"
    SELECTOR_LEARNING = "selector_learning"

    # Monitoring & Debugging
    DETAILED_LOGGING = "detailed_logging"
    METRICS_COLLECTION = "metrics_collection"
    CIRCUIT_BREAKER = "circuit_breaker"

    # Experimental features
    PARALLEL_SLOT_CHECKING = "parallel_slot_checking"
    ADVANCED_ANTI_DETECTION = "advanced_anti_detection"


class FeatureFlags:
    """
    Feature flag management system for graceful degradation.

    Features can be enabled/disabled via environment variables:
    - FEATURE_<NAME>=true/false

    Example:
        FEATURE_CAPTCHA_SOLVING=true
        FEATURE_AUTO_BOOKING=false
    """

    # Default states for features
    _defaults: Dict[str, bool] = {
        # Core features (enabled by default)
        FeatureFlag.CAPTCHA_SOLVING: True,
        FeatureFlag.NOTIFICATIONS: True,
        FeatureFlag.AUTO_BOOKING: True,
        # Advanced features (enabled by default)
        FeatureFlag.WEBHOOK_SIGNATURE_VALIDATION: True,
        FeatureFlag.RATE_LIMIT_HEADERS: True,
        FeatureFlag.AI_SELECTOR_REPAIR: False,  # Disabled by default (requires API key)
        FeatureFlag.SELECTOR_LEARNING: True,
        # Monitoring (enabled by default)
        FeatureFlag.DETAILED_LOGGING: False,
        FeatureFlag.METRICS_COLLECTION: True,
        FeatureFlag.CIRCUIT_BREAKER: True,
        # Experimental (disabled by default)
        FeatureFlag.PARALLEL_SLOT_CHECKING: False,
        FeatureFlag.ADVANCED_ANTI_DETECTION: True,
    }

    # Cache for feature states
    _cache: Dict[str, bool] = {}

    @classmethod
    def is_enabled(cls, feature: str) -> bool:
        """
        Check if a feature is enabled.

        Args:
            feature: Feature flag name (use FeatureFlag enum values)

        Returns:
            True if feature is enabled

        Example:
            if FeatureFlags.is_enabled(FeatureFlag.AUTO_BOOKING):
                # Auto booking is enabled
                pass
        """
        # Check cache first
        if feature in cls._cache:
            return cls._cache[feature]

        # Get from environment variable
        env_var = f"FEATURE_{feature.upper()}"
        env_value = os.getenv(env_var)

        if env_value is not None:
            # Parse boolean from env var
            is_enabled = env_value.lower() in ("true", "1", "yes", "on")
            cls._cache[feature] = is_enabled
            return is_enabled

        # Use default value
        default = cls._defaults.get(feature, False)
        cls._cache[feature] = default
        return default

    @classmethod
    def set(cls, feature: str, enabled: bool) -> None:
        """
        Programmatically set a feature flag.

        Args:
            feature: Feature flag name
            enabled: Whether to enable the feature

        Note:
            This only affects the current process. For persistent changes,
            set environment variables.
        """
        cls._cache[feature] = enabled
        logger.info(f"Feature flag '{feature}' set to {enabled}")

    @classmethod
    def get_all(cls) -> Dict[str, bool]:
        """
        Get all feature flags and their states.

        Returns:
            Dictionary of feature flags and their enabled states
        """
        result = {}
        for feature in FeatureFlag:
            result[feature.value] = cls.is_enabled(feature.value)
        return result

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the feature flag cache."""
        cls._cache.clear()
        logger.debug("Feature flag cache cleared")

    @classmethod
    def get_enabled_features(cls) -> Set[str]:
        """
        Get set of all enabled features.

        Returns:
            Set of enabled feature names
        """
        return {feature.value for feature in FeatureFlag if cls.is_enabled(feature.value)}

    @classmethod
    def get_disabled_features(cls) -> Set[str]:
        """
        Get set of all disabled features.

        Returns:
            Set of disabled feature names
        """
        return {feature.value for feature in FeatureFlag if not cls.is_enabled(feature.value)}

    @classmethod
    def require(cls, feature: str) -> None:
        """
        Require a feature to be enabled, raise exception if not.

        Args:
            feature: Feature flag name

        Raises:
            RuntimeError: If feature is not enabled
        """
        if not cls.is_enabled(feature):
            raise RuntimeError(
                f"Required feature '{feature}' is not enabled. "
                f"Set FEATURE_{feature.upper()}=true to enable."
            )

    @classmethod
    def log_status(cls) -> None:
        """Log the current status of all feature flags."""
        enabled = cls.get_enabled_features()
        disabled = cls.get_disabled_features()

        logger.info("=== Feature Flags Status ===")
        logger.info(f"Enabled ({len(enabled)}): {', '.join(sorted(enabled))}")
        logger.info(f"Disabled ({len(disabled)}): {', '.join(sorted(disabled))}")


def get_feature_flags() -> FeatureFlags:
    """
    Get the feature flags instance.

    Returns:
        FeatureFlags instance
    """
    return FeatureFlags
