"""Audit log models for VFS-Bot web application."""

from typing import Dict, Optional

from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    """Audit log entry response model."""

    id: int
    action: str
    user_id: Optional[int] = None
    username: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[str] = None
    timestamp: str
    success: bool
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None


class AuditStatsResponse(BaseModel):
    """Audit statistics response model."""

    total: int = Field(description="Total audit log entries")
    by_action: Dict[str, int] = Field(description="Count by action type")
    success_rate: float = Field(description="Success rate (0.0 to 1.0)")
    recent_failures: int = Field(description="Number of failures in last 24h")
