"""Configuration schema validation."""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validate configuration schema."""

    REQUIRED_SECTIONS = ["vfs", "bot", "captcha", "notifications"]

    VFS_REQUIRED = ["base_url", "country", "mission"]
    BOT_REQUIRED = ["check_interval"]

    @classmethod
    def validate(cls, config: Dict[str, Any]) -> bool:
        """
        Validate configuration structure.

        Args:
            config: Configuration dictionary

        Returns:
            True if valid
        """
        errors: List[str] = []

        # Check required sections
        for section in cls.REQUIRED_SECTIONS:
            if section not in config:
                errors.append(f"Missing required section: {section}")

        # Validate VFS section
        if "vfs" in config:
            for field in cls.VFS_REQUIRED:
                if field not in config["vfs"]:
                    errors.append(f"Missing vfs.{field}")

        # Validate bot section
        if "bot" in config:
            for field in cls.BOT_REQUIRED:
                if field not in config["bot"]:
                    errors.append(f"Missing bot.{field}")

            # Validate check_interval range
            interval = config["bot"].get("check_interval", 0)
            if interval < 10:
                errors.append("bot.check_interval must be >= 10 seconds")

        # Report errors
        if errors:
            logger.error("❌ Configuration validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return False

        logger.info("✅ Configuration validation passed")
        return True
