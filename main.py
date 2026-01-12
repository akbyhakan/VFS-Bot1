#!/usr/bin/env python3
"""
VFS-Bot - Automated VFS appointment booking bot.

Main entry point for the application.
"""

import asyncio
import logging
import sys
import os
import argparse
import signal

from src.core.config_loader import load_config
from src.models.database import Database
from src.services.notification import NotificationService
from src.services.bot_service import VFSBot
from src.core.logger import setup_structured_logging
from src.core.env_validator import EnvValidator
from src.core.config_validator import ConfigValidator


def setup_signal_handlers():
    """Setup graceful shutdown handlers."""
    logger = logging.getLogger(__name__)

    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)


async def run_bot_mode(config: dict) -> None:
    """
    Run bot in automated mode.

    Args:
        config: Configuration dictionary
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting VFS-Bot in automated mode...")

    # Initialize database
    db = Database()
    await db.connect()

    try:
        # Initialize notification service
        notifier = NotificationService(config["notifications"])

        # Initialize and start bot
        bot = VFSBot(config, db, notifier)

        # Initialize selector health monitoring (if enabled)
        # Note: The health checker will be started within the bot's browser context
        # when the browser is available. See VFSBot.start() for implementation.
        if config.get("selector_health_check", {}).get("enabled", True):
            from src.utils.selector_watcher import SelectorHealthCheck
            from src.utils.selectors import SelectorManager

            selector_manager = SelectorManager()
            bot.health_checker = SelectorHealthCheck(
                selector_manager,
                notifier,
                check_interval=config.get("selector_health_check", {}).get("interval", 3600),
            )
            logger.info("Selector health monitoring initialized")
        else:
            bot.health_checker = None

        await bot.start()

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)
    finally:
        await db.close()


async def run_web_mode(config: dict) -> None:
    """
    Run bot with web dashboard.

    Args:
        config: Configuration dictionary
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting VFS-Bot with web dashboard...")

    import uvicorn
    from web.app import app

    # Run uvicorn server
    config_uvicorn = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config_uvicorn)
    await server.serve()


async def run_both_mode(config: dict) -> None:
    """
    Run both bot and web dashboard concurrently.

    Args:
        config: Configuration dictionary
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting VFS-Bot in combined mode (bot + web)...")

    # Create tasks for both modes
    web_task = asyncio.create_task(run_web_mode(config))
    bot_task = asyncio.create_task(run_bot_mode(config))

    # Run both concurrently
    await asyncio.gather(web_task, bot_task, return_exceptions=True)


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
        # Validate environment variables
        logger.info("Validating environment variables...")
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
