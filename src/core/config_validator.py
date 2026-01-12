"""Configuration schema validation."""

import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, HttpUrl, validator

logger = logging.getLogger(__name__)


class VFSConfig(BaseModel):
    """VFS configuration schema."""
    
    base_url: HttpUrl = Field(..., description="VFS base URL (must be HTTPS)")
    country: str = Field(..., min_length=2, max_length=3, description="Country code")
    mission: str = Field(..., min_length=2, max_length=3, description="Mission code")
    centres: List[str] = Field(..., min_items=1, description="List of VFS centres")
    
    @validator('base_url')
    def validate_https(cls, v):
        """Ensure URL is HTTPS."""
        if not str(v).startswith('https://'):
            raise ValueError('VFS base_url must use HTTPS')
        return v


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
    
    @validator('provider')
    def validate_provider(cls, v):
        """Validate captcha provider."""
        valid_providers = ['manual', '2captcha', 'anticaptcha', 'nopecha']
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
        extra = 'allow'  # Allow extra fields for flexibility


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
