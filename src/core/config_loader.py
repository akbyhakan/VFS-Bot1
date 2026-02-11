"""Configuration loader with YAML and environment variable support."""

import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml
from dotenv import load_dotenv
from loguru import logger

from src.core.config_version_checker import check_config_version
from src.core.environment import Environment

# Critical environment variables that must be set in production
CRITICAL_ENV_VARS: frozenset[str] = frozenset({
    "ENCRYPTION_KEY",
    "API_SECRET_KEY",
    "VFS_ENCRYPTION_KEY",
    "DATABASE_URL",
})

# Sensitive configuration keys to mask in logs
SENSITIVE_CONFIG_KEYS: frozenset[str] = frozenset({
    "database_url",
    "password",
    "secret",
    "token",
    "api_key",
    "encryption_key",
    "vfs_encryption_key",
    "api_secret_key",
    "bearer",
    "auth",
    "credential",
})


def _get_environment() -> str:
    """
    Get the current environment.
    
    Returns:
        Environment name in lowercase
    """
    return Environment.current_raw()


def _is_production_environment(env: str) -> bool:
    """
    Check if the environment is production.
    
    Args:
        env: Environment name
        
    Returns:
        True if production environment, False otherwise
    """
    return env not in Environment._NON_PROD


def load_env_variables() -> None:
    """Load environment variables from .env file."""
    # Load from project root
    env_path = Path(__file__).parent.parent.parent / ".env"
    
    if env_path.exists():
        load_dotenv(env_path)
        logger.debug(f"Loaded environment variables from {env_path}")


def substitute_env_vars(value: Any, _env: str = None, _is_production: bool = None) -> Any:
    """
    Recursively substitute environment variables in configuration values.

    Args:
        value: Configuration value (string, dict, list, etc.)
        _env: Internal parameter - cached environment value (do not set manually)
        _is_production: Internal parameter - cached production check (do not set manually)

    Returns:
        Value with environment variables substituted
        
    Raises:
        ValueError: If a critical env var is missing in production
    """
    if isinstance(value, str):
        # Find ${VAR_NAME} patterns and replace with environment variable
        pattern = r"\$\{([^}]+)\}"
        matches = re.findall(pattern, value)
        if _env is None:
            _env = _get_environment()
            _is_production = _is_production_environment(_env)
        
        for match in matches:
            env_value = os.getenv(match)
            
            # Check if this is a critical environment variable
            if env_value is None and match in CRITICAL_ENV_VARS:
                if _is_production:
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
        if _env is None:
            _env = _get_environment()
            _is_production = _is_production_environment(_env)
        return {k: substitute_env_vars(v, _env, _is_production) for k, v in value.items()}
    elif isinstance(value, list):
        if _env is None:
            _env = _get_environment()
            _is_production = _is_production_environment(_env)
        return [substitute_env_vars(item, _env, _is_production) for item in value]
    else:
        return value


def _safe_config_summary(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a safe version of config dict with sensitive values masked for logging.
    
    This is a defense-in-depth measure to prevent accidental logging of secrets.
    Uses SENSITIVE_CONFIG_KEYS set to identify sensitive fields.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        New dictionary with sensitive values masked as "[REDACTED]"
    """
    if not isinstance(config, dict):
        return config
    
    safe_config: Dict[str, Any] = {}
    for key, value in config.items():
        key_lower = key.lower()
        
        # Check if key contains any sensitive pattern
        is_sensitive = any(pattern in key_lower for pattern in SENSITIVE_CONFIG_KEYS)
        
        if is_sensitive:
            safe_config[key] = "[REDACTED]"
        elif isinstance(value, dict):
            # Recursively mask nested dictionaries
            safe_config[key] = _safe_config_summary(value)
        elif isinstance(value, list):
            # Mask list items if they're dicts
            safe_config[key] = [
                _safe_config_summary(item) if isinstance(item, dict) else item 
                for item in value
            ]
        else:
            safe_config[key] = value
    
    return safe_config


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


# TTL-based cache for selectors (configurable via environment variable)
# Note: TTL is read once at module load time and cached for application lifetime
try:
    _SELECTORS_CACHE_TTL = int(os.getenv("SELECTORS_CACHE_TTL", "60"))  # seconds, default 60
    if _SELECTORS_CACHE_TTL <= 0:
        raise ValueError(f"SELECTORS_CACHE_TTL must be positive, got: {_SELECTORS_CACHE_TTL}")
except ValueError as e:
    logger.warning(
        f"Invalid SELECTORS_CACHE_TTL value: {os.getenv('SELECTORS_CACHE_TTL')}. "
        f"Must be a positive integer (seconds). Error: {e}. Using default: 60"
    )
    _SELECTORS_CACHE_TTL = 60
_selectors_cache: Optional[Tuple[float, Dict[str, Dict[str, Any]]]] = None
_selectors_cache_lock = threading.Lock()  # Thread-safe cache access


def invalidate_selectors_cache() -> None:
    """
    Invalidate the selectors cache.

    This function should be called after AI repair updates the selectors file
    to ensure the next call to load_selectors() reloads from disk.
    
    Thread-safe: Uses lock to prevent race conditions.
    """
    global _selectors_cache
    with _selectors_cache_lock:
        _selectors_cache = None
    logger.debug("Selectors cache invalidated")


def load_selectors(config_path: str = "config/selectors.yaml") -> Dict[str, Dict[str, Any]]:
    """
    Load selectors from YAML config file with TTL-based caching.

    Cache expires after _SELECTORS_CACHE_TTL seconds to allow AI Auto-Repair
    system to update selectors at runtime and have changes picked up.
    
    Thread-safe: Uses lock to prevent race conditions during cache updates.
    
    Note: Returns the cached dictionary directly (not a copy) for performance.
    Callers should treat the returned dictionary as read-only to avoid
    race conditions with concurrent access.

    Args:
        config_path: Path to selectors YAML file

    Returns:
        Dictionary of selector groups (read-only)
    """
    global _selectors_cache

    with _selectors_cache_lock:
        # Check if cache is still valid
        current_time = time.time()
        if _selectors_cache is not None:
            cache_time, cached_data = _selectors_cache
            if current_time - cache_time < _SELECTORS_CACHE_TTL:
                return cached_data

        # Cache expired or not set, reload from disk
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
        result = selectors if isinstance(selectors, dict) else {}

        # Update cache
        _selectors_cache = (current_time, result)
        return result


def get_config_selector(group: str, name: str, default: str = "") -> str:
    """
    Get a specific selector by group and name from config/selectors.yaml.

    Note: This function is for reading selectors from YAML config files.
    For runtime selector management with AI repair and learning, use
    CountryAwareSelectorManager from src.selector instead.

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
