"""Application settings with Pydantic validation."""

from typing import Any, List, Optional

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class VFSSettings(BaseSettings):
    """Application settings with validation and environment variable support."""

    # Configuration Version
    config_version: Optional[str] = Field(
        default=None, description="Configuration schema version for compatibility checking"
    )

    # VFS Credentials
    vfs_email: str = Field(default="", description="VFS Global account email")
    vfs_password: SecretStr = Field(
        default=SecretStr(""), description="VFS Global account password"
    )
    vfs_password_encrypted: bool = Field(
        default=False, description="Flag indicating if VFS_PASSWORD is Fernet-encrypted"
    )

    # Encryption Keys
    encryption_key: Optional[SecretStr] = Field(
        default=None,
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
    api_secret_key: Optional[SecretStr] = Field(
        default=None, description="Secret key for API authentication (JWT signing)"
    )
    api_key_salt: Optional[SecretStr] = Field(
        default=None, description="Optional salt for API key generation"
    )

    # Environment
    env: str = Field(
        default="production", description="Environment (production, development, testing)"
    )

    @model_validator(mode="before")
    @classmethod
    def default_env_for_pytest(cls, data: Any) -> Any:
        """Auto-detect testing environment when running under pytest."""
        import sys

        # Ensure data is a dict
        if not isinstance(data, dict):
            return data

        # If env not set and we're running under pytest, default to testing
        if ("env" not in data or not data.get("env")) and "pytest" in sys.modules:
            data["env"] = "testing"

        return data

    # Database Configuration
    database_url: str = Field(
        default="postgresql://localhost:5432/vfs_bot",
        description="PostgreSQL database connection URL",
    )
    db_pool_size: int = Field(default=10, ge=1, le=100, description="Database connection pool size")
    db_connection_timeout: float = Field(
        default=30.0, gt=0, description="Database connection timeout in seconds"
    )

    # Redis Configuration
    redis_url: Optional[str] = Field(
        default=None,
        description=(
            "Redis URL for distributed rate limiting and caching (leave empty for in-memory). "
            "Read via os.getenv('REDIS_URL') in RedisManager, which manages the shared connection pool."
        ),
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

    # NOTE: Bot configuration parameters (check_interval, max_retries, headless,
    # notification settings) are managed via config/config.yaml (YAML Config).
    # See config_loader.py and config_validator.py for runtime configuration management.

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
    def validate_secret_key_length(cls, v: Optional[SecretStr]) -> Optional[SecretStr]:
        """Validate API secret key length."""
        if v is None:
            return None
        secret_value = v.get_secret_value()
        if len(secret_value) < 64:
            raise ValueError("API_SECRET_KEY must be at least 64 characters")
        return v

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key_format(cls, v: Optional[SecretStr]) -> Optional[SecretStr]:
        """Validate encryption key format (should be base64)."""
        if v is None:
            return None

        import base64

        key_value = v.get_secret_value()

        # Try URL-safe base64 first (Fernet standard), then regular base64
        decoded = None
        try:
            decoded = base64.urlsafe_b64decode(key_value)
        except Exception:
            try:
                decoded = base64.b64decode(key_value)
            except Exception:
                raise ValueError("ENCRYPTION_KEY must be a valid base64-encoded string")

        # Check length after successful decode
        if len(decoded) != 32:
            raise ValueError(
                f"ENCRYPTION_KEY must decode to exactly 32 bytes, got {len(decoded)}. "
                "Generate a valid key with: "
                'python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )

        return v

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

    @model_validator(mode="after")
    def ensure_required_keys_or_defaults(self) -> "VFSSettings":
        """
        Ensure encryption_key and api_secret_key are set.

        In production/staging: These fields are REQUIRED
        In testing/development: Auto-generate secure defaults if missing

        Returns:
            Self with keys populated

        Raises:
            ValueError: If required keys are missing in production/staging
        """
        import secrets
        from cryptography.fernet import Fernet

        is_test_or_dev = self.env in ("testing", "development")

        # Handle encryption_key
        if self.encryption_key is None:
            if is_test_or_dev:
                # Auto-generate for testing/development
                self.encryption_key = SecretStr(Fernet.generate_key().decode())
            else:
                raise ValueError(
                    "ENCRYPTION_KEY is required in production/staging. "
                    'Generate with: python -c "from cryptography.fernet import Fernet; '
                    'print(Fernet.generate_key().decode())"'
                )

        # Handle api_secret_key
        if self.api_secret_key is None:
            if is_test_or_dev:
                # Auto-generate for testing/development
                self.api_secret_key = SecretStr(secrets.token_urlsafe(48))
            else:
                raise ValueError(
                    "API_SECRET_KEY is required in production/staging. "
                    "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
                )

        return self

    @model_validator(mode="after")
    def decrypt_vfs_password(self) -> "VFSSettings":
        """
        Decrypt VFS password if it was stored encrypted.

        Returns:
            Self with decrypted password

        Raises:
            ValueError: If decryption fails
        """
        if self.vfs_password_encrypted:
            try:
                from cryptography.fernet import Fernet

                # Guard against None encryption_key
                if self.encryption_key is None:
                    raise ValueError(
                        "ENCRYPTION_KEY is required when VFS_PASSWORD_ENCRYPTED is True"
                    )
                encryption_key = self.encryption_key.get_secret_value()
                cipher = Fernet(encryption_key)

                # Decrypt the password
                encrypted_password = self.vfs_password.get_secret_value()
                decrypted_password = cipher.decrypt(encrypted_password.encode()).decode()

                # Update the password with decrypted value
                self.vfs_password = SecretStr(decrypted_password)

            except Exception as e:
                raise ValueError(
                    f"Failed to decrypt VFS_PASSWORD. Ensure ENCRYPTION_KEY is correct. Error: {e}"
                )

        return self

    @model_validator(mode="after")
    def validate_database_url_in_production(self) -> "VFSSettings":
        """
        Validate database URL in production environment.

        Ensures production deployments don't use insecure default database URLs
        without authentication credentials.

        Returns:
            Self if validation passes

        Raises:
            ValueError: If production environment uses insecure database URL
        """
        if self.env == "production":
            # Check if using the default insecure URL
            if self.database_url == "postgresql://localhost:5432/vfs_bot":
                raise ValueError(
                    "Production environment cannot use default DATABASE_URL. "
                    "Set DATABASE_URL with proper credentials in environment variables."
                )

            # Check if database URL contains authentication (@ symbol)
            if "@" not in self.database_url:
                raise ValueError(
                    "Production DATABASE_URL must contain authentication credentials. "
                    "Format: postgresql://user:password@host:port/database"
                )

        # In test/dev environments, allow any database URL including defaults
        return self

    def get_cors_origins(self) -> List[str]:
        """
        Get CORS allowed origins as a list, with security validation.

        Returns:
            List of validated allowed origin URLs
        """
        from web.cors import validate_cors_origins
        return validate_cors_origins(self.cors_allowed_origins)

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
        _settings = VFSSettings()
    return _settings


def reset_settings() -> None:
    """Reset settings singleton (useful for testing)."""
    global _settings
    _settings = None
