"""Request context management for correlation tracking."""

import contextvars
import uuid
from typing import Optional

# Context variables for request tracking
correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'correlation_id', default=None
)
user_email: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'user_email', default=None
)


def get_correlation_id() -> str:
    """Get current correlation ID or generate new one."""
    cid = correlation_id.get()
    if cid is None:
        cid = str(uuid.uuid4())[:8]
        correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """Set correlation ID for current context."""
    correlation_id.set(cid)


def set_user_context(email: str) -> None:
    """Set user email for current context."""
    user_email.set(email)


def get_user_context() -> Optional[str]:
    """Get user email from current context."""
    return user_email.get()


class CorrelationLogFilter:
    """Logging filter that adds correlation ID to log records."""

    def filter(self, record):
        """Add correlation ID and user email to log record."""
        record.correlation_id = get_correlation_id()
        record.user_email = get_user_context() or "system"
        return True
