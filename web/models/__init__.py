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
from .payment import PaymentCardRequest, PaymentCardResponse, PaymentInitiateRequest
from .proxy import ProxyCreateRequest, ProxyResponse, ProxyUpdateRequest
from .users import UserCreateRequest, UserModel, UserUpdateRequest

__all__ = [
    # Auth models
    "LoginRequest",
    "TokenResponse",
    # Bot models
    "BotCommand",
    "StatusUpdate",
    # User models
    "UserCreateRequest",
    "UserUpdateRequest",
    "UserModel",
    # Appointment models
    "AppointmentPersonRequest",
    "AppointmentRequestCreate",
    "AppointmentPersonResponse",
    "AppointmentRequestResponse",
    # Payment models
    "PaymentCardRequest",
    "PaymentCardResponse",
    "PaymentInitiateRequest",
    # Proxy models
    "ProxyCreateRequest",
    "ProxyUpdateRequest",
    "ProxyResponse",
    # Common models
    "WebhookUrlsResponse",
    "CountryResponse",
]
