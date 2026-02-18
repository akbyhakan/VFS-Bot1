"""Audit log routes for VFS-Bot web application."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from src.repositories.audit_log_repository import AuditLogRepository
from web.dependencies import get_audit_log_repository, verify_jwt_token
from web.models.audit import AuditLogResponse, AuditStatsResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=List[AuditLogResponse])
async def list_audit_logs(
    limit: int = Query(
        default=100, ge=1, le=1000, description="Maximum number of logs to retrieve"
    ),
    action: Optional[str] = Query(default=None, description="Filter by action type"),
    user_id: Optional[int] = Query(default=None, description="Filter by user ID"),
    success: Optional[bool] = Query(default=None, description="Filter by success status"),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    current_user: Dict[str, Any] = Depends(verify_jwt_token),
) -> List[AuditLogResponse]:
    """
    Get audit log entries with optional filters.

    Requires authentication.
    """
    try:
        logs = await audit_repo.get_all(limit=limit, action=action, user_id=user_id)

        # Filter by success if specified
        if success is not None:
            logs = [log for log in logs if log.get("success") == success]

        return [AuditLogResponse(**log) for log in logs]
    except Exception as e:
        logger.error(f"Failed to retrieve audit logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit logs")


@router.get("/logs/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: int,
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    current_user: Dict[str, Any] = Depends(verify_jwt_token),
) -> AuditLogResponse:
    """
    Get a specific audit log entry by ID.

    Requires authentication.
    """
    try:
        log_entry = await audit_repo.get_by_id(log_id)

        if log_entry is None:
            raise HTTPException(status_code=404, detail="Audit log entry not found")

        return AuditLogResponse(**log_entry.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve audit log {log_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit log")


@router.get("/stats", response_model=AuditStatsResponse)
async def get_audit_stats(
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    current_user: Dict[str, Any] = Depends(verify_jwt_token),
) -> AuditStatsResponse:
    """
    Get audit log statistics.

    Requires authentication.
    """
    try:
        # Get all logs (with reasonable limit for stats calculation)
        all_logs = await audit_repo.get_all(limit=10000)

        total = len(all_logs)

        # Count by action type
        by_action: Dict[str, int] = {}
        success_count = 0

        # Calculate 24h threshold
        now = datetime.now(timezone.utc)
        threshold_24h = (now - timedelta(hours=24)).isoformat()
        recent_failures = 0

        for log in all_logs:
            action = log.get("action", "unknown")
            by_action[action] = by_action.get(action, 0) + 1

            if log.get("success", True):
                success_count += 1

            # Check for recent failures
            if not log.get("success", True) and log.get("timestamp", "") >= threshold_24h:
                recent_failures += 1

        # Calculate success rate
        success_rate = success_count / total if total > 0 else 1.0

        return AuditStatsResponse(
            total=total,
            by_action=by_action,
            success_rate=success_rate,
            recent_failures=recent_failures,
        )
    except Exception as e:
        logger.error(f"Failed to retrieve audit statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit statistics")
