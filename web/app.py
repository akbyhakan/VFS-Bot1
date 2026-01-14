"""FastAPI web dashboard with WebSocket support for VFS-Bot."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Set
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.core.security import verify_api_key, generate_api_key
from src.core.auth import create_access_token, verify_token

security_scheme = HTTPBearer()

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="VFS-Bot Dashboard", version="2.0.0")

# CORS Configuration
ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount static files
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"

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
    "logs": [],
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
        await websocket.accept()
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


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Render main dashboard page.

    Args:
        request: FastAPI request object

    Returns:
        HTML response with dashboard template
    """
    return templates.TemplateResponse(
        "index.html", {"request": request, "title": "VFS-Bot Dashboard"}
    )


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
    """Check database connectivity."""
    try:
        # Check if database is available in app state
        if hasattr(app.state, 'db') and app.state.db:
            async with app.state.db.get_connection(timeout=5.0) as conn:
                await conn.execute("SELECT 1")
                return True
        return True  # Assume healthy if not initialized yet
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


@app.get("/health/live")
async def liveness_check():
    """Kubernetes liveness probe - just check if app is responding."""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness_check():
    """Kubernetes readiness probe - check if app is ready to serve traffic."""
    # Check critical dependencies
    try:
        if hasattr(app.state, 'db') and app.state.db:
            async with app.state.db.get_connection(timeout=2.0) as conn:
                await conn.execute("SELECT 1")
        return {"status": "ready"}
    except Exception:
        return Response(content='{"status": "not_ready"}', status_code=503)


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
    return {"logs": bot_state["logs"][-limit:]}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.

    Args:
        websocket: WebSocket connection
    """
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

    # Keep only last 500 logs in memory
    if len(bot_state["logs"]) > 500:
        bot_state["logs"] = bot_state["logs"][-500:]

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

    # Check password - support both plaintext (for simple setups) and hashed passwords
    password_valid = False
    if admin_password.startswith("$2b$"):
        # Hashed password (bcrypt format)
        password_valid = verify_password(credentials.password, admin_password)
    else:
        # Plaintext password (for development/testing)
        # Note: In production, passwords should be hashed
        password_valid = credentials.password == admin_password

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
