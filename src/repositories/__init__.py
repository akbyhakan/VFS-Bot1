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
from .user_entity import User
from .user_read_repository import UserReadRepository
from .user_repository import UserRepository
from .user_write_repository import UserWriteRepository
from .webhook_repository import Webhook, WebhookRepository

__all__ = [
    "AccountPoolRepository",
    "BaseRepository",
    "DropdownCacheRepository",
    "UserRepository",
    "User",
    "UserReadRepository",
    "UserWriteRepository",
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
