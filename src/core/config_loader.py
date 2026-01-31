"""Configuration loader with YAML and environment variable support."""

import os
import re
import logging
from pathlib import Path
from typing import Any, Dict
from functools import lru_cache

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_env_variables() -> None:
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def substitute_env_vars(value: Any) -> Any:
    """
    Recursively substitute environment variables in configuration values.

    Args:
        value: Configuration value (string, dict, list, etc.)

    Returns:
        Value with environment variables substituted
    """
    if isinstance(value, str):
        # Find ${VAR_NAME} patterns and replace with environment variable
        pattern = r"\$\{([^}]+)\}"
        matches = re.findall(pattern, value)
        for match in matches:
            env_value = os.getenv(match, "")
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
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML is invalid
    """
    # Load environment variables first
    load_env_variables()

    # Check if config exists, otherwise use example
    config_file = Path(config_path)
    if not config_file.exists():
        example_config = Path("config/config.example.yaml")
        if example_config.exists():
            config_file = example_config
        else:
            raise FileNotFoundError(f"Config file not found: {config_path}")

    # Load YAML
    with open(config_file, "r", encoding="utf-8") as f:
        config_data: Any = yaml.safe_load(f)

    # Substitute environment variables
    config: Dict[str, Any] = (
        substitute_env_vars(config_data) if isinstance(config_data, dict) else {}
    )

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


def get_selector(group: str, name: str, default: str = "") -> str:
    """
    Get a specific selector by group and name.

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
            return selector["primary"]
        elif isinstance(selector, str):
            return selector

    return default
