"""Configuration loader with YAML and environment variable support.

DEPRECATED: This module is deprecated. Use src.core.config_loader instead.
This file exists only for backward compatibility and will be removed in a future version.
"""

import warnings
from src.core.config_loader import (  # noqa: F401
    load_env_variables,
    substitute_env_vars,
    load_config,
    get_config_value,
)

warnings.warn(
    "src.config_loader is deprecated. Use src.core.config_loader instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export for backward compatibility
__all__ = ["load_env_variables", "substitute_env_vars", "load_config", "get_config_value"]
