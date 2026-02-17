"""Configuration schema validation."""

from typing import Any

from loguru import logger

from .config_models import AppConfig


class ConfigValidator:
    """Validate configuration schema."""

    @classmethod
    def validate(cls, config: dict[str, Any]) -> bool:
        """
        Validate configuration structure using Pydantic.

        If Pydantic validation fails, manual validation is run for diagnostic purposes
        to provide more detailed error messages, but the result is always False.

        Args:
            config: Configuration dictionary

        Returns:
            True if valid, False otherwise
        """
        # Try Pydantic validation first
        try:
            AppConfig(**config)
            logger.info("✅ Configuration validation passed (Pydantic)")
            return True
        except Exception as e:
            logger.error(f"❌ Pydantic validation failed: {e}")

            # Run manual validation for diagnostic purposes only
            # This provides more user-friendly error messages
            # The validate() method returns False after diagnostic validation runs
            cls._diagnostic_validation(config)
            return False

    @classmethod
    def _diagnostic_validation(cls, config: dict[str, Any]) -> None:
        """
        Run manual validation to provide user-friendly diagnostic messages.

        This is only called when Pydantic validation fails, to help users
        understand what's wrong with their configuration.

        Args:
            config: Configuration dictionary
        """
        logger.info("Running diagnostic validation for better error messages...")

        # Check for missing top-level sections
        required_sections = ["vfs", "bot", "captcha", "notifications"]
        missing_sections = [s for s in required_sections if s not in config]
        if missing_sections:
            logger.error(f"Missing required sections: {', '.join(missing_sections)}")

        # Check VFS section
        if "vfs" in config:
            vfs = config["vfs"]
            vfs_required = ["base_url", "country", "mission"]
            for field in vfs_required:
                if field not in vfs:
                    logger.error(f"Missing vfs.{field}")

            # Check HTTPS
            base_url = vfs.get("base_url", "")
            if base_url and not base_url.startswith("https://"):
                logger.error("vfs.base_url must use HTTPS")

            # Check centres
            centres = vfs.get("centres", [])
            if not centres or len(centres) < 1:
                logger.error("vfs.centres must contain at least 1 centre")

        # Check bot section
        if "bot" in config:
            bot = config["bot"]
            if "check_interval" not in bot:
                logger.error("Missing bot.check_interval")
            else:
                interval = bot.get("check_interval", 0)
                if interval < 10 or interval > 3600:
                    logger.error("bot.check_interval must be between 10 and 3600 seconds")

    @classmethod
    def validate_environment_variables(cls) -> list[str]:
        """
        Validate critical environment variables for security and correctness.

        This includes:
        - ADMIN_PASSWORD format check (bcrypt in production)
        - API_SECRET_KEY minimum length
        - ENCRYPTION_KEY format check

        Returns:
            List of validation error messages (empty if all pass)
        """
        import os

        errors = []
        env = os.getenv("ENV", "production").lower()

        # 1. ADMIN_PASSWORD validation
        admin_password = os.getenv("ADMIN_PASSWORD")
        if admin_password and env == "production":
            bcrypt_prefixes = ("$2b$", "$2a$", "$2y$")
            if not admin_password.startswith(bcrypt_prefixes):
                errors.append(
                    "ADMIN_PASSWORD must be bcrypt hashed in production. "
                    'Use: python -c "from passlib.context import CryptContext; '
                    "print(CryptContext(schemes=['bcrypt']).hash('your-password'))\""
                )

        # 2. API_SECRET_KEY validation
        api_secret = os.getenv("API_SECRET_KEY")
        if api_secret:
            MIN_API_KEY_LENGTH = 64
            if len(api_secret) < MIN_API_KEY_LENGTH:
                errors.append(
                    f"API_SECRET_KEY must be at least {MIN_API_KEY_LENGTH} "
                    f"characters for security. Current length: {len(api_secret)}"
                )

        # 3. ENCRYPTION_KEY validation
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if encryption_key:
            try:
                import base64
                from binascii import Error as Base64Error

                if len(encryption_key) != 44:
                    errors.append(
                        "ENCRYPTION_KEY must be 44 characters (Fernet key format). "
                        "Generate with: python -c 'from cryptography.fernet import Fernet; "
                        "print(Fernet.generate_key().decode())'"
                    )
                else:
                    # Validate it's valid base64
                    try:
                        decoded = base64.urlsafe_b64decode(encryption_key.encode())
                        if len(decoded) != 32:
                            errors.append(
                                "ENCRYPTION_KEY is not a valid Fernet key (must decode to 32 bytes)"
                            )
                    except (Base64Error, ValueError) as e:
                        errors.append(f"ENCRYPTION_KEY is not valid base64: {e}")
            except Exception as e:
                errors.append(f"ENCRYPTION_KEY validation failed: {e}")

        # 4. CAPTCHA_API_KEY validation
        captcha_key = os.getenv("CAPTCHA_API_KEY")
        if captcha_key:
            MIN_CAPTCHA_KEY_LENGTH = 16
            if len(captcha_key) < MIN_CAPTCHA_KEY_LENGTH:
                errors.append(
                    f"CAPTCHA_API_KEY should be at least {MIN_CAPTCHA_KEY_LENGTH} "
                    f"characters. Current length: {len(captcha_key)}"
                )

        return errors
