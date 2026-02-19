"""Centralized environment detection and configuration.

Single source of truth for environment-related logic across the application.
"""

import os
from typing import FrozenSet


class Environment:
    """Centralized environment configuration.

    This class eliminates DRY violations by providing a single source of truth
    for all environment detection logic across the application.
    """

    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    TESTING = "testing"
    LOCAL = "local"

    # All valid environment names (whitelist)
    VALID: FrozenSet[str] = frozenset(
        {"production", "staging", "development", "dev", "testing", "test", "local"}
    )

    # Non-production environments (used for relaxed security checks)
    _NON_PROD: FrozenSet[str] = frozenset({"development", "dev", "local", "testing", "test"})

    # Development-mode environments (for debug features like diagnose)
    _DEV_MODE: FrozenSet[str] = frozenset({"development", "dev", "local", "test", "testing"})

    @classmethod
    def current(cls) -> str:
        """Get the current environment name, validated and lowercased.

        Returns:
            Validated environment name. Defaults to 'production' for unknown values.
        """
        env = os.getenv("ENV", cls.PRODUCTION).lower()
        if env not in cls.VALID:
            return cls.PRODUCTION
        return env

    @classmethod
    def current_raw(cls) -> str:
        """Get the raw current environment name without validation fallback.

        Returns:
            Raw environment name in lowercase. Does NOT default unknown values to production.
            This is used when you need to detect and warn about unknown environments.
        """
        return os.getenv("ENV", cls.PRODUCTION).lower()

    @classmethod
    def is_production(cls) -> bool:
        """Check if the current environment is a production-like environment.

        Returns:
            True if the environment is NOT in the non-production set.
        """
        return cls.current() not in cls._NON_PROD

    @classmethod
    def is_development(cls) -> bool:
        """Check if the current environment is development mode.

        Returns:
            True if in a development/test/local environment.
        """
        return cls.current() in cls._DEV_MODE

    @classmethod
    def is_production_or_staging(cls) -> bool:
        """Check if the current environment is production or staging.

        Returns:
            True if environment is 'production' or 'staging'.
        """
        return cls.current() in (cls.PRODUCTION, cls.STAGING)

    @classmethod
    def is_testing(cls) -> bool:
        """Check if the current environment is testing mode.

        Returns:
            True if environment is 'testing' or 'test'.
        """
        return cls.current() in ("testing", "test")
