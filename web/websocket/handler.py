"""WebSocket handler for real-time updates."""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger

from src.core.auth import verify_token
from web.dependencies import bot_state, broadcast_message, manager


async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.

    Authentication methods (in order of priority):
    1. HttpOnly cookie (access_token) - automatically sent by browser
    2. First message as {"token": "your-jwt-token"} - legacy fallback

    Args:
        websocket: WebSocket connection
    """
    # Method 1: Try to get token from HttpOnly cookie (primary method for web browsers)
    token = websocket.cookies.get("access_token")
    if token:
        logger.debug("WebSocket auth via cookie")

    # Pre-accept verification for cookie tokens
    if token:
        try:
            await verify_token(token)
        except HTTPException:
            await websocket.close(code=4001, reason="Invalid token")
            return
        await websocket.accept()
    else:
        # Legacy: must accept first to receive message
        await websocket.accept()
        # Method 3: Wait for authentication message (legacy fallback for backward compatibility)
        try:
            logger.debug("WebSocket waiting for auth message (legacy method)")
            auth_data = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)

            if not isinstance(auth_data, dict) or "token" not in auth_data:
                await websocket.close(code=4001, reason="Authentication required")
                return

            token = auth_data.get("token")
            if not token:
                await websocket.close(code=4001, reason="Token missing")
                return
            logger.debug("WebSocket auth via message (legacy)")

            # Verify token for legacy auth
            try:
                await verify_token(token)
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
        {
            "type": "status",
            "data": {"running": bot_state.get_running(), "status": bot_state.get_status()},
        }
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
    slots_found: Optional[int] = None, appointments_booked: Optional[int] = None, active_users: Optional[int] = None
) -> None:
    """
    Update bot statistics and broadcast to clients.

    Args:
        slots_found: Number of slots found
        appointments_booked: Number of appointments booked
        active_users: Number of active users
    """
    if slots_found is not None:
        bot_state.set_slots_found(slots_found)
    if appointments_booked is not None:
        bot_state.set_appointments_booked(appointments_booked)
    if active_users is not None:
        bot_state.set_active_users(active_users)

    bot_state.set_last_check(datetime.now(timezone.utc).isoformat())

    await broadcast_message(
        {
            "type": "stats",
            "data": {
                "slots_found": bot_state.get_slots_found(),
                "appointments_booked": bot_state.get_appointments_booked(),
                "active_users": bot_state.get_active_users(),
                "last_check": bot_state.get_last_check(),
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

    bot_state.append_log(message, level)
    # deque with maxlen=500 automatically removes oldest entries

    await broadcast_message(
        {"type": "log", "data": {"message": message, "level": level, "timestamp": timestamp}}
    )
