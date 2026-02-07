#!/usr/bin/env python3
"""
VFS-Bot - Automated VFS appointment booking bot.

Main entry point for the application.
"""

import argparse
import asyncio
import logging
import os
import sys

from src.core.config_loader import load_config
from src.core.config_validator import ConfigValidator
from src.core.env_validator import EnvValidator
from src.core.logger import setup_structured_logging
from src.core.monitoring import init_sentry
from src.core.runners import run_both_mode, run_bot_mode, run_web_mode
from src.core.shutdown import setup_signal_handlers
from src.core.startup import validate_environment, verify_critical_dependencies

# Backward compatibility - deprecated, use src.core.shutdown / src.core.startup directly
from src.core.shutdown import (  # noqa: F401
    fast_emergency_cleanup as _fast_emergency_cleanup,
)
from src.core.shutdown import graceful_shutdown  # noqa: F401
from src.core.shutdown import graceful_shutdown_with_timeout  # noqa: F401
from src.core.shutdown import (  # noqa: F401
    safe_shutdown_cleanup as _safe_shutdown_cleanup,
)
from src.core.startup import validate_environment  # noqa: F401


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="VFS-Bot - Automated appointment booking")
    parser.add_argument(
        "--mode",
        choices=["bot", "web", "both"],
        default="both",
        help="Run mode: bot (automated), web (dashboard only), both (default)",
    )
    parser.add_argument("--config", default="config/config.yaml", help="Path to configuration file")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Setup structured logging
    json_logging = os.getenv("JSON_LOGGING", "true").lower() == "true"
    setup_structured_logging(args.log_level, json_format=json_logging)
    logger = logging.getLogger(__name__)

    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()

    try:
        # Initialize Sentry monitoring
        init_sentry()

        # Verify critical dependencies
        verify_critical_dependencies()

        # Validate environment variables
        logger.info("Validating environment variables...")
        validate_environment()
        EnvValidator.validate(strict=True)

        # Load configuration
        logger.info("Loading configuration...")
        config = load_config(args.config)
        logger.info("Configuration loaded successfully")

        # Validate config
        if not ConfigValidator.validate(config):
            logger.error("Invalid configuration, exiting...")
            sys.exit(1)

        # Run in selected mode
        if args.mode == "bot":
            asyncio.run(run_bot_mode(config))
        elif args.mode == "web":
            asyncio.run(run_web_mode(config))
        else:  # both
            asyncio.run(run_both_mode(config))

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        logger.info("Please copy config/config.example.yaml to config/config.yaml and configure it")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
