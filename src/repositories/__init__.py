"""Repository pattern implementation."""

from .appointment_history_repository import AppointmentHistory, AppointmentHistoryRepository
from .appointment_repository import Appointment, AppointmentRepository
from .appointment_request_repository import AppointmentRequest, AppointmentRequestRepository
from .audit_log_repository import AuditLogEntry, AuditLogRepository
from .base import BaseRepository
from .log_repository import LogEntry, LogRepository
from .payment_repository import PaymentCard, PaymentRepository
from .proxy_repository import Proxy, ProxyRepository
from .token_blacklist_repository import TokenBlacklistEntry, TokenBlacklistRepository
from .user_repository import User, UserRepository
from .webhook_repository import Webhook, WebhookRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "User",
    "Appointment",
    "AppointmentRepository",
    "LogEntry",
    "LogRepository",
    "PaymentCard",
    "PaymentRepository",
    "AppointmentRequest",
    "AppointmentRequestRepository",
    "AppointmentHistory",
    "AppointmentHistoryRepository",
    "AuditLogEntry",
    "AuditLogRepository",
    "TokenBlacklistEntry",
    "TokenBlacklistRepository",
    "Webhook",
    "WebhookRepository",
    "Proxy",
    "ProxyRepository",
]
