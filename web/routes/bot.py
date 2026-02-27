"""Bot control routes for VFS-Bot web application."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.bot_controller import BotController
from web.dependencies import bot_state, broadcast_message, verify_jwt_token
from web.models.bot import BotSettings, BotSettingsResponse

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
    Sync real bot status to bot_state for WebSocket broadcast compatibility.

    Args:
        controller: BotController instance
    """
    status = controller.get_status()
    bot_state.set_running(status["running"])
    bot_state.set_status(status["status"])


@router.post("/start")
@limiter.limit("5/minute")
async def start_bot(
    request: Request, auth_data: dict = Depends(verify_jwt_token)
) -> Dict[str, str]:
    """
    Start the bot - requires authentication.

    Args:
        request: FastAPI request object (required for rate limiter)
        auth_data: Verified authentication metadata

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
        logger.info(
            f"Bot started via dashboard by {auth_data.get('name', auth_data.get('sub', 'unknown'))}"
        )
    else:
        await broadcast_message(
            {
                "type": "status",
                "data": {"running": False, "status": "error", "message": result["message"]},
            }
        )

    return result


@router.post("/stop")
@limiter.limit("5/minute")
async def stop_bot(
    request: Request, auth_data: dict = Depends(verify_jwt_token)
) -> Dict[str, str]:
    """
    Stop the bot - requires authentication.

    Args:
        request: FastAPI request object (required for rate limiter)
        auth_data: Verified authentication metadata

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
        logger.info(
            f"Bot stopped via dashboard by {auth_data.get('name', auth_data.get('sub', 'unknown'))}"
        )
    else:
        await broadcast_message(
            {
                "type": "status",
                "data": {"running": False, "status": "error", "message": result["message"]},
            }
        )

    return result


@router.post("/restart")
@limiter.limit("5/minute")
async def restart_bot(
    request: Request, auth_data: dict = Depends(verify_jwt_token)
) -> Dict[str, str]:
    """
    Restart the bot - requires authentication.

    Args:
        request: FastAPI request object (required for rate limiter)
        auth_data: Verified authentication metadata

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
        logger.info(
            f"Bot restarted via dashboard by "
            f"{auth_data.get('name', auth_data.get('sub', 'unknown'))}"
        )
    else:
        await broadcast_message(
            {
                "type": "status",
                "data": {"running": False, "status": "error", "message": result["message"]},
            }
        )

    return result


@router.post("/check-now")
@limiter.limit("10/minute")
async def check_now(
    request: Request, auth_data: dict = Depends(verify_jwt_token)
) -> Dict[str, str]:
    """
    Trigger a manual slot check - requires authentication.

    Args:
        request: FastAPI request object (required for rate limiter)
        auth_data: Verified authentication metadata

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
        bot_state.set_last_check(datetime.now(timezone.utc).isoformat())

        await broadcast_message(
            {
                "type": "status",
                "data": {"message": result["message"], "last_check": bot_state.get_last_check()},
            }
        )

        logger.info(
            f"Manual check triggered via dashboard by "
            f"{auth_data.get('name', auth_data.get('sub', 'unknown'))}"
        )

    return result


@router.get("/logs")
async def get_logs(
    limit: int = 100, auth_data: Dict[str, Any] = Depends(verify_jwt_token)
) -> Dict[str, List[str]]:
    """
    Get recent logs - requires authentication.

    Args:
        limit: Maximum number of logs to return
        auth_data: Verified authentication metadata

    Returns:
        Dictionary with logs list
    """
    logs_list = bot_state.get_logs_list()
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
                    if not resolved_path.is_relative_to(expected_dir):
                        logger.warning(f"Path traversal attempt: {screenshot_path}")
                        raise HTTPException(status_code=403, detail="Access denied")

                    if resolved_path.exists():
                        return FileResponse(resolved_path, media_type="image/png")
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Error accessing screenshot: {e}")
                    raise HTTPException(status_code=500, detail="Error accessing screenshot")

    raise HTTPException(status_code=404, detail="Screenshot not found")


@router.get("/errors/{error_id}/html-snapshot")
async def get_error_html_snapshot(request: Request, error_id: str):
    """
    Get error HTML snapshot.

    Args:
        request: FastAPI request object
        error_id: Error ID

    Returns:
        HTML file
    """
    if hasattr(request.app.state, "error_capture"):
        error = request.app.state.error_capture.get_error_by_id(error_id)
        if error and "captures" in error:
            if "html_snapshot" in error["captures"]:
                html_path = Path(error["captures"]["html_snapshot"])
                # Security: Ensure HTML path is within the expected directory
                expected_dir = Path(request.app.state.error_capture.screenshots_dir).resolve()
                try:
                    resolved_path = html_path.resolve()
                    # Check if path is within expected directory
                    if not resolved_path.is_relative_to(expected_dir):
                        logger.warning(f"Path traversal attempt: {html_path}")
                        raise HTTPException(status_code=403, detail="Access denied")

                    if resolved_path.exists():
                        return FileResponse(
                            resolved_path,
                            media_type="text/html",
                            filename=f"error_{error_id}.html",
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Error accessing HTML snapshot: {e}")
                    raise HTTPException(status_code=500, detail="Error accessing HTML snapshot")

    raise HTTPException(status_code=404, detail="HTML snapshot not found")


@router.get("/settings")
async def get_bot_settings(
    auth_data: Dict[str, Any] = Depends(verify_jwt_token),
) -> BotSettingsResponse:
    """
    Get bot settings - requires authentication.

    Args:
        auth_data: Verified authentication metadata

    Returns:
        Bot settings response
    """
    try:
        controller = await _get_controller()
    except HTTPException:
        # If bot controller not configured, return defaults
        from src.constants import AccountPoolConfig

        return BotSettingsResponse(
            cooldown_seconds=AccountPoolConfig.COOLDOWN_SECONDS,
            cooldown_minutes=round(
                AccountPoolConfig.COOLDOWN_SECONDS / 60
            ),  # Round to nearest minute
            quarantine_minutes=AccountPoolConfig.QUARANTINE_SECONDS // 60,
            max_failures=AccountPoolConfig.MAX_FAILURES,
        )

    settings = controller.get_cooldown_settings()
    return BotSettingsResponse(**settings)


@router.put("/settings")
@limiter.limit("5/minute")
async def update_bot_settings(
    request: Request,
    settings: BotSettings,
    auth_data: Dict[str, Any] = Depends(verify_jwt_token),
) -> Dict[str, str]:
    """
    Update bot settings - requires authentication.

    Args:
        request: FastAPI request object (required for rate limiter)
        settings: Bot settings to update
        auth_data: Verified authentication metadata

    Returns:
        Response dictionary
    """
    try:
        controller = await _get_controller()
    except HTTPException:
        return BOT_NOT_CONFIGURED_ERROR

    # Build update kwargs - only send non-None values
    update_kwargs = {"cooldown_seconds": settings.cooldown_minutes * 60}

    if settings.quarantine_minutes is not None:
        update_kwargs["quarantine_seconds"] = settings.quarantine_minutes * 60

    if settings.max_failures is not None:
        update_kwargs["max_failures"] = settings.max_failures

    result = await controller.update_settings(**update_kwargs)

    if result["status"] == "success":
        user = auth_data.get('name', auth_data.get('sub', 'unknown'))
        logger.info(f"Bot settings updated via dashboard by {user}: {update_kwargs}")
        return {
            "status": "success",
            "message": "Bot ayarları güncellendi",
        }
    else:
        return result
