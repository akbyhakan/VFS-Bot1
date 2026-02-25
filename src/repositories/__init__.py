"""Repository pattern implementation."""

from .account_pool_repository import AccountPoolRepository
from .appointment_history_repository import AppointmentHistory, AppointmentHistoryRepository
from .appointment_repository import Appointment, AppointmentRepository
from .appointment_request_repository import AppointmentRequest, AppointmentRequestRepository
from .audit_log_repository import AuditLogEntry, AuditLogRepository
from .base import BaseRepository
from .dropdown_cache_repository import DropdownCacheRepository
from .log_repository import LogEntry, LogRepository
from .payment_repository import PaymentCard, PaymentRepository
from .proxy_repository import Proxy, ProxyRepository
from .token_blacklist_repository import TokenBlacklistEntry, TokenBlacklistRepository
from .webhook_repository import Webhook, WebhookRepository

from .user_repository import User, UserRepository

__all__ = [
    "AccountPoolRepository",
    "UserRepository",
    "User",
    "BaseRepository",
    "DropdownCacheRepository",
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
