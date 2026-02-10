"""Configuration loader with YAML and environment variable support."""

import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

from src.core.config_version_checker import check_config_version

logger = logging.getLogger(__name__)

# Critical environment variables that must be set in production
CRITICAL_ENV_VARS: frozenset[str] = frozenset({
    "ENCRYPTION_KEY",
    "API_SECRET_KEY",
    "VFS_ENCRYPTION_KEY",
    "DATABASE_URL",
})


def _get_environment() -> str:
    """
    Get the current environment.
    
    Returns:
        Environment name in lowercase
    """
    return os.getenv("ENV", "production").lower()


def _is_production_environment(env: str) -> bool:
    """
    Check if the environment is production.
    
    Args:
        env: Environment name
        
    Returns:
        True if production environment, False otherwise
    """
    return env not in ("development", "dev", "local", "testing", "test")


def load_env_variables() -> None:
    """Load environment variables from .env file."""
    # Load from project root
    env_path = Path(__file__).parent.parent.parent / ".env"
    
    if env_path.exists():
        load_dotenv(env_path)
        logger.debug(f"Loaded environment variables from {env_path}")


def substitute_env_vars(value: Any) -> Any:
    """
    Recursively substitute environment variables in configuration values.

    Args:
        value: Configuration value (string, dict, list, etc.)

    Returns:
        Value with environment variables substituted
        
    Raises:
        ValueError: If a critical env var is missing in production
    """
    if isinstance(value, str):
        # Find ${VAR_NAME} patterns and replace with environment variable
        pattern = r"\$\{([^}]+)\}"
        matches = re.findall(pattern, value)
        env = _get_environment()
        is_production = _is_production_environment(env)
        
        for match in matches:
            env_value = os.getenv(match)
            
            # Check if this is a critical environment variable
            if env_value is None and match in CRITICAL_ENV_VARS:
                if is_production:
                    raise ValueError(
                        f"CRITICAL: Environment variable '{match}' is required in production "
                        f"but not set. This is a security risk. Please set {match} in your "
                        f".env file or environment."
                    )
                else:
                    logger.warning(
                        f"Critical environment variable '{match}' is not set in development mode. "
                        f"Using empty string. Set {match} for full functionality."
                    )
                    env_value = ""
            elif env_value is None:
                # Non-critical variable
                logger.debug(f"Environment variable '{match}' not set, using empty string")
                env_value = ""
            
            value = value.replace(f"${{{match}}}", env_value)
        return value
    elif isinstance(value, dict):
        return {k: substitute_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [substitute_env_vars(item) for item in value]
    else:
        return value


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file with environment variable substitution.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist (production mode)
        yaml.YAMLError: If YAML is invalid
    """
    # Load environment variables first
    load_env_variables()
    
    env = _get_environment()
    is_production = _is_production_environment(env)

    # Check if config exists, otherwise use example
    config_file = Path(config_path)
    if not config_file.exists():
        if is_production:
            # In production, never fall back to example config - fail fast
            raise FileNotFoundError(
                f"CRITICAL: Configuration file not found: {config_path}. "
                f"Running in {env} environment. Example config fallback is disabled "
                f"in production for security. Please create a proper config file."
            )
        else:
            # In development, allow fallback with warning
            example_config = Path("config/config.example.yaml")
            if example_config.exists():
                logger.warning(
                    f"Config file not found: {config_path}. Falling back to example config "
                    f"in {env} environment. This is allowed in development but would fail "
                    f"in production."
                )
                config_file = example_config
            else:
                raise FileNotFoundError(
                    f"Config file not found: {config_path} and no example config available"
                )
    
    logger.info(f"Loading config from {config_file} in {env} environment")

    # Load YAML
    with open(config_file, "r", encoding="utf-8") as f:
        config_data: Any = yaml.safe_load(f)

    # Substitute environment variables
    config: Dict[str, Any] = (
        substitute_env_vars(config_data) if isinstance(config_data, dict) else {}
    )

    # Validate configuration version
    check_config_version(config)

    return config


def get_config_value(config: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    Get a nested configuration value using dot notation.

    Args:
        config: Configuration dictionary
        path: Dot-separated path (e.g., "vfs.base_url")
        default: Default value if path doesn't exist

    Returns:
        Configuration value or default
    """
    keys = path.split(".")
    value = config

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


@lru_cache(maxsize=1)
def load_selectors(config_path: str = "config/selectors.yaml") -> Dict[str, Dict[str, Any]]:
    """
    Load selectors from YAML config file with caching.

    Args:
        config_path: Path to selectors YAML file

    Returns:
        Dictionary of selector groups
    """
    path = Path(config_path)
    if not path.exists():
        logger.warning(f"Selectors config not found: {config_path}, using defaults")
        return {}

    with open(path, "r", encoding="utf-8") as f:
        selectors = yaml.safe_load(f)

    # Count total selectors
    total = 0
    if isinstance(selectors, dict):
        for value in selectors.values():
            if isinstance(value, dict):
                total += len(value)

    logger.info(f"Loaded {total} selectors from {config_path}")
    return selectors if isinstance(selectors, dict) else {}


def get_config_selector(group: str, name: str, default: str = "") -> str:
    """
    Get a specific selector by group and name from config/selectors.yaml.

    Note: This function is for reading selectors from YAML config files.
    For runtime selector management with AI repair and learning, use
    CountryAwareSelectorManager from src/utils/selectors.py instead.

    Args:
        group: Selector group (e.g., 'login', 'appointment')
        name: Selector name
        default: Default value if not found

    Returns:
        Selector string
    """
    selectors = load_selectors()
    group_selectors = selectors.get(group, {})

    if isinstance(group_selectors, dict):
        selector = group_selectors.get(name)
        # Handle both simple strings and objects with primary/fallbacks
        if isinstance(selector, dict) and "primary" in selector:
            primary = selector["primary"]
            if isinstance(primary, str):
                return primary
        elif isinstance(selector, str):
            return selector

    return default
