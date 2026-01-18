"""Environment variables validation."""

import os
import sys
import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)


class EnvValidator:
    """Validate required environment variables."""

    REQUIRED_VARS = {
        "VFS_EMAIL": "VFS account email",
        "VFS_PASSWORD": "VFS account password",
        "ENCRYPTION_KEY": "Password encryption key (Fernet)",
    }

    OPTIONAL_VARS = {
        "TELEGRAM_BOT_TOKEN": "Telegram bot token for notifications",
        "TELEGRAM_CHAT_ID": "Telegram chat ID for notifications",
        "EMAIL_SENDER": "Email sender address",
        "EMAIL_PASSWORD": "Email password/app password",
        "EMAIL_RECEIVER": "Email receiver address",
        "CAPTCHA_API_KEY": "Captcha solver API key",
        "VFS_ENCRYPTION_KEY": "VFS API encryption key",
        "API_SECRET_KEY": "JWT secret key for API authentication",
        "ADMIN_PASSWORD": "Admin password for dashboard access",
        "SMS_WEBHOOK_SECRET": "SMS webhook signature secret",
    }

    @classmethod
    def validate(cls, strict: bool = False) -> bool:
        """
        Validate environment variables with enhanced security checks.

        Args:
            strict: If True, exit on missing required vars or validation errors

        Returns:
            True if all required vars present and valid
        """
        missing_required: List[str] = []
        missing_optional: List[str] = []
        validation_errors: List[str] = []
        env = os.getenv("ENV", "production").lower()

        # Check required
        for var, description in cls.REQUIRED_VARS.items():
            value = os.getenv(var)
            if not value:
                missing_required.append(f"{var} ({description})")
            else:
                # Validate specific formats
                if var == "VFS_EMAIL":
                    if not cls._validate_email(value):
                        validation_errors.append(f"{var}: Invalid email format")
                elif var == "VFS_PASSWORD":
                    if len(value) < 8:
                        validation_errors.append(f"{var}: Password too short (minimum 8 characters)")
                elif var == "ENCRYPTION_KEY":
                    if not cls._validate_encryption_key(value):
                        validation_errors.append(
                            f"{var}: Invalid encryption key (must be 44-char base64-encoded Fernet key)"
                        )

        # Check optional vars with enhanced validation
        for var, description in cls.OPTIONAL_VARS.items():
            value = os.getenv(var)
            if not value:
                missing_optional.append(f"{var} ({description})")
            else:
                # Validate optional var formats
                if var == "CAPTCHA_API_KEY" and len(value) < 16:
                    validation_errors.append(f"{var}: API key too short (minimum 16 characters)")
                
                # VFS_ENCRYPTION_KEY validation
                elif var == "VFS_ENCRYPTION_KEY" and len(value) < 32:
                    validation_errors.append(
                        f"{var}: Encryption key too short (minimum 32 bytes for AES-256)"
                    )
                
                # API_SECRET_KEY validation
                elif var == "API_SECRET_KEY":
                    if len(value) < 32:
                        validation_errors.append(
                            f"{var}: JWT secret too short (minimum 32 characters for security)"
                        )
                
                # ADMIN_PASSWORD validation (production only)
                elif var == "ADMIN_PASSWORD" and env == "production":
                    # In production, admin password should be bcrypt hashed
                    if not value.startswith("$2b$") and not value.startswith("$2a$"):
                        validation_errors.append(
                            f"{var}: Must be bcrypt hashed in production. "
                            "Use: python -c \"from passlib.context import CryptContext; "
                            "print(CryptContext(schemes=['bcrypt']).hash('your-password'))\""
                        )
                
                # SMS_WEBHOOK_SECRET validation
                elif var == "SMS_WEBHOOK_SECRET":
                    if len(value) < 32:
                        validation_errors.append(
                            f"{var}: Webhook secret too short (minimum 32 characters)"
                        )

        # Report errors
        if missing_required:
            logger.error("❌ Missing required environment variables:")
            for var in missing_required:
                logger.error(f"  - {var}")

        if validation_errors:
            logger.error("❌ Environment variable validation errors:")
            for error in validation_errors:
                logger.error(f"  - {error}")

        if missing_required or validation_errors:
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

    @staticmethod
    def _validate_email(email: str) -> bool:
        """
        Validate email format.

        Args:
            email: Email address to validate

        Returns:
            True if valid email format
        """
        # Basic email regex pattern
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    @staticmethod
    def _validate_encryption_key(key: str) -> bool:
        """
        Validate encryption key format (Fernet key).

        Args:
            key: Encryption key to validate

        Returns:
            True if valid Fernet key format
        """
        try:
            # Fernet keys are 44 characters of base64-encoded data
            if len(key) != 44:
                return False
            # Try to decode as base64
            import base64

            decoded = base64.urlsafe_b64decode(key.encode())
            # Fernet key should be 32 bytes
            return len(decoded) == 32
        except Exception:
            return False

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
