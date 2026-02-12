"""WebSocket management for VFS-Bot web application."""

from .handler import add_log, update_bot_stats, websocket_endpoint
from .manager import ConnectionManager

__all__ = ["ConnectionManager", "websocket_endpoint", "update_bot_stats", "add_log"]
