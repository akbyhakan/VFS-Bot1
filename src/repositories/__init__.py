"""Repository pattern implementation."""

from .base import BaseRepository
from .user_repository import User, UserRepository
from .appointment_repository import Appointment, AppointmentRepository
from .log_repository import LogEntry, LogRepository
from .payment_repository import PaymentCard, PaymentRepository
from .appointment_request_repository import AppointmentRequest, AppointmentRequestRepository
from .appointment_history_repository import AppointmentHistory, AppointmentHistoryRepository
from .audit_log_repository import AuditLogEntry, AuditLogRepository
from .token_blacklist_repository import TokenBlacklistEntry, TokenBlacklistRepository
from .webhook_repository import Webhook, WebhookRepository
from .proxy_repository import Proxy, ProxyRepository

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
