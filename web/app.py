"""FastAPI web dashboard with WebSocket support for VFS-Bot."""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="VFS-Bot Dashboard", version="2.0.0")

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
active_connections: List[WebSocket] = []


class BotCommand(BaseModel):
    """Bot command model."""

    action: str
    config: Dict[str, Any] = {}


class StatusUpdate(BaseModel):
    """Status update model."""

    status: str
    message: str
    timestamp: str


async def broadcast_message(message: Dict[str, Any]) -> None:
    """
    Broadcast message to all connected WebSocket clients.

    Args:
        message: Message dictionary to broadcast
    """
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception as e:
            logger.error(f"Error broadcasting to client: {e}")
            disconnected.append(connection)

    # Remove disconnected clients
    for conn in disconnected:
        if conn in active_connections:
            active_connections.remove(conn)


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
    db_healthy = await check_database_health()

    # Determine overall status based on component health
    overall_status = "healthy" if db_healthy else "degraded"

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "components": {
            "database": db_healthy,
            "bot": bot_state.get("running", False),
            "notifications": True,
        },
    }


async def check_database_health() -> bool:
    """Check database connectivity."""
    try:
        # Try to import and check database module
        # This is a basic check - in production, you would do an actual query
        from src.database import Database

        # For now, assume healthy if import works
        # TODO: Add actual database ping query when database is initialized
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


@app.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """
    Prometheus-compatible metrics endpoint.

    Returns:
        Metrics dictionary
    """
    uptime = (datetime.now(timezone.utc) - metrics["start_time"]).total_seconds()

    return {
        "uptime_seconds": uptime,
        "requests_total": metrics["requests_total"],
        "requests_success": metrics["requests_success"],
        "requests_failed": metrics["requests_failed"],
        "success_rate": metrics["requests_success"] / max(metrics["requests_total"], 1),
        "slots_checked": metrics["slots_checked"],
        "slots_found": metrics["slots_found"],
        "appointments_booked": metrics["appointments_booked"],
        "captchas_solved": metrics["captchas_solved"],
        "errors_by_type": metrics["errors"],
        "bot_status": bot_state["status"],
    }


def increment_metric(name: str, count: int = 1) -> None:
    """Increment a metric counter."""
    if name in metrics:
        metrics[name] += count


@app.post("/api/bot/start")
async def start_bot(command: BotCommand) -> Dict[str, str]:
    """
    Start the bot.

    Args:
        command: Bot command with configuration

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

    logger.info("Bot started via dashboard")
    return {"status": "success", "message": "Bot started"}


@app.post("/api/bot/stop")
async def stop_bot() -> Dict[str, str]:
    """
    Stop the bot.

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

    logger.info("Bot stopped via dashboard")
    return {"status": "success", "message": "Bot stopped"}


@app.get("/api/logs")
async def get_logs(limit: int = 100) -> Dict[str, List[str]]:
    """
    Get recent logs.

    Args:
        limit: Maximum number of logs to return

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
    await websocket.accept()
    active_connections.append(websocket)

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
        active_connections.remove(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
