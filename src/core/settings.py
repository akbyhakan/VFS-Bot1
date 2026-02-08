"""Application settings with Pydantic validation."""

from typing import List, Optional

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class VFSSettings(BaseSettings):
    """Application settings with validation and environment variable support."""

    # VFS Credentials
    vfs_email: str = Field(default="", description="VFS Global account email")
    vfs_password: SecretStr = Field(
        default=SecretStr(""), description="VFS Global account password"
    )

    # Encryption Keys
    encryption_key: SecretStr = Field(
        ...,  # Required field
        description=(
            "Base64-encoded Fernet encryption key for password encryption. "
            "Must be 32 bytes (44 characters when base64 encoded). "
            'Generate with: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        ),
    )
    vfs_encryption_key: Optional[SecretStr] = Field(
        default=None, description="Optional separate encryption key for VFS-specific data"
    )

    # API Security
    api_secret_key: SecretStr = Field(
        ..., description="Secret key for API authentication (JWT signing)"  # Required field
    )
    api_key_salt: Optional[SecretStr] = Field(
        default=None, description="Optional salt for API key generation"
    )

    # Environment
    env: str = Field(
        default="production", description="Environment (production, development, testing)"
    )

    # Database Configuration
    database_url: str = Field(
        default="postgresql://localhost:5432/vfs_bot",
        description="PostgreSQL database connection URL"
    )
    db_pool_size: int = Field(default=10, ge=1, le=100, description="Database connection pool size")
    db_connection_timeout: float = Field(
        default=30.0, gt=0, description="Database connection timeout in seconds"
    )

    # CORS Configuration
    cors_allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated list of allowed CORS origins",
    )

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests: int = Field(
        default=60, ge=1, description="Maximum requests per time window"
    )
    rate_limit_window: int = Field(
        default=60, ge=1, description="Rate limit time window in seconds"
    )

    # Webhook Configuration
    sms_webhook_secret: Optional[SecretStr] = Field(
        default=None, description="Secret for SMS webhook signature verification"
    )

    # Monitoring
    metrics_enabled: bool = Field(default=True, description="Enable Prometheus metrics")

    # Logging
    log_level: str = Field(
        default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    # VFS Bot Configuration
    check_interval: int = Field(
        default=60, ge=10, le=3600, description="Interval between slot checks in seconds"
    )
    max_retries: int = Field(
        default=3, ge=1, le=10, description="Maximum retry attempts for operations"
    )
    headless: bool = Field(default=True, description="Run browser in headless mode")

    # Notification Settings
    telegram_enabled: bool = Field(default=False, description="Enable Telegram notifications")
    telegram_bot_token: Optional[SecretStr] = Field(default=None, description="Telegram bot token")
    telegram_chat_id: Optional[str] = Field(default=None, description="Telegram chat ID")

    email_enabled: bool = Field(default=False, description="Enable email notifications")
    smtp_server: Optional[str] = Field(default=None, description="SMTP server address")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_username: Optional[str] = Field(default=None, description="SMTP username")
    smtp_password: Optional[SecretStr] = Field(default=None, description="SMTP password")
    email_from: Optional[str] = Field(default=None, description="Email sender address")
    email_to: Optional[str] = Field(default=None, description="Email recipient address")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields in .env
    )

    @field_validator("vfs_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format."""
        if v and "@" not in v:
            raise ValueError("Invalid email format")
        return v

    @field_validator("api_secret_key")
    @classmethod
    def validate_secret_key_length(cls, v: SecretStr) -> SecretStr:
        """Validate API secret key length."""
        secret_value = v.get_secret_value()
        if len(secret_value) < 64:
            raise ValueError("API_SECRET_KEY must be at least 64 characters")
        return v

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key_format(cls, v: SecretStr) -> SecretStr:
        """Validate encryption key format (should be base64)."""
        import base64

        try:
            key_value = v.get_secret_value()
            # Try to decode as base64
            base64.b64decode(key_value)
            return v
        except Exception:
            raise ValueError("ENCRYPTION_KEY must be a valid base64-encoded string")

    @field_validator("env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        """Validate environment value."""
        allowed = ["production", "development", "testing", "staging"]
        if v.lower() not in allowed:
            raise ValueError(f'ENV must be one of: {", ".join(allowed)}')
        return v.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f'LOG_LEVEL must be one of: {", ".join(allowed)}')
        return v_upper

    def get_cors_origins(self) -> List[str]:
        """
        Get CORS allowed origins as a list.

        Returns:
            List of allowed origin URLs
        """
        return [origin.strip() for origin in self.cors_allowed_origins.split(",")]

    def is_development(self) -> bool:
        """
        Check if running in development mode.

        Returns:
            True if development environment
        """
        return self.env == "development"

    def is_production(self) -> bool:
        """
        Check if running in production mode.

        Returns:
            True if production environment
        """
        return self.env == "production"


# Singleton instance
_settings: Optional[VFSSettings] = None


def get_settings() -> VFSSettings:
    """
    Get application settings singleton.

    Returns:
        VFSSettings instance

    Raises:
        ValidationError: If required settings are missing or invalid
    """
    global _settings
    if _settings is None:
        _settings = VFSSettings()  # type: ignore[call-arg]
    return _settings


def reset_settings() -> None:
    """Reset settings singleton (useful for testing)."""
    global _settings
    _settings = None
