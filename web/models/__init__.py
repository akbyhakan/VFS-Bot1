"""Pydantic models for VFS-Bot web application."""

# Re-export all models for convenience
from .appointments import (
    AppointmentPersonRequest,
    AppointmentPersonResponse,
    AppointmentRequestCreate,
    AppointmentRequestResponse,
)
from .auth import LoginRequest, TokenResponse
from .bot import BotCommand, StatusUpdate
from .common import CountryResponse, WebhookUrlsResponse
from .payment import PaymentCardRequest, PaymentCardResponse
from .proxy import ProxyCreateRequest, ProxyResponse, ProxyUpdateRequest
from .vfs_accounts import VFSAccountCreateRequest, VFSAccountModel, VFSAccountUpdateRequest

__all__ = [
    # Auth models
    "LoginRequest",
    "TokenResponse",
    # Bot models
    "BotCommand",
    "StatusUpdate",
    # VFS Account models
    "VFSAccountCreateRequest",
    "VFSAccountUpdateRequest",
    "VFSAccountModel",
    # Appointment models
    "AppointmentPersonRequest",
    "AppointmentRequestCreate",
    "AppointmentPersonResponse",
    "AppointmentRequestResponse",
    # Payment models
    "PaymentCardRequest",
    "PaymentCardResponse",
    # Proxy models
    "ProxyCreateRequest",
    "ProxyUpdateRequest",
    "ProxyResponse",
    # Common models
    "WebhookUrlsResponse",
    "CountryResponse",
]
