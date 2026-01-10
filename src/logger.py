"""Structured JSON logging for production."""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add custom fields
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "centre"):
            log_data["centre"] = record.centre
        if hasattr(record, "action"):
            log_data["action"] = record.action

        return json.dumps(log_data)


def setup_structured_logging(level: str = "INFO", json_format: bool = True) -> None:
    """
    Setup structured logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON format (True for production)
    """
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Choose formatter
    formatter: logging.Formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # File handler with JSON
    file_handler = logging.FileHandler(logs_dir / "vfs_bot.jsonl")
    file_handler.setFormatter(formatter)

    # Console handler (human-readable for development)
    console_handler = logging.StreamHandler(sys.stdout)
    if not json_format:
        console_handler.setFormatter(formatter)
    else:
        # Use simple format for console even in production
        console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()), handlers=[file_handler, console_handler]
    )
