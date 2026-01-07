#!/usr/bin/env python3
"""
VFS-Bot - Automated VFS appointment booking bot.

Main entry point for the application.
"""

import asyncio
import logging
import sys
from pathlib import Path
import argparse

from src.config_loader import load_config
from src.database import Database
from src.notification import NotificationService
from src.bot import VFSBot


def setup_logging(level: str = "INFO") -> None:
    """
    Setup logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configure logging
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=log_format,
        handlers=[
            logging.FileHandler(logs_dir / "vfs_bot.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Logging initialized")


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
        notifier = NotificationService(config['notifications'])
        
        # Initialize and start bot
        bot = VFSBot(config, db, notifier)
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
    config_uvicorn = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
    server = uvicorn.Server(config_uvicorn)
    await server.serve()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="VFS-Bot - Automated appointment booking")
    parser.add_argument(
        "--mode",
        choices=["bot", "web", "both"],
        default="both",
        help="Run mode: bot (automated), web (dashboard only), both (default)"
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = load_config(args.config)
        logger.info("Configuration loaded successfully")
        
        # Run in selected mode
        if args.mode == "bot":
            asyncio.run(run_bot_mode(config))
        elif args.mode == "web":
            asyncio.run(run_web_mode(config))
        else:  # both
            logger.info("Running in combined mode (bot + web)")
            # For now, just run web mode
            # TODO: Implement concurrent bot + web execution
            asyncio.run(run_web_mode(config))
            
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        logger.info("Please copy config/config.example.yaml to config/config.yaml and configure it")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()