"""Monitoring and error tracking with Sentry."""

import logging
import os
from typing import Any, Dict, Optional

from loguru import logger


def init_sentry() -> None:
    """Initialize Sentry with PCI-DSS compliant filtering."""
    sentry_dsn = os.getenv("SENTRY_DSN")

    if not sentry_dsn:
        logger.warning("SENTRY_DSN not set - monitoring disabled")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=os.getenv("ENV", "production"),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            integrations=[LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)],
            before_send=filter_sensitive_data,
        )

        logger.info("Sentry initialized")
    except ImportError:
        logger.warning("sentry-sdk not installed - monitoring disabled")
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")


def filter_sensitive_data(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Filter CVV, passwords, tokens from error reports."""
    sensitive_keys = ["cvv", "password", "token", "api_key", "card_number"]

    if "request" in event and "data" in event["request"]:
        for key in sensitive_keys:
            if key in event["request"]["data"]:
                event["request"]["data"][key] = "[FILTERED]"

    return event
