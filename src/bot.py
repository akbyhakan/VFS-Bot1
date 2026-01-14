"""
DEPRECATED: This module is kept for backward compatibility.
Use src.services.bot_service.VFSBot instead.
"""

import warnings
from src.services.bot_service import VFSBot

warnings.warn(
    "src.bot module is deprecated. Use src.services.bot_service instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["VFSBot"]
