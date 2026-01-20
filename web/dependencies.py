"""Shared dependencies, models, and utilities for VFS-Bot web application."""

import asyncio
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set, List

from fastapi import Depends, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from src.core.auth import verify_token

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer()


# Pydantic Models
class BotCommand(BaseModel):
    """Bot command model."""

    action: str
    config: Dict[str, Any] = {}


class StatusUpdate(BaseModel):
    """Status update model."""

    status: str
    message: str
    timestamp: str


class LoginRequest(BaseModel):
    """Login request model."""

    username: str
    password: str


class TokenResponse(BaseModel):
    """Token response model."""

    access_token: str
    token_type: str = "bearer"


class PaymentCardRequest(BaseModel):
    """Payment card request model - CVV removed for PCI-DSS compliance."""

    card_holder_name: str
    card_number: str
    expiry_month: str
    expiry_year: str


class PaymentCardResponse(BaseModel):
    """Payment card response model (masked)."""

    id: int
    card_holder_name: str
    card_number_masked: str
    expiry_month: str
    expiry_year: str
    created_at: str


class PaymentInitiateRequest(BaseModel):
    """Payment initiation with runtime CVV."""

    appointment_id: int
    cvv: str  # Only in memory, never stored


class WebhookUrlsResponse(BaseModel):
    """Webhook URLs response model."""

    appointment_webhook: str
    payment_webhook: str
    base_url: str


class UserCreateRequest(BaseModel):
    """User creation request."""

    email: str
    password: str  # VFS password for login
    phone: str
    first_name: str
    last_name: str
    center_name: str
    visa_category: str
    visa_subcategory: str
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    """User update request."""

    email: Optional[str] = None
    password: Optional[str] = None  # VFS password
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    center_name: Optional[str] = None
    visa_category: Optional[str] = None
    visa_subcategory: Optional[str] = None
    is_active: Optional[bool] = None


class UserModel(BaseModel):
    """User response model."""

    id: int
    email: str
    phone: str = ""  # Default to empty string for backward compatibility
    first_name: str = ""  # Default to empty string for backward compatibility
    last_name: str = ""  # Default to empty string for backward compatibility
    center_name: str
    visa_category: str
    visa_subcategory: str
    is_active: bool
    created_at: str
    updated_at: str


class AppointmentPersonRequest(BaseModel):
    """Appointment person request model."""

    first_name: str
    last_name: str
    gender: str  # "female" | "male"
    nationality: str = "Turkey"
    birth_date: str  # Format: DD/MM/YYYY
    passport_number: str
    passport_issue_date: str  # Format: DD/MM/YYYY
    passport_expiry_date: str  # Format: DD/MM/YYYY
    phone_code: str = "90"
    phone_number: str  # Without leading 0
    email: str
    is_child_with_parent: bool = False  # Child checkbox


class AppointmentRequestCreate(BaseModel):
    """Appointment request creation model."""

    country_code: str
    visa_category: str
    visa_subcategory: str
    centres: List[str]
    preferred_dates: List[str]  # Format: DD/MM/YYYY
    person_count: int
    persons: List[AppointmentPersonRequest]


class AppointmentPersonResponse(BaseModel):
    """Appointment person response model."""

    id: int
    first_name: str
    last_name: str
    gender: str
    nationality: str
    birth_date: str
    passport_number: str
    passport_issue_date: str
    passport_expiry_date: str
    phone_code: str
    phone_number: str
    email: str
    is_child_with_parent: bool


class AppointmentRequestResponse(BaseModel):
    """Appointment request response model."""

    id: int
    country_code: str
    visa_category: str
    visa_subcategory: str
    centres: List[str]
    preferred_dates: List[str]
    person_count: int
    status: str
    created_at: str
    completed_at: Optional[str] = None
    persons: List[AppointmentPersonResponse]


class CountryResponse(BaseModel):
    """Country response model."""

    code: str
    name_en: str
    name_tr: str


# Thread-safe state management
@dataclass
class ThreadSafeBotState:
    """Thread-safe wrapper for bot state."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _state: Dict[str, Any] = field(
        default_factory=lambda: {
            "running": False,
            "status": "stopped",
            "last_check": None,
            "slots_found": 0,
            "appointments_booked": 0,
            "active_users": 0,
            "logs": deque(maxlen=500),
        }
    )

    def get(self, key: str, default: Any = None) -> Any:
        """Thread-safe get."""
        with self._lock:
            return self._state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Thread-safe set."""
        with self._lock:
            self._state[key] = value

    def __getitem__(self, key: str) -> Any:
        with self._lock:
            return self._state[key]

    def __setitem__(self, key: str, value: Any) -> None:
        with self._lock:
            self._state[key] = value


# WebSocket connection manager
class ConnectionManager:
    """Thread-safe WebSocket connection manager."""

    def __init__(self):
        """Initialize connection manager."""
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """
        Connect a new WebSocket client.

        Args:
            websocket: WebSocket connection
        """
        # Note: WebSocket should already be accepted before calling this method
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket):
        """
        Disconnect a WebSocket client.

        Args:
            websocket: WebSocket connection
        """
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: dict):
        """
        Broadcast message to all connected clients.

        Args:
            message: Message dictionary to broadcast
        """
        async with self._lock:
            connections = self._connections.copy()

        disconnected = []
        for connection in connections:
            try:
                await connection.send_json(message)
            except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
                logger.debug(f"WebSocket connection closed during broadcast: {e}")
                disconnected.append(connection)
            except Exception as e:
                logger.error(f"Unexpected error broadcasting to WebSocket client: {e}")
                disconnected.append(connection)

        if disconnected:
            async with self._lock:
                for conn in disconnected:
                    self._connections.discard(conn)


# Global state instances
bot_state = ThreadSafeBotState()
manager = ConnectionManager()

# Metrics storage
metrics = {
    "requests_total": 0,
    "requests_success": 0,
    "requests_failed": 0,
    "slots_checked": 0,
    "slots_found": 0,
    "appointments_booked": 0,
    "captchas_solved": 0,
    "errors": {},
    "start_time": datetime.now(timezone.utc),
}


# Dependency functions
async def verify_jwt_token(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> Dict[str, Any]:
    """
    Verify JWT token from Authorization header.

    Args:
        credentials: HTTP authorization credentials

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid
    """
    token = credentials.credentials
    return verify_token(token)


async def broadcast_message(message: Dict[str, Any]) -> None:
    """
    Broadcast message to all connected WebSocket clients.

    Args:
        message: Message dictionary to broadcast
    """
    await manager.broadcast(message)
