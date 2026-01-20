"""Configuration schema validation."""

import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, HttpUrl, validator, model_validator

logger = logging.getLogger(__name__)


class VFSConfig(BaseModel):
    """VFS configuration schema."""

    base_url: HttpUrl = Field(..., description="VFS base URL (must be HTTPS)")
    country: str = Field(..., min_length=2, max_length=3, description="Country code")
    mission: str = Field(..., min_length=2, max_length=3, description="Mission code")
    centres: List[str] = Field(..., description="List of VFS centres")

    @validator("base_url")
    def validate_https(cls, v):
        """Ensure URL is HTTPS."""
        if not str(v).startswith("https://"):
            raise ValueError("VFS base_url must use HTTPS")
        return v

    @model_validator(mode="after")
    def check_centres(self):
        """Validate that centres list contains at least one centre."""
        if not self.centres:
            raise ValueError("List of VFS centres must contain at least one centre")
        return self


class BotConfig(BaseModel):
    """Bot configuration schema."""

    check_interval: int = Field(..., ge=10, le=3600, description="Check interval (10-3600 seconds)")
    headless: bool = Field(default=False, description="Run browser in headless mode")
    screenshot_on_error: bool = Field(default=True, description="Take screenshots on errors")
    max_retries: int = Field(default=3, ge=1, le=10, description="Maximum retries (1-10)")


class NotificationConfig(BaseModel):
    """Notification configuration schema."""

    telegram: Optional[Dict[str, Any]] = Field(default=None)
    email: Optional[Dict[str, Any]] = Field(default=None)


class CaptchaConfig(BaseModel):
    """Captcha configuration schema."""

    provider: str = Field(..., description="Captcha provider")
    api_key: str = Field(default="", description="Captcha API key")
    manual_timeout: int = Field(default=120, ge=30, le=600, description="Manual timeout (30-600s)")

    @validator("provider")
    def validate_provider(cls, v):
        """Validate captcha provider."""
        valid_providers = ["manual", "2captcha", "anticaptcha", "nopecha"]
        if v not in valid_providers:
            raise ValueError(f'provider must be one of: {", ".join(valid_providers)}')
        return v


class AppConfig(BaseModel):
    """Complete application configuration schema."""

    vfs: VFSConfig
    bot: BotConfig
    captcha: CaptchaConfig
    notifications: NotificationConfig
    anti_detection: Optional[Dict[str, Any]] = Field(default=None)
    appointments: Optional[Dict[str, Any]] = Field(default=None)

    class Config:
        """Pydantic config."""

        extra = "allow"  # Allow extra fields for flexibility


class ConfigValidator:
    """Validate configuration schema."""

    REQUIRED_SECTIONS = ["vfs", "bot", "captcha", "notifications"]

    VFS_REQUIRED = ["base_url", "country", "mission"]
    BOT_REQUIRED = ["check_interval"]

    @classmethod
    def validate(cls, config: Dict[str, Any]) -> bool:
        """
        Validate configuration structure using Pydantic.

        Args:
            config: Configuration dictionary

        Returns:
            True if valid
        """
        errors: List[str] = []

        # Try Pydantic validation first
        try:
            AppConfig(**config)
            logger.info("✅ Configuration validation passed (Pydantic)")
            return True
        except Exception as e:
            logger.warning(f"Pydantic validation failed, falling back to manual: {e}")

        # Fallback to manual validation for backwards compatibility
        # Check required sections
        for section in cls.REQUIRED_SECTIONS:
            if section not in config:
                errors.append(f"Missing required section: {section}")

        # Validate VFS section
        if "vfs" in config:
            for field in cls.VFS_REQUIRED:
                if field not in config["vfs"]:
                    errors.append(f"Missing vfs.{field}")

            # Validate HTTPS
            base_url = config["vfs"].get("base_url", "")
            if base_url and not base_url.startswith("https://"):
                errors.append("vfs.base_url must use HTTPS")

            # Validate centres
            centres = config["vfs"].get("centres", [])
            if not centres or len(centres) < 1:
                errors.append("vfs.centres must contain at least 1 centre")

        # Validate bot section
        if "bot" in config:
            for field in cls.BOT_REQUIRED:
                if field not in config["bot"]:
                    errors.append(f"Missing bot.{field}")

            # Validate check_interval range
            interval = config["bot"].get("check_interval", 0)
            if interval < 10 or interval > 3600:
                errors.append("bot.check_interval must be between 10 and 3600 seconds")

        # Report errors
        if errors:
            logger.error("❌ Configuration validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return False

        logger.info("✅ Configuration validation passed")
        return True

    @classmethod
    def validate_strict(cls, config: Dict[str, Any]) -> AppConfig:
        """
        Validate configuration strictly using Pydantic.

        Args:
            config: Configuration dictionary

        Returns:
            Validated AppConfig instance

        Raises:
            ValueError: If validation fails
        """
        try:
            return AppConfig(**config)
        except Exception as e:
            raise ValueError(f"Configuration validation failed: {e}") from e

    @classmethod
    def validate_environment_variables(cls) -> List[str]:
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
        import re
        
        errors = []
        env = os.getenv("ENV", "production").lower()
        
        # 1. ADMIN_PASSWORD validation
        admin_password = os.getenv("ADMIN_PASSWORD")
        if admin_password and env == "production":
            bcrypt_prefixes = ("$2b$", "$2a$", "$2y$")
            if not admin_password.startswith(bcrypt_prefixes):
                errors.append(
                    "ADMIN_PASSWORD must be bcrypt hashed in production. "
                    "Use: python -c \"from passlib.context import CryptContext; "
                    "print(CryptContext(schemes=['bcrypt']).hash('your-password'))\""
                )
        
        # 2. API_SECRET_KEY validation
        api_secret = os.getenv("API_SECRET_KEY")
        if api_secret:
            MIN_API_KEY_LENGTH = 64
            if len(api_secret) < MIN_API_KEY_LENGTH:
                errors.append(
                    f"API_SECRET_KEY must be at least {MIN_API_KEY_LENGTH} characters for security. Current length: {len(api_secret)}"
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
                            errors.append("ENCRYPTION_KEY is not a valid Fernet key (must decode to 32 bytes)")
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
                    f"CAPTCHA_API_KEY should be at least {MIN_CAPTCHA_KEY_LENGTH} characters. Current length: {len(captcha_key)}"
                )
        
        return errors
