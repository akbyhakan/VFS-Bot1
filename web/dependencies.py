"""Shared dependencies, models, and utilities for VFS-Bot web application."""

import asyncio
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Set

from fastapi import Depends, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

from src.core.auth import verify_token
from src.models.database import Database
from src.models.db_factory import DatabaseFactory

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
    """Payment card request model."""

    card_holder_name: str = Field(..., min_length=2, max_length=100)
    card_number: str = Field(..., min_length=13, max_length=19, pattern=r"^\d{13,19}$")
    expiry_month: str = Field(..., pattern=r"^(0[1-9]|1[0-2])$")
    expiry_year: str = Field(..., pattern=r"^\d{2,4}$")
    cvv: str = Field(..., min_length=3, max_length=4, pattern=r"^\d{3,4}$")

    @field_validator("card_number")
    @classmethod
    def validate_luhn(cls, v: str) -> str:
        """Validate card number using Luhn algorithm."""
        # Remove any spaces or dashes (should already be digits only due to pattern)
        clean_number = v.replace(" ", "").replace("-", "")
        
        # Luhn algorithm implementation
        total = 0
        is_even = False
        
        for i in range(len(clean_number) - 1, -1, -1):
            digit = int(clean_number[i])
            
            if is_even:
                digit *= 2
                if digit > 9:
                    digit -= 9
            
            total += digit
            is_even = not is_even
        
        if total % 10 != 0:
            raise ValueError("Invalid card number (failed Luhn check)")
        
        return v

    @field_validator("card_holder_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate card holder name contains only letters and spaces."""
        trimmed = v.strip()
        # Allow letters (including Turkish characters) and spaces only
        if not all(c.isalpha() or c.isspace() for c in trimmed):
            raise ValueError("Card holder name must contain only letters and spaces")
        return trimmed


class PaymentCardResponse(BaseModel):
    """Payment card response model (masked)."""

    id: int
    card_holder_name: str
    card_number_masked: str
    expiry_month: str
    expiry_year: str
    created_at: str


class PaymentInitiateRequest(BaseModel):
    """Payment initiation request."""

    appointment_id: int


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


# Proxy Models
class ProxyCreateRequest(BaseModel):
    """Proxy creation request model."""

    server: str
    port: int
    username: str
    password: str

    class Config:
        json_schema_extra = {
            "example": {
                "server": "gw.netnut.net",
                "port": 5959,
                "username": "ntnt_user",
                "password": "your_password",
            }
        }


class ProxyUpdateRequest(BaseModel):
    """Proxy update request model."""

    server: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


class ProxyResponse(BaseModel):
    """Proxy response model (password excluded)."""

    id: int
    server: str
    port: int
    username: str
    is_active: bool
    failure_count: int
    last_used: Optional[str] = None
    created_at: str
    updated_at: str


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
    """Thread-safe WebSocket connection manager with connection limits and rate limiting."""

    MAX_CONNECTIONS = int(os.getenv("MAX_WEBSOCKET_CONNECTIONS", "1000"))
    MESSAGES_PER_SECOND = 10  # Token bucket rate
    BURST_SIZE = 20  # Maximum burst capacity

    def __init__(self):
        """Initialize connection manager."""
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        # Rate limiting: token bucket for each connection
        self._rate_limits: Dict[WebSocket, Dict[str, float]] = {}

    def _check_rate_limit(self, websocket: WebSocket) -> bool:
        """
        Check if message is within rate limit using token bucket algorithm.

        Args:
            websocket: WebSocket connection to check

        Returns:
            True if message is allowed, False if rate limited
        """
        now = time.monotonic()

        # Initialize bucket if not exists
        if websocket not in self._rate_limits:
            self._rate_limits[websocket] = {
                "tokens": self.BURST_SIZE,
                "last_update": now,
            }

        bucket = self._rate_limits[websocket]
        elapsed = now - bucket["last_update"]

        # Add tokens based on elapsed time
        bucket["tokens"] = min(
            self.BURST_SIZE, bucket["tokens"] + elapsed * self.MESSAGES_PER_SECOND
        )
        bucket["last_update"] = now

        # Check if we have at least 1 token
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True

        return False

    async def connect(self, websocket: WebSocket) -> bool:
        """
        Connect a new WebSocket client with connection limit enforcement.

        Args:
            websocket: WebSocket connection

        Returns:
            True if connection was accepted, False if limit reached
        """
        # Note: WebSocket should already be accepted before calling this method
        async with self._lock:
            if len(self._connections) >= self.MAX_CONNECTIONS:
                logger.warning(
                    f"WebSocket connection limit reached ({self.MAX_CONNECTIONS}). "
                    "Rejecting new connection."
                )
                return False
            self._connections.add(websocket)
            # Initialize rate limit bucket
            self._rate_limits[websocket] = {
                "tokens": self.BURST_SIZE,
                "last_update": time.monotonic(),
            }
            logger.debug(f"WebSocket connected. Active connections: {len(self._connections)}")
            return True

    async def disconnect(self, websocket: WebSocket):
        """
        Disconnect a WebSocket client.

        Args:
            websocket: WebSocket connection
        """
        async with self._lock:
            self._connections.discard(websocket)
            # Clean up rate limit data
            self._rate_limits.pop(websocket, None)
            logger.debug(f"WebSocket disconnected. Active connections: {len(self._connections)}")

    async def send_message(self, websocket: WebSocket, message: dict) -> bool:
        """
        Send message to a WebSocket client with rate limiting.

        Args:
            websocket: WebSocket connection
            message: Message dictionary to send

        Returns:
            True if message was sent, False if rate limited
        """
        if not self._check_rate_limit(websocket):
            logger.warning("WebSocket message rate limit exceeded")
            return False

        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            return False

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
                # Note: Broadcast doesn't check rate limit to ensure
                # important updates reach all clients
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
                    self._rate_limits.pop(conn, None)


# Thread-safe metrics class
class ThreadSafeMetrics:
    """Thread-safe metrics storage."""

    def __init__(self):
        self._lock = threading.Lock()
        self._data = {
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

    def increment(self, key: str, value: int = 1) -> None:
        """Increment a metric value thread-safely."""
        with self._lock:
            if key in self._data and isinstance(self._data[key], (int, float)):
                self._data[key] += value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a metric value thread-safely."""
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a metric value thread-safely."""
        with self._lock:
            self._data[key] = value

    def add_error(self, error_type: str) -> None:
        """Add an error to metrics thread-safely."""
        with self._lock:
            if "errors" not in self._data:
                self._data["errors"] = {}
            if error_type not in self._data["errors"]:
                self._data["errors"][error_type] = 0
            self._data["errors"][error_type] += 1

    def to_dict(self) -> Dict[str, Any]:
        """Return a copy of metrics data thread-safely."""
        with self._lock:
            return self._data.copy()

    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dictionary-style item assignment."""
        self.set(key, value)

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style item access."""
        with self._lock:
            return self._data[key]

    def __contains__(self, key: str) -> bool:
        """Allow 'in' operator for checking key existence."""
        with self._lock:
            return key in self._data


# Global state instances
bot_state = ThreadSafeBotState()
manager = ConnectionManager()
metrics = ThreadSafeMetrics()


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


async def get_db() -> AsyncIterator[Database]:
    """
    FastAPI dependency — singleton DB via DatabaseFactory.

    Yields:
        Connected database instance

    Note:
        This is a singleton pattern. Do NOT close the database connection
        in route handlers. DatabaseFactory.close_instance() handles shutdown.
    """
    db = await DatabaseFactory.ensure_connected()
    yield db
    # Do NOT close — DatabaseFactory.close_instance() handles shutdown


async def broadcast_message(message: Dict[str, Any]) -> None:
    """
    Broadcast message to all connected WebSocket clients.

    Args:
        message: Message dictionary to broadcast
    """
    await manager.broadcast(message)
