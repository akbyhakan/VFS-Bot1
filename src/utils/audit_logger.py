"""Audit logging for security-sensitive operations."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict
from enum import Enum

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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AuditLogger:
    """
    Audit logger for tracking security-sensitive operations.

    Features:
    - Automatic sensitive data masking
    - Database persistence
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

    def __init__(self, db=None):
        self.db = db
        self._buffer = []
        self._buffer_size = 100

    async def log(
        self,
        action: AuditAction,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
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
        )

        # Log to standard logger
        log_level = logging.INFO if success else logging.WARNING
        logger.log(
            log_level,
            f"AUDIT: {action.value} | user={username or user_id} | "
            f"ip={ip_address} | success={success}",
        )

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

        sanitized = {}
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

    async def _persist(self, entry: AuditEntry) -> None:
        """Persist audit entry to database."""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO audit_log 
                        (action, user_id, username, ip_address, user_agent, details, timestamp, success)
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
        self, limit: int = 100, action: Optional[AuditAction] = None, user_id: Optional[int] = None
    ) -> list:
        """Get recent audit entries."""
        if not self.db:
            return [e.to_dict() for e in self._buffer[-limit:]]

        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    query = "SELECT * FROM audit_log WHERE 1=1"
                    params = []

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


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(db=None) -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(db)
    elif db and _audit_logger.db is None:
        _audit_logger.db = db
    return _audit_logger
