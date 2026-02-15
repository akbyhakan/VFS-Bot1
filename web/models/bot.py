"""Bot command and status models for VFS-Bot web application."""

from typing import Any, Dict, Literal

from pydantic import BaseModel, Field


class BotCommand(BaseModel):
    """Bot command model."""

    action: Literal["start", "stop", "restart", "check_now"]
    config: Dict[str, Any] = {}


class StatusUpdate(BaseModel):
    """Status update model."""

    status: str
    message: str
    timestamp: str


class BotSettings(BaseModel):
    """Bot settings update model."""

    cooldown_minutes: int = Field(ge=5, le=60, default=10, description="Cooldown süresi (dakika)")


class BotSettingsResponse(BaseModel):
    """Bot settings response model."""

    cooldown_minutes: int
    cooldown_seconds: int
    quarantine_minutes: int
    max_failures: int
