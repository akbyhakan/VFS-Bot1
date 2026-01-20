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
    MIN_SECRET_KEY_LENGTH = 32
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
