"""Structured logging configuration — delegates to src.core.logger.

This module is kept for backward compatibility.  All real logging setup
lives in ``src.core.logger`` which uses Loguru.  Importing from here
still works so existing code does not break.

Migration guide:
    # Old (still works)
    from src.core.logging_config import setup_logging, JSONFormatter

    # Preferred
    from src.core.logger import setup_structured_logging, JSONFormatter
"""

import warnings

from src.core.logger import JSONFormatter, setup_structured_logging

__all__ = ["JSONFormatter", "setup_logging"]


def setup_logging(level=None, json_format=None):
    """Thin wrapper kept for backward compatibility.

    Delegates to :func:`src.core.logger.setup_structured_logging`.
    New code should import ``setup_structured_logging`` directly.
    
    Note: The deprecation warning is emitted once per unique call site
    by Python's default warning filters.
    """
    warnings.warn(
        "setup_logging() is deprecated — use setup_structured_logging() from "
        "src.core.logger instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    import os

    level = level or os.getenv("LOG_LEVEL", "INFO")
    json_format = (
        json_format if json_format is not None
        else os.getenv("LOG_FORMAT", "text") == "json"
    )
    setup_structured_logging(level=level, json_format=json_format)
