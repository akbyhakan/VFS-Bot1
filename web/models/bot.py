"""Bot command and status models for VFS-Bot web application."""

from typing import Any, Dict

from pydantic import BaseModel


class BotCommand(BaseModel):
    """Bot command model."""

    action: str
    config: Dict[str, Any] = {}


class StatusUpdate(BaseModel):
    """Status update model."""

    status: str
    message: str
    timestamp: str
