"""Request context utilities for structured logging with request IDs."""

import uuid
import logging
from contextvars import ContextVar
from typing import Optional


# Context variable for storing request ID across async calls
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def _generate_request_id() -> str:
    """
    Generate a new request ID.

    Returns:
        12-character hex string from UUID
    """
    return str(uuid.uuid4())[:12]


def get_request_id() -> str:
    """
    Get current request ID or generate new one.

    Returns:
        Request ID (12-character hex string for lower collision risk)
    """
    rid = request_id_var.get()
    if not rid:
        rid = _generate_request_id()
        request_id_var.set(rid)
    return rid


def set_request_id(request_id: Optional[str] = None) -> str:
    """
    Set request ID for current context.

    Args:
        request_id: Optional request ID to set. If None, generates a new one.

    Returns:
        The request ID that was set
    """
    rid = request_id or _generate_request_id()
    request_id_var.set(rid)
    return rid


def clear_request_id() -> None:
    """Clear request ID from current context."""
    request_id_var.set("")


class RequestIdFilter(logging.Filter):
    """
    Logging filter that adds request_id to log records.

    Usage:
        import logging
        from src.utils.request_context import RequestIdFilter

        logger = logging.getLogger(__name__)
        logger.addFilter(RequestIdFilter())

        # In log format:
        # '%(asctime)s [%(request_id)s] %(levelname)s: %(message)s'
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add request_id to log record.

        Args:
            record: Log record to modify

        Returns:
            Always True (don't filter out any records)
        """
        record.request_id = get_request_id() or "-"
        return True


def get_logger_with_request_id(name: str) -> logging.Logger:
    """
    Get a logger with RequestIdFilter already applied.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance with request ID filter
    """
    logger = logging.getLogger(name)

    # Check if filter already added to avoid duplicates
    has_filter = any(isinstance(f, RequestIdFilter) for f in logger.filters)
    if not has_filter:
        logger.addFilter(RequestIdFilter())

    return logger
