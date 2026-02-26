"""Configuration version compatibility checking.

The config schema version (CURRENT_CONFIG_VERSION) is independent of the
application version (__version__ in src/__init__.py). This version only
changes when the config.yaml structure has breaking changes such as
renamed or removed keys, or new required sections. Minor application
releases that do not alter the config schema do NOT bump this version.

Versioning policy:
    - Config version major bump (1.0 -> 2.0): Breaking config schema changes
    - Application version (__version__) follows SemVer independently
"""

from typing import Any, Dict, Final

from loguru import logger

from src.core.exceptions import ConfigurationError

# Current configuration schema version — single source of truth.
# Only bump when config.yaml schema has breaking/structural changes.
# This is independent of __version__ (app SemVer) in src/__init__.py.
CURRENT_CONFIG_VERSION: Final[str] = "2.0"

# Supported configuration versions
SUPPORTED_CONFIG_VERSIONS: Final[frozenset[str]] = frozenset(
    {
        "2.0",
    }
)


def check_config_version(config: Dict[str, Any]) -> None:
    """
    Validate configuration version for compatibility.

    Checks if the config version is supported and logs appropriate warnings
    for old but supported versions. Raises ConfigurationError for unsupported
    versions or missing version field.

    Args:
        config: Configuration dictionary loaded from YAML

    Raises:
        ConfigurationError: If config version is not supported or missing

    Example:
        >>> config = {"config_version": "2.0", "vfs": {...}}
        >>> check_config_version(config)  # No error

        >>> config = {"config_version": "3.0", "vfs": {...}}
        >>> check_config_version(config)  # Raises ConfigurationError
    """
    config_version = config.get("config_version")

    # Require version field to be present
    if config_version is None:
        raise ConfigurationError(
            f"Configuration file is missing the required 'config_version' field. "
            f"Please add 'config_version: {CURRENT_CONFIG_VERSION}' to your config.yaml.",
            details={"current_version": CURRENT_CONFIG_VERSION},
        )

    # Ensure version is a string
    if not isinstance(config_version, str):
        raise ConfigurationError(
            f"Configuration version must be a string, got {type(config_version).__name__}",
            details={"config_version": config_version},
        )

    # Check if version is supported
    if config_version not in SUPPORTED_CONFIG_VERSIONS:
        raise ConfigurationError(
            f"Unsupported configuration version: {config_version}. "
            f"Supported versions: {', '.join(sorted(SUPPORTED_CONFIG_VERSIONS))}. "
            f"Current version: {CURRENT_CONFIG_VERSION}. "
            "Please update your config.yaml or upgrade the application.",
            details={
                "config_version": config_version,
                "supported_versions": list(SUPPORTED_CONFIG_VERSIONS),
                "current_version": CURRENT_CONFIG_VERSION,
            },
        )

    logger.debug(f"Configuration version {config_version} is current.")
