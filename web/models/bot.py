"""Bot command and status models for VFS-Bot web application."""

from typing import Any, Dict, Literal

from pydantic import BaseModel


class BotCommand(BaseModel):
    """Bot command model."""

    action: Literal["start", "stop", "restart", "check_now"]
    config: Dict[str, Any] = {}


class StatusUpdate(BaseModel):
    """Status update model."""

    status: str
    message: str
    timestamp: str
