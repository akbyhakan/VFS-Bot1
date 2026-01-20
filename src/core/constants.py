"""Application-wide constants."""


class LogEmoji:
    """Emoji constants for consistent logging."""

    # Status indicators
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    DEBUG = "🔍"
    
    # Actions
    START = "🚀"
    STOP = "🛑"
    PROCESSING = "⚙️"
    WAITING = "⏳"
    RETRY = "🔄"
    
    # Results
    FOUND = "🎯"
    NOT_FOUND = "🔍"
    COMPLETE = "✔️"
    FAILED = "❌"
    
    # Security
    LOCK = "🔒"
    UNLOCK = "🔓"
    KEY = "🔑"
    SHIELD = "🛡️"
    ALERT = "🚨"
    
    # Network
    UPLOAD = "⬆️"
    DOWNLOAD = "⬇️"
    NETWORK = "🌐"
    API = "🔌"
    
    # Bot specific
    BOT = "🤖"
    USER = "👤"
    CALENDAR = "📅"
    TIME = "⏰"
    PAYMENT = "💳"
    EMAIL = "📧"
    PHONE = "📱"
    CAPTCHA = "🧩"
    SCREENSHOT = "📸"


class RateLimitDefaults:
    """Default rate limiting configuration."""

    MAX_REQUESTS = 60
    TIME_WINDOW = 60  # seconds
    BURST_MULTIPLIER = 2


class SecurityDefaults:
    """Default security configuration."""

    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_HOURS = 24
    MIN_SECRET_KEY_LENGTH = 64
    MIN_API_KEY_SALT_LENGTH = 32
    MIN_ENCRYPTION_KEY_LENGTH = 32
    PASSWORD_HASH_ROUNDS = 12
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    SESSION_FILE_PERMISSIONS = 0o600


class VFSDefaults:
    """VFS-specific defaults."""

    FORM_WAIT_SECONDS = 21
    PAYMENT_CONFIRMATION_WAIT_SECONDS = 60
    CHECK_INTERVAL_SECONDS = 30
    MAX_RETRIES = 3


class DatabaseDefaults:
    """Database configuration defaults."""

    POOL_SIZE = 10
    CONNECTION_TIMEOUT = 5.0
    QUERY_TIMEOUT = 30.0


class TimeoutDefaults:
    """Default timeout values in seconds."""
    
    HTTP_REQUEST = 30
    OTP_WAIT = 300
    PAYMENT_WAIT = 300
    DATABASE_CONNECTION = 30
    WEBSOCKET_PING = 30
    CIRCUIT_BREAKER_RESET = 60


class CircuitBreakerDefaults:
    """Default circuit breaker values."""
    
    FAIL_THRESHOLD = 5
    RESET_TIMEOUT = 60
    HALF_OPEN_MAX_CALLS = 3


class PoolDefaults:
    """Default pool sizes."""
    
    DATABASE_POOL_SIZE = 10
    HTTP_CONNECTION_LIMIT = 50
    HTTP_CONNECTION_LIMIT_PER_HOST = 20
