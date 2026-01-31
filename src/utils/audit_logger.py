"""Audit logging for security-sensitive operations."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Union, Callable, TYPE_CHECKING
from dataclasses import dataclass, asdict
from enum import Enum
from functools import wraps
from pathlib import Path

if TYPE_CHECKING:
    from ..models.database import Database

logger = logging.getLogger(__name__)


class AuditAction(Enum):
    """Audit action types."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    APPOINTMENT_CREATED = "appointment_created"
    APPOINTMENT_BOOKED = "appointment_booked"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    PAYMENT_CARD_ADDED = "payment_card_added"
    PAYMENT_CARD_DELETED = "payment_card_deleted"
    CONFIG_CHANGED = "config_changed"
    BOT_STARTED = "bot_started"
    BOT_STOPPED = "bot_stopped"
    API_KEY_GENERATED = "api_key_generated"
    WEBHOOK_RECEIVED = "webhook_received"
    PASSWORD_CHANGED = "password_changed"
    DATA_EXPORTED = "data_exported"
    DATA_DELETED = "data_deleted"
    PERMISSION_CHANGED = "permission_changed"
    PROXY_ADDED = "proxy_added"
    PROXY_DELETED = "proxy_deleted"


@dataclass
class AuditEntry:
    """Audit log entry."""

    action: str
    user_id: Optional[int]
    username: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    details: Dict[str, Any]
    timestamp: str
    success: bool = True
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class AuditLogger:
    """
    Audit logger for tracking security-sensitive operations.

    Features:
    - Automatic sensitive data masking
    - Database persistence
    - JSONL file output for long-term storage
    - Structured logging
    """

    SENSITIVE_KEYS = {
        "password",
        "token",
        "api_key",
        "secret",
        "card_number",
        "cvv",
        "authorization",
        "cookie",
        "session",
    }

    def __init__(self, db: Optional["Database"] = None, log_file: Optional[str] = None):
        """
        Initialize audit logger.

        Args:
            db: Database instance for persistence
            log_file: Optional JSONL file path for audit logs
        """
        self.db = db
        self.log_file = Path(log_file) if log_file else None
        self._buffer: List[AuditEntry] = []
        self._buffer_size = 100

        # Create log file directory if needed
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

    async def log(
        self,
        action: AuditAction,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ) -> None:
        """
        Log an audit event.

        Args:
            action: The action being audited
            user_id: ID of the user performing the action
            username: Username of the user
            ip_address: IP address of the request
            user_agent: User agent string
            details: Additional details about the action
            success: Whether the action was successful
            resource_type: Type of resource affected (e.g., "user", "appointment")
            resource_id: ID of the resource affected
        """
        sanitized_details = self._sanitize(details or {})

        entry = AuditEntry(
            action=action.value,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            details=sanitized_details,
            timestamp=datetime.now(timezone.utc).isoformat(),
            success=success,
            resource_type=resource_type,
            resource_id=resource_id,
        )

        # Log to standard logger
        log_level = logging.INFO if success else logging.WARNING
        logger.log(
            log_level,
            f"AUDIT: {action.value} | user={username or user_id} | "
            f"ip={ip_address} | success={success}",
        )

        # Write to JSONL file if configured
        if self.log_file:
            await self._write_to_file(entry)

        # Persist to database if available
        if self.db:
            await self._persist(entry)
        else:
            self._buffer.append(entry)
            if len(self._buffer) >= self._buffer_size:
                logger.warning("Audit buffer full, removing oldest entries")
                # Keep only the newer half to avoid frequent trimming
                self._buffer = self._buffer[-self._buffer_size // 2 :]

    def _sanitize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive data in the details dictionary."""
        if not isinstance(data, dict):
            return data

        sanitized: Dict[str, Any] = {}
        for key, value in data.items():
            key_lower = key.lower()

            if any(sensitive in key_lower for sensitive in self.SENSITIVE_KEYS):
                if isinstance(value, str) and len(value) > 4:
                    sanitized[key] = value[:2] + "***" + value[-2:]
                else:
                    sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize(value)
            else:
                sanitized[key] = value

        return sanitized

    async def _write_to_file(self, entry: AuditEntry) -> None:
        """Write audit entry to JSONL file."""
        try:
            if self.log_file is not None:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(entry.to_json() + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit entry to file: {e}")

    async def _persist(self, entry: AuditEntry) -> None:
        """Persist audit entry to database."""
        try:
            if self.db is not None:
                async with self.db.get_connection() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            """
                            INSERT INTO audit_log
                        (action, user_id, username, ip_address, user_agent,
                         details, timestamp, success)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                            (
                                entry.action,
                                entry.user_id,
                                entry.username,
                                entry.ip_address,
                                entry.user_agent,
                                json.dumps(entry.details),
                                entry.timestamp,
                                entry.success,
                            ),
                        )
                    await conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist audit entry: {e}")
            self._buffer.append(entry)

    async def get_recent(
        self,
        limit: int = 100,
        action: Optional[AuditAction] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent audit entries."""
        if not self.db:
            return [e.to_dict() for e in self._buffer[-limit:]]

        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    query = "SELECT * FROM audit_log WHERE 1=1"
                    params: List[Union[str, int]] = []

                    if action:
                        query += " AND action = ?"
                        params.append(action.value)

                    if user_id:
                        query += " AND user_id = ?"
                        params.append(user_id)

                    query += " ORDER BY timestamp DESC LIMIT ?"
                    params.append(limit)

                    await cursor.execute(query, params)
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to fetch audit entries: {e}")
            return []


def audit(
    action: AuditAction, resource_type: Optional[str] = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for automatic audit logging of function calls.

    Args:
        action: Audit action type
        resource_type: Optional resource type being acted upon

    Usage:
        @audit(AuditAction.USER_CREATED, resource_type="user")
        async def create_user(user_data: dict):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract context from kwargs
            user_id = kwargs.get("user_id")
            username = kwargs.get("username")
            ip_address = kwargs.get("ip_address")

            audit_logger = get_audit_logger()
            success = True
            resource_id = None

            try:
                result = await func(*args, **kwargs)

                # Try to extract resource_id from result if it's a dict
                if isinstance(result, dict) and "id" in result:
                    resource_id = str(result["id"])

                return result
            except Exception as _e:
                success = False
                raise
            finally:
                # Log the action
                await audit_logger.log(
                    action=action,
                    user_id=user_id,
                    username=username,
                    ip_address=ip_address,
                    success=success,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details={"function": func.__name__},
                )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, we can't easily do async audit logging
            # So we just call the function normally
            logger.warning(f"Audit decorator used on sync function {func.__name__}")
            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(db: Any = None, log_file: Optional[str] = None) -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(db, log_file)
    elif db and _audit_logger.db is None:
        _audit_logger.db = db
    elif log_file and _audit_logger.log_file is None:
        _audit_logger.log_file = Path(log_file)
        _audit_logger.log_file.parent.mkdir(parents=True, exist_ok=True)
    return _audit_logger
