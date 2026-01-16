"""FastAPI web dashboard with WebSocket support for VFS-Bot."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Set, Optional
from datetime import datetime, timezone
from collections import deque

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.core.security import verify_api_key, generate_api_key
from src.core.auth import create_access_token, verify_token
from src.services.otp_webhook_routes import router as otp_router
from src.models.database import Database
from src.core.exceptions import ValidationError

security_scheme = HTTPBearer()

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="VFS-Bot Dashboard", version="2.0.0")

# Include OTP webhook router
app.include_router(otp_router)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount static files
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"

# Mount the new React frontend build directory
dist_dir = static_dir / "dist"
if dist_dir.exists():
    # Serve React app static assets
    app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")

# Mount other static files (for backward compatibility)
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates = Jinja2Templates(directory=str(templates_dir))

# Global state
bot_state = {
    "running": False,
    "status": "stopped",
    "last_check": None,
    "slots_found": 0,
    "appointments_booked": 0,
    "active_users": 0,
    "logs": deque(maxlen=500),  # Automatic size limit with deque
}

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


# WebSocket connections
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


manager = ConnectionManager()


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

    card_holder_name: str
    card_number: str
    expiry_month: str
    expiry_year: str
    cvv: str


class PaymentCardResponse(BaseModel):
    """Payment card response model (masked)."""

    id: int
    card_holder_name: str
    card_number_masked: str
    expiry_month: str
    expiry_year: str
    created_at: str


class WebhookUrlsResponse(BaseModel):
    """Webhook URLs response model."""

    appointment_webhook: str
    payment_webhook: str
    base_url: str


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


# API Routes start here


@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    """
    Get current bot status.

    Returns:
        Status dictionary
    """
    return {
        "running": bot_state["running"],
        "status": bot_state["status"],
        "last_check": bot_state["last_check"],
        "stats": {
            "slots_found": bot_state["slots_found"],
            "appointments_booked": bot_state["appointments_booked"],
            "active_users": bot_state["active_users"],
        },
    }


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for monitoring and container orchestration.

    Returns:
        Health status with system information
    """
    from src.utils.metrics import get_metrics

    db_healthy = await check_database_health()
    bot_metrics = await get_metrics()

    # Check if bot is experiencing errors
    snapshot = await bot_metrics.get_snapshot()

    # Configurable health threshold (default 50%)
    health_threshold = float(os.getenv("BOT_HEALTH_THRESHOLD", "50.0"))
    bot_healthy = snapshot.success_rate > health_threshold

    circuit_breaker_healthy = not (
        snapshot.circuit_breaker_trips > 0 and bot_state.get("running", False)
    )

    # Determine overall status based on component health
    if db_healthy and bot_healthy and circuit_breaker_healthy:
        overall_status = "healthy"
    elif db_healthy:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.1.0",
        "uptime_seconds": snapshot.uptime_seconds,
        "components": {
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
            },
            "bot": {
                "status": "healthy" if bot_healthy else "degraded",
                "running": bot_state.get("running", False),
                "success_rate": snapshot.success_rate,
            },
            "circuit_breaker": {
                "status": "healthy" if circuit_breaker_healthy else "open",
                "trips": snapshot.circuit_breaker_trips,
            },
            "notifications": {
                "status": "healthy",
            },
        },
        "metrics": {
            "total_checks": snapshot.total_checks,
            "slots_found": snapshot.slots_found,
            "appointments_booked": snapshot.appointments_booked,
            "active_users": snapshot.active_users,
        },
    }


async def check_database_health() -> bool:
    """
    Check database connectivity with actual query.

    Returns:
        True if database is healthy, False otherwise
    """
    try:
        from src.models.database import Database

        db = Database()
        await db.connect()
        try:
            async with db.get_connection(timeout=5.0) as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    result = await cursor.fetchone()
                    return result is not None
        finally:
            await db.close()
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


@app.get("/api/metrics")
async def get_bot_metrics() -> Dict[str, Any]:
    """
    Get detailed bot metrics.

    Returns:
        Comprehensive metrics dictionary
    """
    from src.utils.metrics import get_metrics

    bot_metrics = await get_metrics()
    return await bot_metrics.get_metrics_dict()


@app.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """
    Prometheus-compatible metrics endpoint.

    Returns:
        Metrics dictionary
    """
    from src.utils.metrics import get_metrics as get_bot_metrics_instance

    bot_metrics = await get_bot_metrics_instance()
    snapshot = await bot_metrics.get_snapshot()

    # Legacy compatibility with existing metrics structure
    uptime = (datetime.now(timezone.utc) - metrics["start_time"]).total_seconds()

    return {
        "uptime_seconds": uptime,
        "requests_total": metrics["requests_total"],
        "requests_success": metrics["requests_success"],
        "requests_failed": metrics["requests_failed"],
        "success_rate": metrics["requests_success"] / max(metrics["requests_total"], 1),
        "slots_checked": snapshot.total_checks,
        "slots_found": snapshot.slots_found,
        "appointments_booked": snapshot.appointments_booked,
        "captchas_solved": metrics["captchas_solved"],
        "errors_by_type": metrics["errors"],
        "bot_status": bot_state["status"],
        # New metrics from BotMetrics
        "circuit_breaker_trips": snapshot.circuit_breaker_trips,
        "active_users": snapshot.active_users,
        "avg_response_time_ms": snapshot.avg_response_time_ms,
        "requests_per_minute": snapshot.requests_per_minute,
    }


@app.get("/metrics/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics() -> str:
    """
    Prometheus text format metrics.

    Returns:
        Prometheus-formatted metrics
    """
    from src.utils.metrics import get_metrics

    bot_metrics = await get_metrics()
    return await bot_metrics.get_prometheus_metrics()


def increment_metric(name: str, count: int = 1) -> None:
    """Increment a metric counter."""
    if name in metrics:
        metrics[name] += count


@app.post("/api/bot/start")
@limiter.limit("5/minute")
async def start_bot(
    request: Request, command: BotCommand, api_key: dict = Depends(verify_api_key)
) -> Dict[str, str]:
    """
    Start the bot - requires authentication.

    Args:
        request: FastAPI request object (required for rate limiter)
        command: Bot command with configuration
        api_key: Verified API key metadata

    Returns:
        Response dictionary
    """
    if bot_state["running"]:
        return {"status": "error", "message": "Bot is already running"}

    bot_state["running"] = True
    bot_state["status"] = "running"

    await broadcast_message(
        {
            "type": "status",
            "data": {"running": True, "status": "running", "message": "Bot started successfully"},
        }
    )

    logger.info(f"Bot started via dashboard by {api_key.get('name', 'unknown')}")
    return {"status": "success", "message": "Bot started"}


@app.post("/api/bot/stop")
@limiter.limit("5/minute")
async def stop_bot(request: Request, api_key: dict = Depends(verify_api_key)) -> Dict[str, str]:
    """
    Stop the bot - requires authentication.

    Args:
        request: FastAPI request object (required for rate limiter)
        api_key: Verified API key metadata

    Returns:
        Response dictionary
    """
    if not bot_state["running"]:
        return {"status": "error", "message": "Bot is not running"}

    bot_state["running"] = False
    bot_state["status"] = "stopped"

    await broadcast_message(
        {
            "type": "status",
            "data": {"running": False, "status": "stopped", "message": "Bot stopped successfully"},
        }
    )

    logger.info(f"Bot stopped via dashboard by {api_key.get('name', 'unknown')}")
    return {"status": "success", "message": "Bot stopped"}


@app.get("/api/logs")
async def get_logs(
    limit: int = 100, token_data: Dict[str, Any] = Depends(verify_jwt_token)
) -> Dict[str, List[str]]:
    """
    Get recent logs - requires authentication.

    Args:
        limit: Maximum number of logs to return
        token_data: Verified token data

    Returns:
        Dictionary with logs list
    """
    logs_list = list(bot_state["logs"])
    return {"logs": logs_list[-limit:]}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.

    Authentication: Send token in first message as {"token": "your-jwt-token"}

    Args:
        websocket: WebSocket connection
    """
    await websocket.accept()

    try:
        # Wait for authentication message
        auth_data = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)

        if not isinstance(auth_data, dict) or "token" not in auth_data:
            await websocket.close(code=4001, reason="Authentication required")
            return

        token = auth_data.get("token")
        if not token:
            await websocket.close(code=4001, reason="Token missing")
            return

        # Verify token
        try:
            verify_token(token)
        except HTTPException:
            await websocket.close(code=4001, reason="Invalid token")
            return

    except asyncio.TimeoutError:
        await websocket.close(code=4001, reason="Authentication timeout")
        return
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        await websocket.close(code=4000, reason="Authentication error")
        return

    await manager.connect(websocket)

    # Send initial status
    await websocket.send_json(
        {"type": "status", "data": {"running": bot_state["running"], "status": bot_state["status"]}}
    )

    try:
        while True:
            # Keep connection alive and receive messages with timeout
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=60.0)
                logger.debug(f"Received WebSocket message: {data}")

                # Echo back (can add command handling here)
                await websocket.send_json({"type": "ack", "data": {"message": "Message received"}})
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await websocket.send_json({"type": "ping", "data": {}})
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket)


async def update_bot_stats(
    slots_found: int = None, appointments_booked: int = None, active_users: int = None
) -> None:
    """
    Update bot statistics and broadcast to clients.

    Args:
        slots_found: Number of slots found
        appointments_booked: Number of appointments booked
        active_users: Number of active users
    """
    if slots_found is not None:
        bot_state["slots_found"] = slots_found
    if appointments_booked is not None:
        bot_state["appointments_booked"] = appointments_booked
    if active_users is not None:
        bot_state["active_users"] = active_users

    bot_state["last_check"] = datetime.now().isoformat()

    await broadcast_message(
        {
            "type": "stats",
            "data": {
                "slots_found": bot_state["slots_found"],
                "appointments_booked": bot_state["appointments_booked"],
                "active_users": bot_state["active_users"],
                "last_check": bot_state["last_check"],
            },
        }
    )


async def add_log(message: str, level: str = "INFO") -> None:
    """
    Add a log message and broadcast to clients.

    Args:
        message: Log message
        level: Log level
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"

    bot_state["logs"].append(log_entry)
    # deque with maxlen=500 automatically removes oldest entries

    await broadcast_message(
        {"type": "log", "data": {"message": log_entry, "level": level, "timestamp": timestamp}}
    )


@app.post("/api/auth/generate-key")
async def create_api_key(secret: str) -> Dict[str, str]:
    """
    Generate API key with admin secret - one-time use endpoint.

    Args:
        secret: Admin secret from environment

    Returns:
        New API key

    Raises:
        HTTPException: If admin secret is invalid
    """
    admin_secret = os.getenv("ADMIN_SECRET")
    if not admin_secret or secret != admin_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    new_key = generate_api_key()
    return {"api_key": new_key, "note": "Save this key securely! It will not be shown again."}


@app.post("/api/auth/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, credentials: LoginRequest) -> TokenResponse:
    """
    Login endpoint - returns JWT token.

    Args:
        request: FastAPI request object (required for rate limiter)
        credentials: Username and password

    Returns:
        JWT access token

    Raises:
        HTTPException: If credentials are invalid or environment not configured
    """
    from src.core.auth import verify_password

    # Get credentials from environment - fail if not set
    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_username or not admin_password:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: ADMIN_USERNAME and ADMIN_PASSWORD must be set",
        )

    # Check username
    if credentials.username != admin_username:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check password - support both plaintext (for development) and hashed passwords
    password_valid = False
    if admin_password.startswith("$2b$"):
        # Hashed password (bcrypt format)
        password_valid = verify_password(credentials.password, admin_password)
    else:
        # Plaintext password - only allowed in development
        if os.getenv("ENV", "production").lower() == "development":
            logger.warning(
                "⚠️ SECURITY WARNING: Using plaintext password. Only allowed in development!"
            )
            password_valid = credentials.password == admin_password
        else:
            raise HTTPException(
                status_code=500,
                detail="Server configuration error: ADMIN_PASSWORD must be hashed in production. "
                'Use: python -c "from passlib.context import CryptContext; '
                "print(CryptContext(schemes=['bcrypt']).hash('your-password'))\"",
            )

    if not password_valid:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": credentials.username, "name": credentials.username}
    )

    return TokenResponse(access_token=access_token)


@app.get("/api/selector-health")
async def get_selector_health() -> Dict[str, Any]:
    """
    Get selector health status.

    Returns:
        Current health check results
    """
    # Access from bot_state or global health checker
    if hasattr(app.state, "selector_health"):
        return app.state.selector_health

    return {"status": "not_initialized", "message": "Health monitoring not started yet"}


@app.get("/api/errors")
async def get_errors(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get recent errors with captures.

    Args:
        limit: Number of errors to return

    Returns:
        List of recent errors
    """
    if hasattr(app.state, "error_capture"):
        return app.state.error_capture.get_recent_errors(limit)
    return []


@app.get("/api/errors/{error_id}")
async def get_error_detail(error_id: str) -> Dict[str, Any]:
    """
    Get detailed error information.

    Args:
        error_id: Error ID

    Returns:
        Full error details with captures
    """
    if hasattr(app.state, "error_capture"):
        error = app.state.error_capture.get_error_by_id(error_id)
        if error:
            return error

    raise HTTPException(status_code=404, detail="Error not found")


@app.get("/api/errors/{error_id}/screenshot")
async def get_error_screenshot(error_id: str, type: str = "full"):
    """
    Get error screenshot.

    Args:
        error_id: Error ID
        type: Screenshot type (full or element)

    Returns:
        Image file
    """
    if hasattr(app.state, "error_capture"):
        error = app.state.error_capture.get_error_by_id(error_id)
        if error and "captures" in error:
            screenshot_key = f"{type}_screenshot"
            if screenshot_key in error["captures"]:
                screenshot_path = Path(error["captures"][screenshot_key])
                # Security: Ensure screenshot path is within the expected directory
                expected_dir = Path(app.state.error_capture.screenshots_dir).resolve()
                try:
                    resolved_path = screenshot_path.resolve()
                    # Check if path is within expected directory
                    if not str(resolved_path).startswith(str(expected_dir)):
                        logger.warning(f"Path traversal attempt: {screenshot_path}")
                        raise HTTPException(status_code=403, detail="Access denied")

                    if resolved_path.exists():
                        return FileResponse(resolved_path, media_type="image/png")
                except Exception as e:
                    logger.error(f"Error accessing screenshot: {e}")
                    raise HTTPException(status_code=500, detail="Error accessing screenshot")

    raise HTTPException(status_code=404, detail="Screenshot not found")


# User Management API Endpoints (Mock - for frontend development)
# TODO: Implement full database integration with personal_details table
class UserCreateRequest(BaseModel):
    """User creation request."""

    email: str
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
    phone: str
    first_name: str
    last_name: str
    center_name: str
    visa_category: str
    visa_subcategory: str
    is_active: bool
    created_at: str
    updated_at: str


# In-memory mock users storage (temporary - for frontend development only)
# WARNING: This is NOT thread-safe and should be replaced with proper database integration
# TODO: Replace with async database operations using existing users/personal_details tables
mock_users: List[UserModel] = []
next_user_id = 1


@app.get("/api/users", response_model=List[UserModel])
async def get_users(token_data: Dict[str, Any] = Depends(verify_jwt_token)):
    """
    Get all users - requires authentication.

    Args:
        token_data: Verified token data

    Returns:
        List of users
    """
    # TODO: Replace with actual database query
    return mock_users


@app.post("/api/users", response_model=UserModel)
async def create_user(
    user: UserCreateRequest, token_data: Dict[str, Any] = Depends(verify_jwt_token)
):
    """
    Create a new user - requires authentication.

    Args:
        user: User data
        token_data: Verified token data

    Returns:
        Created user
    """
    global next_user_id

    # TODO: Replace with actual database insert
    new_user = UserModel(
        id=next_user_id,
        email=user.email,
        phone=user.phone,
        first_name=user.first_name,
        last_name=user.last_name,
        center_name=user.center_name,
        visa_category=user.visa_category,
        visa_subcategory=user.visa_subcategory,
        is_active=user.is_active,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )

    mock_users.append(new_user)
    next_user_id += 1

    logger.info(f"User created: {new_user.email} by {token_data.get('sub', 'unknown')}")
    return new_user


@app.put("/api/users/{user_id}", response_model=UserModel)
async def update_user(
    user_id: int,
    user_update: UserUpdateRequest,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
):
    """
    Update a user - requires authentication.

    Args:
        user_id: User ID
        user_update: Updated user data
        token_data: Verified token data

    Returns:
        Updated user
    """
    # TODO: Replace with actual database update
    for user in mock_users:
        if user.id == user_id:
            update_data = user_update.dict(exclude_unset=True)
            for key, value in update_data.items():
                setattr(user, key, value)
            user.updated_at = datetime.now(timezone.utc).isoformat()

            logger.info(f"User updated: {user.email} by {token_data.get('sub', 'unknown')}")
            return user

    raise HTTPException(status_code=404, detail="User not found")


@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, token_data: Dict[str, Any] = Depends(verify_jwt_token)):
    """
    Delete a user - requires authentication.

    Args:
        user_id: User ID
        token_data: Verified token data

    Returns:
        Success message
    """
    global mock_users

    # TODO: Replace with actual database delete
    for i, user in enumerate(mock_users):
        if user.id == user_id:
            deleted_user = mock_users.pop(i)
            logger.info(f"User deleted: {deleted_user.email} by {token_data.get('sub', 'unknown')}")
            return {"message": "User deleted successfully"}

    raise HTTPException(status_code=404, detail="User not found")


@app.patch("/api/users/{user_id}", response_model=UserModel)
async def toggle_user_status(
    user_id: int,
    status_update: Dict[str, bool],
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
):
    """
    Toggle user active status - requires authentication.

    Args:
        user_id: User ID
        status_update: Status update data (is_active)
        token_data: Verified token data

    Returns:
        Updated user
    """
    # TODO: Replace with actual database update
    for user in mock_users:
        if user.id == user_id:
            if "is_active" in status_update:
                user.is_active = status_update["is_active"]
                user.updated_at = datetime.now(timezone.utc).isoformat()

                logger.info(
                    f"User status toggled: {user.email} -> {user.is_active} by {token_data.get('sub', 'unknown')}"
                )
                return user

    raise HTTPException(status_code=404, detail="User not found")


# Payment card endpoints
@app.get("/api/payment-card", response_model=Optional[PaymentCardResponse])
async def get_payment_card(token_data: Dict[str, Any] = Depends(verify_jwt_token)):
    """
    Get saved payment card (masked) - requires authentication.

    Args:
        token_data: Verified token data

    Returns:
        Masked payment card data or None if no card exists
    """
    try:
        db = Database()
        await db.connect()

        try:
            card = await db.get_payment_card_masked()
            if not card:
                return None

            return PaymentCardResponse(
                id=card["id"],
                card_holder_name=card["card_holder_name"],
                card_number_masked=card["card_number_masked"],
                expiry_month=card["expiry_month"],
                expiry_year=card["expiry_year"],
                created_at=card["created_at"],
            )
        finally:
            await db.close()
    except Exception as e:
        logger.error(f"Failed to get payment card: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve payment card")


@app.post("/api/payment-card", status_code=201)
async def save_payment_card(
    card_data: PaymentCardRequest, token_data: Dict[str, Any] = Depends(verify_jwt_token)
):
    """
    Save or update payment card - requires authentication.

    Args:
        card_data: Payment card data
        token_data: Verified token data

    Returns:
        Success message with card ID
    """
    try:
        db = Database()
        await db.connect()

        try:
            card_id = await db.save_payment_card(
                {
                    "card_holder_name": card_data.card_holder_name,
                    "card_number": card_data.card_number,
                    "expiry_month": card_data.expiry_month,
                    "expiry_year": card_data.expiry_year,
                    "cvv": card_data.cvv,
                }
            )

            logger.info(f"Payment card saved/updated by {token_data.get('sub', 'unknown')}")
            return {
                "success": True,
                "card_id": card_id,
                "message": "Payment card saved successfully",
            }
        finally:
            await db.close()
    except ValueError as e:
        logger.error(f"Invalid card data: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save payment card: {e}")
        raise HTTPException(status_code=500, detail="Failed to save payment card")


@app.delete("/api/payment-card")
async def delete_payment_card(token_data: Dict[str, Any] = Depends(verify_jwt_token)):
    """
    Delete saved payment card - requires authentication.

    Args:
        token_data: Verified token data

    Returns:
        Success message
    """
    try:
        db = Database()
        await db.connect()

        try:
            deleted = await db.delete_payment_card()
            if not deleted:
                raise HTTPException(status_code=404, detail="No payment card found")

            logger.info(f"Payment card deleted by {token_data.get('sub', 'unknown')}")
            return {"success": True, "message": "Payment card deleted successfully"}
        finally:
            await db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete payment card: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete payment card")


# Appointment Request Models
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


# Countries data (21 countries as specified)
COUNTRIES_DATA = [
    {"code": "nld", "name_en": "Netherlands", "name_tr": "Hollanda"},
    {"code": "aut", "name_en": "Austria", "name_tr": "Avusturya"},
    {"code": "bel", "name_en": "Belgium", "name_tr": "Belçika"},
    {"code": "che", "name_en": "Switzerland", "name_tr": "İsviçre"},
    {"code": "cze", "name_en": "Czech Republic", "name_tr": "Çekya"},
    {"code": "deu", "name_en": "Germany", "name_tr": "Almanya"},
    {"code": "dnk", "name_en": "Denmark", "name_tr": "Danimarka"},
    {"code": "esp", "name_en": "Spain", "name_tr": "İspanya"},
    {"code": "est", "name_en": "Estonia", "name_tr": "Estonya"},
    {"code": "fin", "name_en": "Finland", "name_tr": "Finlandiya"},
    {"code": "fra", "name_en": "France", "name_tr": "Fransa"},
    {"code": "grc", "name_en": "Greece", "name_tr": "Yunanistan"},
    {"code": "hun", "name_en": "Hungary", "name_tr": "Macaristan"},
    {"code": "isl", "name_en": "Iceland", "name_tr": "İzlanda"},
    {"code": "ita", "name_en": "Italy", "name_tr": "İtalya"},
    {"code": "ltu", "name_en": "Lithuania", "name_tr": "Litvanya"},
    {"code": "lva", "name_en": "Latvia", "name_tr": "Letonya"},
    {"code": "mlt", "name_en": "Malta", "name_tr": "Malta"},
    {"code": "nor", "name_en": "Norway", "name_tr": "Norveç"},
    {"code": "pol", "name_en": "Poland", "name_tr": "Polonya"},
    {"code": "prt", "name_en": "Portugal", "name_tr": "Portekiz"},
]


@app.get("/api/countries", response_model=List[CountryResponse])
async def get_countries():
    """
    Get list of available countries.

    Returns:
        List of countries with codes and names
    """
    return COUNTRIES_DATA


@app.get("/api/countries/{country_code}/centres")
async def get_country_centres(country_code: str):
    """
    Get list of centres for a specific country.

    Args:
        country_code: Country code (e.g., 'nld', 'aut')

    Returns:
        List of centre names

    Note:
        Currently returns Turkish VFS centres regardless of country_code.
        This is because appointments are made at Turkish VFS centres for
        all destination countries. In the future, this could be dynamically
        fetched from VFS or cached.
    """
    # Turkish VFS centres (same for all countries as applications are made in Turkey)
    centres = ["Istanbul", "Ankara", "Izmir", "Antalya", "Bursa"]
    return centres


@app.post("/api/appointment-requests", status_code=201)
async def create_appointment_request(
    request_data: AppointmentRequestCreate, token_data: Dict[str, Any] = Depends(verify_jwt_token)
):
    """
    Create a new appointment request.

    Args:
        request_data: Appointment request data
        token_data: Verified token data

    Returns:
        Created appointment request info
    """
    try:
        db = Database()
        await db.connect()

        try:
            # Validate person count matches persons list
            if request_data.person_count != len(request_data.persons):
                raise HTTPException(
                    status_code=400,
                    detail=f"Person count ({request_data.person_count}) does not match number of persons provided ({len(request_data.persons)})",
                )

            # Convert persons to dict
            persons_data = [person.dict() for person in request_data.persons]

            # Create request in database
            request_id = await db.create_appointment_request(
                country_code=request_data.country_code,
                visa_category=request_data.visa_category,
                visa_subcategory=request_data.visa_subcategory,
                centres=request_data.centres,
                preferred_dates=request_data.preferred_dates,
                person_count=request_data.person_count,
                persons=persons_data,
            )

            logger.info(
                f"Appointment request {request_id} created by {token_data.get('sub', 'unknown')}"
            )

            return {"id": request_id, "status": "pending", "message": "Talep oluşturuldu"}
        finally:
            await db.close()
    except HTTPException:
        raise
    except ValidationError as e:
        logger.error(f"Validation error creating appointment request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create appointment request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create appointment request")


@app.get("/api/appointment-requests", response_model=List[AppointmentRequestResponse])
async def get_appointment_requests(
    status: Optional[str] = None, token_data: Dict[str, Any] = Depends(verify_jwt_token)
):
    """
    Get all appointment requests.

    Args:
        status: Optional status filter
        token_data: Verified token data

    Returns:
        List of appointment requests
    """
    try:
        db = Database()
        await db.connect()

        try:
            requests = await db.get_all_appointment_requests(status=status)

            # Convert to response model
            response_requests = []
            for req in requests:
                # Remove internal fields from persons
                persons = [
                    {k: v for k, v in person.items() if k != "request_id" and k != "created_at"}
                    for person in req["persons"]
                ]

                response_requests.append(
                    AppointmentRequestResponse(
                        id=req["id"],
                        country_code=req["country_code"],
                        visa_category=req["visa_category"],
                        visa_subcategory=req["visa_subcategory"],
                        centres=req["centres"],
                        preferred_dates=req["preferred_dates"],
                        person_count=req["person_count"],
                        status=req["status"],
                        created_at=req["created_at"],
                        completed_at=req.get("completed_at"),
                        persons=persons,
                    )
                )

            return response_requests
        finally:
            await db.close()
    except Exception as e:
        logger.error(f"Failed to get appointment requests: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get appointment requests")


@app.get("/api/appointment-requests/{request_id}", response_model=AppointmentRequestResponse)
async def get_appointment_request(
    request_id: int, token_data: Dict[str, Any] = Depends(verify_jwt_token)
):
    """
    Get a specific appointment request.

    Args:
        request_id: Request ID
        token_data: Verified token data

    Returns:
        Appointment request details
    """
    try:
        db = Database()
        await db.connect()

        try:
            req = await db.get_appointment_request(request_id)

            if not req:
                raise HTTPException(status_code=404, detail="Appointment request not found")

            # Remove internal fields from persons
            persons = [
                {k: v for k, v in person.items() if k != "request_id" and k != "created_at"}
                for person in req["persons"]
            ]

            return AppointmentRequestResponse(
                id=req["id"],
                country_code=req["country_code"],
                visa_category=req["visa_category"],
                visa_subcategory=req["visa_subcategory"],
                centres=req["centres"],
                preferred_dates=req["preferred_dates"],
                person_count=req["person_count"],
                status=req["status"],
                created_at=req["created_at"],
                completed_at=req.get("completed_at"),
                persons=persons,
            )
        finally:
            await db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get appointment request {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get appointment request")


@app.delete("/api/appointment-requests/{request_id}")
async def delete_appointment_request(
    request_id: int, token_data: Dict[str, Any] = Depends(verify_jwt_token)
):
    """
    Delete an appointment request.

    Args:
        request_id: Request ID
        token_data: Verified token data

    Returns:
        Success message
    """
    try:
        db = Database()
        await db.connect()

        try:
            deleted = await db.delete_appointment_request(request_id)

            if not deleted:
                raise HTTPException(status_code=404, detail="Appointment request not found")

            logger.info(
                f"Appointment request {request_id} deleted by {token_data.get('sub', 'unknown')}"
            )

            return {"success": True, "message": "Appointment request deleted"}
        finally:
            await db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete appointment request {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete appointment request")


@app.patch("/api/appointment-requests/{request_id}/status")
async def update_appointment_request_status(
    request_id: int,
    status_update: Dict[str, str],
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
):
    """
    Update appointment request status.

    Args:
        request_id: Request ID
        status_update: Dict with 'status' key
        token_data: Verified token data

    Returns:
        Success message

    Note:
        When status is set to 'completed', completed_at timestamp is set.
        When status changes from 'completed' to another status, completed_at
        is not cleared as it represents historical data.
    """
    try:
        status = status_update.get("status")
        if not status:
            raise HTTPException(status_code=400, detail="Status is required")

        if status not in ["pending", "processing", "completed", "failed"]:
            raise HTTPException(status_code=400, detail="Invalid status value")

        db = Database()
        await db.connect()

        try:
            # Set completed_at timestamp only when status becomes 'completed'
            completed_at = datetime.now(timezone.utc) if status == "completed" else None

            updated = await db.update_appointment_request_status(
                request_id=request_id, status=status, completed_at=completed_at
            )

            if not updated:
                raise HTTPException(status_code=404, detail="Appointment request not found")

            logger.info(
                f"Appointment request {request_id} status updated to {status} by {token_data.get('sub', 'unknown')}"
            )

            return {"success": True, "message": f"Status updated to {status}"}
        finally:
            await db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to update appointment request {request_id} status: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to update status")


@app.get("/api/settings/webhook-urls", response_model=WebhookUrlsResponse)
async def get_webhook_urls(request: Request):
    """
    Get webhook URLs for SMS forwarding.

    Args:
        request: FastAPI request object

    Returns:
        Webhook URLs with base URL
    """
    # Get base URL from request
    base_url = str(request.base_url).rstrip("/")

    return WebhookUrlsResponse(
        appointment_webhook=f"{base_url}/api/webhook/sms/appointment",
        payment_webhook=f"{base_url}/api/webhook/sms/payment",
        base_url=base_url,
    )


@app.get("/errors.html", response_class=HTMLResponse)
async def errors_dashboard(request: Request):
    """
    Render errors dashboard page.

    Args:
        request: FastAPI request object

    Returns:
        HTML response with errors dashboard template
    """
    return templates.TemplateResponse(
        "errors.html", {"request": request, "title": "Error Dashboard - VFS Bot"}
    )


# Catch-all route for React SPA - MUST be last!
@app.get("/", response_class=HTMLResponse)
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_react_app(request: Request, full_path: str = ""):
    """
    Serve React SPA for all non-API routes.

    This handles client-side routing by serving index.html for all routes
    that don't start with /api, /ws, /health, /metrics, or /static.

    Args:
        request: FastAPI request object
        full_path: Requested path

    Returns:
        HTML response with React app
    """
    # Skip API routes, WebSocket, health checks, and static files
    if full_path.startswith(("api/", "ws", "health", "metrics", "static/", "assets/")):
        raise HTTPException(status_code=404, detail="Not found")

    # Serve the React app
    dist_dir = Path(__file__).parent / "static" / "dist"
    index_file = dist_dir / "index.html"

    if index_file.exists():
        return FileResponse(index_file)
    else:
        # Fallback to old template if React build doesn't exist
        return templates.TemplateResponse(
            "index.html", {"request": request, "title": "VFS-Bot Dashboard"}
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
