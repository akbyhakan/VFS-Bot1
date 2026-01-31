"""Advanced logging with Loguru."""

import logging
import json
import sys
import contextvars
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from types import FrameType
from pathlib import Path
from loguru import logger


# Context variable for request correlation ID
correlation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record):
        record.correlation_id = correlation_id_ctx.get() or "N/A"
        return True


class JSONFormatter(logging.Formatter):
    """Format log records as JSON - kept for backward compatibility."""

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

        # Add correlation ID if available
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id

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
    Setup Loguru logging with structured output.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON format (True for production)
    """
    # Remove default handler
    logger.remove()

    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Console handler - human readable
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(
        sys.stdout,
        format=console_format,
        level=level,
        colorize=True,
    )

    # File handler - JSON for production or text for development
    if json_format:
        logger.add(
            logs_dir / "vfs_bot.jsonl",
            format="{message}",
            level=level,
            rotation="10 MB",  # Rotate when file reaches 10MB
            retention="30 days",  # Keep for 30 days
            compression="zip",  # Compress old logs
            serialize=True,  # JSON format
        )
    else:
        text_format = (
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | " "{name}:{function}:{line} - {message}"
        )
        logger.add(
            logs_dir / "vfs_bot.jsonl",
            format=text_format,
            level=level,
            rotation="10 MB",  # Rotate when file reaches 10MB
            retention="30 days",
            compression="zip",
        )

    # Error file - separate error logs
    logger.add(
        logs_dir / "errors_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="10 MB",
        retention="90 days",  # Keep errors longer
        backtrace=True,  # Include full traceback
        diagnose=True,  # Include variable values
    )

    logger.info(f"Logging initialized (level={level}, json={json_format})")

    # Intercept standard logging and redirect to loguru
    class InterceptHandler(logging.Handler):
        def emit(self, record):
            # Get corresponding Loguru level if it exists
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller from where originated the logged message
            frame: Optional[FrameType] = logging.currentframe()
            depth = 2
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

    # Intercept all standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Set the root logger level to match the configured level
    logging.root.setLevel(getattr(logging, level))
