"""Configuration version compatibility checking."""

from typing import Any, Dict, Final

from loguru import logger

from src.core.exceptions import ConfigurationError

# Current configuration schema version
CURRENT_CONFIG_VERSION: Final[str] = "2.0"

# Supported configuration versions (backward compatibility)
SUPPORTED_CONFIG_VERSIONS: Final[frozenset[str]] = frozenset({
    "1.0",
    "2.0",
})


def check_config_version(config: Dict[str, Any]) -> None:
    """
    Validate configuration version for compatibility.
    
    Checks if the config version is supported and logs appropriate warnings
    for old but supported versions. Raises ConfigurationError for unsupported
    versions.
    
    Args:
        config: Configuration dictionary loaded from YAML
        
    Raises:
        ConfigurationError: If config version is not supported
        
    Example:
        >>> config = {"config_version": "2.0", "vfs": {...}}
        >>> check_config_version(config)  # No error
        
        >>> config = {"config_version": "3.0", "vfs": {...}}
        >>> check_config_version(config)  # Raises ConfigurationError
    """
    config_version = config.get("config_version")
    
    # Handle missing version field gracefully
    if config_version is None:
        logger.warning(
            "Configuration file does not have a 'config_version' field. "
            f"Please add 'config_version: {CURRENT_CONFIG_VERSION}' to your config.yaml. "
            "Continuing with backward compatibility mode."
        )
        return
    
    # Ensure version is a string
    if not isinstance(config_version, str):
        raise ConfigurationError(
            f"Configuration version must be a string, got {type(config_version).__name__}",
            details={"config_version": config_version}
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
            }
        )
    
    # Warn about old but supported versions
    if config_version != CURRENT_CONFIG_VERSION:
        logger.warning(
            f"Configuration version {config_version} is supported but outdated. "
            f"Current version is {CURRENT_CONFIG_VERSION}. "
            "Consider updating your config.yaml to the latest schema."
        )
    else:
        logger.debug(f"Configuration version {config_version} is current.")
