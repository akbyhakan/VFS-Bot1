"""Environment variables validation."""

import os
import re
import sys
from typing import Dict, List

from loguru import logger

# Bcrypt hash prefixes for validation
BCRYPT_PREFIXES = ("$2b$", "$2a$", "$2y$")

# Known placeholder/example values that should never be used in production
DANGEROUS_PLACEHOLDERS = frozenset({
    "change_me_to_secure_password",
    "your-secret-key-here",
    "your_bot_token",
    "your-bot-token-here",
    "your-telegram-token",
    "your-api-key",
    "your-api-key-here",
    "replace-me",
    "changeme",
    "change-me",
    "example-key",
    "test-key",
    "your-encryption-key",
    "your-password-here",
    "your_email@example.com",
    "your-email@example.com",
    "example@example.com",
})


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

        # Check required
        for var, description in cls.REQUIRED_VARS.items():
            value = os.getenv(var)
            if not value:
                missing_required.append(f"{var} ({description})")
            else:
                # Check for dangerous placeholder values
                if cls._is_placeholder_value(value):
                    validation_errors.append(
                        f"{var}: Contains placeholder/example value. "
                        "Please replace with a real value."
                    )
                # Validate specific formats
                if var == "VFS_EMAIL":
                    if not cls._validate_email(value):
                        validation_errors.append(f"{var}: Invalid email format")
                elif var == "VFS_PASSWORD":
                    # Check if password is encrypted
                    is_encrypted = os.getenv("VFS_PASSWORD_ENCRYPTED", "false").lower() == "true"

                    if is_encrypted:
                        # Validate Fernet token format (base64-encoded, longer string)
                        if not cls._validate_fernet_token(value):
                            validation_errors.append(
                                f"{var}: Invalid encrypted password format (should be Fernet-encrypted)"
                            )
                    else:
                        # Plain text password validation
                        if len(value) < 8:
                            validation_errors.append(
                                f"{var}: Password too short (minimum 8 characters)"
                            )
                elif var == "ENCRYPTION_KEY":
                    if not cls._validate_encryption_key(value):
                        validation_errors.append(
                            f"{var}: Invalid encryption key "
                            "(must be 44-char base64-encoded Fernet key)"
                        )

        # Check optional vars with enhanced validation
        for var, description in cls.OPTIONAL_VARS.items():
            value = os.getenv(var)
            if not value:
                missing_optional.append(f"{var} ({description})")
            else:
                # Check for dangerous placeholder values
                if cls._is_placeholder_value(value):
                    validation_errors.append(
                        f"{var}: Contains placeholder/example value. "
                        "Please replace with a real value."
                    )
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

                # ADMIN_PASSWORD validation (ALL environments)
                elif var == "ADMIN_PASSWORD":
                    # Admin password should be bcrypt hashed in ALL environments
                    if not value.startswith(BCRYPT_PREFIXES):
                        validation_errors.append(
                            f"{var}: Must be bcrypt hashed in ALL environments. "
                            'Use: python -c "from passlib.context import CryptContext; '
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
    def _is_placeholder_value(value: str) -> bool:
        """
        Check if a value is a known placeholder/example value.

        Args:
            value: Value to check

        Returns:
            True if the value is a known placeholder
        """
        # Convert to lowercase once for all checks
        value_lower = value.lower()
        
        # Check exact matches (case-insensitive)
        if value_lower in DANGEROUS_PLACEHOLDERS:
            return True
        
        # Check common patterns
        placeholder_patterns = [
            "change",
            "replace",
            "example",
            "your-",
            "your_",
            "placeholder",
            "test-key",
            "dummy",
        ]
        
        return any(pattern in value_lower for pattern in placeholder_patterns)

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

    @staticmethod
    def _validate_fernet_token(token: str) -> bool:
        """
        Validate Fernet token format (encrypted data).

        Args:
            token: Fernet token to validate

        Returns:
            True if valid Fernet token format
        """
        try:
            import base64

            # Fernet tokens are base64-encoded and typically longer than plain text
            # Minimum 60 characters: Fernet adds ~41 bytes overhead (version byte +
            # timestamp + IV + padding) to the encrypted data, which becomes ~55 chars
            # in base64. A short password would still result in 60+ chars total.
            if len(token) < 60:
                return False

            # Try to decode as base64
            decoded = base64.urlsafe_b64decode(token.encode())

            # Fernet overhead: 1 byte version + 8 bytes timestamp + 16 bytes IV +
            # 16 bytes auth tag + PKCS7 padding = minimum ~40 bytes overhead
            # So any valid Fernet token should have at least 40 bytes
            if len(decoded) < 40:
                return False

            return True
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
