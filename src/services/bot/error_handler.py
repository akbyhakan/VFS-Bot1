"""Error handling and screenshot capture service."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
from playwright.async_api import Page


class ErrorHandler:
    """Handles error capture, screenshots, and checkpoint saving."""

    def __init__(self, screenshots_dir: str = "screenshots", checkpoint_dir: str = "data"):
        """
        Initialize error handler.

        Args:
            screenshots_dir: Directory to save screenshots (default: "screenshots")
            checkpoint_dir: Directory to save checkpoints (default: "data")
        """
        self.screenshots_dir = Path(screenshots_dir)
        self.checkpoint_dir = Path(checkpoint_dir)

        # Ensure directories exist
        self.screenshots_dir.mkdir(exist_ok=True)
        self.checkpoint_dir.mkdir(exist_ok=True)

    async def handle_error(
        self, page: Page, error: Exception, context: Dict[str, Any]
    ) -> Optional[Path]:
        """
        Handle error by capturing context and taking screenshot.

        Args:
            page: Playwright page object
            error: Exception that occurred
            context: Context dictionary with error details

        Returns:
            Path to screenshot if successful, None otherwise
        """
        try:
            timestamp = datetime.now(timezone.utc).timestamp()
            error_name = context.get("error_name", "error")
            screenshot_name = f"{error_name}_{timestamp}"

            logger.error(f"Handling error: {error}", exc_info=True)
            logger.debug(f"Error context: {context}")

            screenshot_path = await self.take_screenshot(page, screenshot_name)
            return screenshot_path

        except Exception as e:
            logger.error(f"Failed to handle error: {e}")
            return None

    async def take_screenshot(self, page: Page, name: str) -> Optional[Path]:
        """
        Take a screenshot of the current page.

        Args:
            page: Playwright page object
            name: Screenshot filename (without extension)

        Returns:
            Path to screenshot file if successful, None otherwise
        """
        try:
            filepath = self.screenshots_dir / f"{name}.png"
            await page.screenshot(path=str(filepath), full_page=True)
            logger.info(f"Screenshot saved: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return None

    async def save_checkpoint(self, state: Dict[str, Any]) -> Optional[Path]:
        """
        Save current state to checkpoint file for recovery.

        Args:
            state: State dictionary to save

        Returns:
            Path to checkpoint file if successful, None otherwise
        """
        try:
            checkpoint_file = self.checkpoint_dir / "checkpoint.json"

            checkpoint_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **state,
            }

            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint_data, f, indent=2)

            logger.info(f"Checkpoint saved to {checkpoint_file}")
            return checkpoint_file

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return None

    def load_checkpoint(self) -> Dict[str, Any] | None:
        """
        Load state from checkpoint file.

        Returns:
            State dictionary if checkpoint exists, None otherwise
        """
        try:
            checkpoint_file = self.checkpoint_dir / "checkpoint.json"

            if not checkpoint_file.exists():
                logger.debug("No checkpoint file found")
                return None

            with open(checkpoint_file, "r") as f:
                checkpoint_data = json.load(f)

            logger.info(f"Checkpoint loaded from {checkpoint_file}")
            return dict(checkpoint_data)

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
