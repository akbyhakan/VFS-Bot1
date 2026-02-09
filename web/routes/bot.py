"""Bot control and WebSocket routes for VFS-Bot web application."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.auth import verify_token
from src.core.bot_controller import BotController
from src.core.security import verify_api_key
from web.dependencies import BotCommand, bot_state, broadcast_message, manager, verify_jwt_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bot", tags=["bot"])
limiter = Limiter(key_func=get_remote_address)

# Error message constants
BOT_NOT_CONFIGURED_ERROR = {
    "status": "error",
    "message": "Bot controller not configured. Please restart in 'both' mode.",
}


async def _get_controller() -> BotController:
    """
    Get the BotController instance.
    
    Returns:
        BotController instance
        
    Raises:
        HTTPException: If controller is not configured
    """
    controller = await BotController.get_instance()
    status = controller.get_status()
    if status["status"] == "not_configured":
        raise HTTPException(
            status_code=503,
            detail="Bot controller not configured. Please restart the application in 'both' mode.",
        )
    return controller


async def _sync_bot_state(controller: BotController) -> None:
    """
    Sync real bot status to bot_state dict for WebSocket broadcast compatibility.
    
    Args:
        controller: BotController instance
    """
    status = controller.get_status()
    bot_state["running"] = status["running"]
    bot_state["status"] = status["status"]


@router.post("/bot/start")
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
    try:
        controller = await _get_controller()
    except HTTPException:
        return BOT_NOT_CONFIGURED_ERROR

    # Start the bot via controller
    result = await controller.start_bot()

    # Sync status to bot_state for WebSocket broadcast
    await _sync_bot_state(controller)

    # Broadcast status update
    if result["status"] == "success":
        await broadcast_message(
            {
                "type": "status",
                "data": {"running": True, "status": "running", "message": result["message"]},
            }
        )
        logger.info(f"Bot started via dashboard by {api_key.get('name', 'unknown')}")
    else:
        await broadcast_message(
            {
                "type": "status",
                "data": {"running": False, "status": "error", "message": result["message"]},
            }
        )

    return result


@router.post("/bot/stop")
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
    try:
        controller = await _get_controller()
    except HTTPException:
        return BOT_NOT_CONFIGURED_ERROR

    # Stop the bot via controller
    result = await controller.stop_bot()

    # Sync status to bot_state for WebSocket broadcast
    await _sync_bot_state(controller)

    # Broadcast status update
    if result["status"] == "success":
        await broadcast_message(
            {
                "type": "status",
                "data": {"running": False, "status": "stopped", "message": result["message"]},
            }
        )
        logger.info(f"Bot stopped via dashboard by {api_key.get('name', 'unknown')}")
    else:
        await broadcast_message(
            {
                "type": "status",
                "data": {"running": False, "status": "error", "message": result["message"]},
            }
        )

    return result


@router.post("/bot/restart")
@limiter.limit("5/minute")
async def restart_bot(request: Request, api_key: dict = Depends(verify_api_key)) -> Dict[str, str]:
    """
    Restart the bot - requires authentication.

    Args:
        request: FastAPI request object (required for rate limiter)
        api_key: Verified API key metadata

    Returns:
        Response dictionary
    """
    try:
        controller = await _get_controller()
    except HTTPException:
        return BOT_NOT_CONFIGURED_ERROR

    # Broadcast restarting status
    await broadcast_message(
        {
            "type": "status",
            "data": {"running": False, "status": "restarting", "message": "Bot restarting..."},
        }
    )

    # Restart the bot via controller
    result = await controller.restart_bot()

    # Sync status to bot_state for WebSocket broadcast
    await _sync_bot_state(controller)

    # Broadcast final status
    if result["status"] == "success":
        await broadcast_message(
            {
                "type": "status",
                "data": {"running": True, "status": "running", "message": result["message"]},
            }
        )
        logger.info(f"Bot restarted via dashboard by {api_key.get('name', 'unknown')}")
    else:
        await broadcast_message(
            {
                "type": "status",
                "data": {"running": False, "status": "error", "message": result["message"]},
            }
        )

    return result


@router.post("/bot/check-now")
@limiter.limit("10/minute")
async def check_now(request: Request, api_key: dict = Depends(verify_api_key)) -> Dict[str, str]:
    """
    Trigger a manual slot check - requires authentication.

    Args:
        request: FastAPI request object (required for rate limiter)
        api_key: Verified API key metadata

    Returns:
        Response dictionary
    """
    try:
        controller = await _get_controller()
    except HTTPException:
        return BOT_NOT_CONFIGURED_ERROR

    # Trigger manual check via controller
    result = await controller.trigger_check_now()

    if result["status"] == "success":
        # Update last check timestamp
        bot_state["last_check"] = datetime.now(timezone.utc).isoformat()

        await broadcast_message(
            {
                "type": "status",
                "data": {"message": result["message"], "last_check": bot_state["last_check"]},
            }
        )

        logger.info(f"Manual check triggered via dashboard by {api_key.get('name', 'unknown')}")

    return result


@router.get("/logs")
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


@router.get("/selector-health")
async def get_selector_health(request: Request) -> Dict[str, Any]:
    """
    Get selector health status.

    Returns:
        Current health check results
    """
    # Access from bot_state or global health checker
    if hasattr(request.app.state, "selector_health"):
        return request.app.state.selector_health

    return {"status": "not_initialized", "message": "Health monitoring not started yet"}


@router.get("/errors")
async def get_errors(request: Request, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get recent errors with captures.

    Args:
        request: FastAPI request object
        limit: Number of errors to return

    Returns:
        List of recent errors
    """
    if hasattr(request.app.state, "error_capture"):
        return request.app.state.error_capture.get_recent_errors(limit)
    return []


@router.get("/errors/{error_id}")
async def get_error_detail(request: Request, error_id: str) -> Dict[str, Any]:
    """
    Get detailed error information.

    Args:
        request: FastAPI request object
        error_id: Error ID

    Returns:
        Full error details with captures
    """
    if hasattr(request.app.state, "error_capture"):
        error = request.app.state.error_capture.get_error_by_id(error_id)
        if error:
            return error

    raise HTTPException(status_code=404, detail="Error not found")


@router.get("/errors/{error_id}/screenshot")
async def get_error_screenshot(request: Request, error_id: str, type: str = "full"):
    """
    Get error screenshot.

    Args:
        request: FastAPI request object
        error_id: Error ID
        type: Screenshot type (full or element)

    Returns:
        Image file
    """
    if hasattr(request.app.state, "error_capture"):
        error = request.app.state.error_capture.get_error_by_id(error_id)
        if error and "captures" in error:
            screenshot_key = f"{type}_screenshot"
            if screenshot_key in error["captures"]:
                screenshot_path = Path(error["captures"][screenshot_key])
                # Security: Ensure screenshot path is within the expected directory
                expected_dir = Path(request.app.state.error_capture.screenshots_dir).resolve()
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


# WebSocket endpoint (not in APIRouter, added separately to main app)
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

    # Try to connect with limit enforcement
    connected = await manager.connect(websocket)
    if not connected:
        await websocket.close(code=4003, reason="Connection limit reached")
        return

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

    bot_state["last_check"] = datetime.now(timezone.utc).isoformat()

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
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"

    bot_state["logs"].append(log_entry)
    # deque with maxlen=500 automatically removes oldest entries

    await broadcast_message(
        {"type": "log", "data": {"message": log_entry, "level": level, "timestamp": timestamp}}
    )
