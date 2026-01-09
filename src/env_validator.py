"""Environment variables validation."""

import os
import sys
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class EnvValidator:
    """Validate required environment variables."""
    
    REQUIRED_VARS = {
        "VFS_EMAIL": "VFS account email",
        "VFS_PASSWORD": "VFS account password",
    }
    
    OPTIONAL_VARS = {
        "TELEGRAM_BOT_TOKEN": "Telegram bot token for notifications",
        "TELEGRAM_CHAT_ID": "Telegram chat ID for notifications",
        "EMAIL_SENDER": "Email sender address",
        "EMAIL_PASSWORD": "Email password/app password",
        "EMAIL_RECEIVER": "Email receiver address",
        "CAPTCHA_API_KEY": "Captcha solver API key",
    }
    
    @classmethod
    def validate(cls, strict: bool = False) -> bool:
        """
        Validate environment variables.
        
        Args:
            strict: If True, exit on missing required vars
            
        Returns:
            True if all required vars present
        """
        missing_required: List[str] = []
        missing_optional: List[str] = []
        
        # Check required
        for var, description in cls.REQUIRED_VARS.items():
            if not os.getenv(var):
                missing_required.append(f"{var} ({description})")
        
        # Check optional
        for var, description in cls.OPTIONAL_VARS.items():
            if not os.getenv(var):
                missing_optional.append(f"{var} ({description})")
        
        # Report
        if missing_required:
            logger.error("❌ Missing required environment variables:")
            for var in missing_required:
                logger.error(f"  - {var}")
            
            if strict:
                logger.error("\nPlease set these variables in .env file or environment.")
                logger.error("See .env.example for reference.")
                sys.exit(1)
            return False
        
        if missing_optional:
            logger.warning("⚠️  Missing optional environment variables:")
            for var in missing_optional:
                logger.warning(f"  - {var}")
            logger.info("Some features may be disabled.")
        
        logger.info("✅ Environment validation passed")
        return True
    
    @classmethod
    def get_masked_summary(cls) -> Dict[str, str]:
        """Get summary of env vars with masked values."""
        summary = {}
        
        for var in list(cls.REQUIRED_VARS.keys()) + list(cls.OPTIONAL_VARS.keys()):
            value = os.getenv(var)
            if value:
                # Mask sensitive data
                if len(value) > 8:
                    summary[var] = f"{value[:4]}...{value[-4:]}"
                else:
                    summary[var] = "***"
            else:
                summary[var] = "NOT SET"
        
        return summary
