#!/usr/bin/env python3
"""
VFS-Bot - Automated VFS appointment booking bot.

Main entry point for the application.
"""

import argparse
import asyncio
import os
import sys

from loguru import logger

from src.core.config.config_loader import load_config
from src.core.config.config_validator import ConfigValidator
from src.core.config.env_validator import EnvValidator
from src.core.infra.monitoring import init_sentry
from src.core.infra.runners import run_both_mode, run_bot_mode, run_web_mode
from src.core.infra.shutdown import setup_signal_handlers
from src.core.infra.startup import validate_environment, verify_critical_dependencies
from src.core.infra.startup_validator import log_security_warnings
from src.core.logger import setup_structured_logging


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

    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()

    try:
        # Phase 1: Pre-flight - Environment validation
        logger.info("Phase 1 (Pre-flight): Starting environment validation...")
        validate_environment()
        EnvValidator.validate(strict=True)
        log_security_warnings(strict=True)
        logger.info("Phase 1 (Pre-flight): Environment validation completed")

        # Phase 1: Pre-flight - Dependency verification
        logger.info("Phase 1 (Pre-flight): Verifying critical dependencies...")
        verify_critical_dependencies()
        logger.info("Phase 1 (Pre-flight): Critical dependencies verified")

        # Phase 2: Monitoring - Initialize Sentry (now that env vars are validated)
        logger.info("Phase 2 (Monitoring): Initializing Sentry monitoring...")
        init_sentry()
        logger.info("Phase 2 (Monitoring): Sentry monitoring initialized")

        # Phase 3: Config - Load and validate configuration
        logger.info("Phase 3 (Config): Loading configuration...")
        config = load_config(args.config)
        logger.info("Phase 3 (Config): Configuration loaded successfully")

        logger.info("Phase 3 (Config): Validating configuration...")
        if not ConfigValidator.validate(config):
            logger.error("Phase 3 (Config): Invalid configuration, exiting...")
            sys.exit(1)
        logger.info("Phase 3 (Config): Configuration validation completed")

        # Phase 4: Run - Start application in selected mode
        logger.info(f"Phase 4 (Run): Starting application in '{args.mode}' mode...")
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
    except KeyboardInterrupt:
        logger.info("Application interrupted by user (Ctrl+C)")
        sys.exit(130)
    except SystemExit:
        raise  # Let SystemExit propagate naturally
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
