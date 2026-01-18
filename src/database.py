"""
DEPRECATED: Use src.models.database instead.

This module is kept for backward compatibility only.
All database functionality has been moved to src.models.database.
"""

import warnings

# Issue deprecation warning when this module is imported
warnings.warn(
    "src.database is deprecated. Use src.models.database instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from the new location for backward compatibility
from src.models.database import Database, require_connection

__all__ = ["Database", "require_connection"]
