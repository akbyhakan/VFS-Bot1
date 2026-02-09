"""JWT-based authentication for API endpoints."""

import asyncio
import logging
import os
import re
import threading
import time
import uuid
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, NamedTuple, Optional, cast

from fastapi import HTTPException, status
from jose import JWTError, jwt

from ..constants import RateLimits
from ..core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Supported JWT algorithms whitelist
SUPPORTED_JWT_ALGORITHMS = frozenset({
    "HS256", "HS384", "HS512",
    "RS256", "RS384", "RS512",
    "ES256", "ES384", "ES512"
})


class AuthRateLimiter:
    """
    Rate limiter for authentication endpoints to prevent brute-force attacks.
    
    **IMPORTANT: Multi-Worker Deployment Limitation**
    This implementation uses in-memory storage and is NOT safe for multi-worker
    deployments (e.g., `uvicorn --workers N`). Each worker maintains its own
    separate state, which makes rate limiting ineffective across workers.
    
    For production deployments with multiple workers, consider:
    - Using a shared cache backend like Redis
    - Implementing distributed rate limiting
    - Running with a single worker and scaling horizontally with a load balancer
    
    Future versions will support distributed backends via the `is_distributed`
    property.
    """

    # Maximum number of identifiers to track before triggering cleanup
    MAX_IDENTIFIERS_BEFORE_CLEANUP = 10000

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_attempts: Maximum authentication attempts allowed in window
            window_seconds: Time window in seconds
        """
        self._attempts: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    @property
    def is_distributed(self) -> bool:
        """
        Check if rate limiter is using distributed storage.
        
        Returns:
            False for in-memory implementation, True for distributed backends
            
        Note:
            This property is provided for future Redis/distributed backend support.
            Current implementation always returns False.
        """
        return False

    def is_rate_limited(self, identifier: str) -> bool:
        """
        Check if identifier is rate limited.

        Args:
            identifier: Unique identifier (e.g., username, IP address)

        Returns:
            True if rate limited
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=self.window_seconds)

            # Clean old attempts
            self._attempts[identifier] = [t for t in self._attempts[identifier] if t > cutoff]

            # Check rate limit status
            is_limited = len(self._attempts[identifier]) >= self.max_attempts

            # Clean up empty lists to prevent unbounded memory growth
            # Safe to delete here as we've already captured the rate limit status
            # and won't access this identifier again in this call
            if not self._attempts[identifier]:
                del self._attempts[identifier]

            return is_limited

    def record_attempt(self, identifier: str) -> None:
        """
        Record an authentication attempt.

        Args:
            identifier: Unique identifier (e.g., username, IP address)
        """
        with self._lock:
            self._attempts[identifier].append(datetime.now(timezone.utc))
            
            # Trigger cleanup when dict grows beyond a threshold
            if len(self._attempts) > self.MAX_IDENTIFIERS_BEFORE_CLEANUP:
                now = datetime.now(timezone.utc)
                cutoff = now - timedelta(seconds=self.window_seconds)
                stale_keys = [
                    k for k, v in self._attempts.items()
                    if not any(t > cutoff for t in v)
                ]
                for key in stale_keys:
                    del self._attempts[key]

    def cleanup_stale_entries(self) -> int:
        """
        Remove all stale entries that have no attempts within the current window.
        
        Should be called periodically to prevent unbounded memory growth
        from identifiers that recorded attempts but never called is_rate_limited again.
        
        Returns:
            Number of identifiers cleaned up
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=self.window_seconds)
            
            stale_keys = []
            for identifier, attempts in self._attempts.items():
                # Filter to only recent attempts
                recent = [t for t in attempts if t > cutoff]
                if not recent:
                    stale_keys.append(identifier)
                else:
                    self._attempts[identifier] = recent
            
            for key in stale_keys:
                del self._attempts[key]
            
            return len(stale_keys)

    def clear_attempts(self, identifier: str) -> None:
        """
        Clear all attempts for an identifier.

        Args:
            identifier: Unique identifier to clear
        """
        with self._lock:
            if identifier in self._attempts:
                del self._attempts[identifier]


# Global rate limiter instance
_auth_rate_limiter: Optional[AuthRateLimiter] = None
_rate_limiter_lock = threading.Lock()


def get_auth_rate_limiter() -> AuthRateLimiter:
    """
    Get or create auth rate limiter singleton.
    
    **WARNING: Multi-Worker Limitation**
    The rate limiter uses in-memory storage and is not shared across
    multiple worker processes. In multi-worker deployments (e.g.,
    `uvicorn --workers N`), each worker maintains separate state,
    reducing the effectiveness of rate limiting.
    
    For production multi-worker deployments, consider using a distributed
    rate limiting solution with Redis or similar shared storage.

    Returns:
        AuthRateLimiter instance
    """
    global _auth_rate_limiter
    if _auth_rate_limiter is not None:
        return _auth_rate_limiter
    with _rate_limiter_lock:
        if _auth_rate_limiter is None:
            # Get rate limit config from environment or use defaults
            max_attempts = RateLimits.AUTH_RATE_LIMIT_ATTEMPTS
            window_seconds = RateLimits.AUTH_RATE_LIMIT_WINDOW
            _auth_rate_limiter = AuthRateLimiter(
                max_attempts=max_attempts, window_seconds=window_seconds
            )
            
            # Log warning if running in multi-worker environment
            workers = os.getenv("WEB_CONCURRENCY") or os.getenv("UVICORN_WORKERS")
            if workers and int(workers) > 1:
                logger.warning(
                    f"⚠️ Auth rate limiter running with {workers} workers. "
                    "In-memory rate limiting is NOT shared across workers. "
                    "Consider using Redis-backed rate limiting for production."
                )
        return _auth_rate_limiter


class TokenBlacklist:
    """
    Thread-safe token blacklist for JWT revocation.

    Uses OrderedDict for efficient memory management with automatic cleanup
    of expired tokens.
    """

    def __init__(self, max_size: int = 10000):
        """
        Initialize token blacklist.

        Args:
            max_size: Maximum number of tokens to keep in memory
        """
        self._blacklist: OrderedDict[str, datetime] = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    def add(self, jti: str, exp: datetime) -> None:
        """
        Add a token to the blacklist.

        Args:
            jti: JWT ID (jti claim)
            exp: Token expiration time
        """
        with self._lock:
            # Remove expired tokens first
            self._cleanup_expired()

            # Add new token
            self._blacklist[jti] = exp

            # Enforce max size by removing oldest entries
            while len(self._blacklist) > self._max_size:
                self._blacklist.popitem(last=False)

    def is_blacklisted(self, jti: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            jti: JWT ID to check

        Returns:
            True if token is blacklisted
        """
        with self._lock:
            # Cleanup expired tokens
            self._cleanup_expired()
            return jti in self._blacklist

    def _cleanup_expired(self) -> None:
        """Remove expired tokens from blacklist (must be called with lock held)."""
        now = datetime.now(timezone.utc)
        expired_keys = [jti for jti, exp in self._blacklist.items() if exp < now]
        for jti in expired_keys:
            del self._blacklist[jti]

    def size(self) -> int:
        """Get current blacklist size."""
        with self._lock:
            return len(self._blacklist)

    async def start_cleanup_task(self, interval: int = 300) -> None:
        """
        Start background cleanup task.

        Args:
            interval: Cleanup interval in seconds (default: 5 minutes)
        """
        self._running = True
        while self._running:
            await asyncio.sleep(interval)
            with self._lock:
                self._cleanup_expired()
                logger.debug(f"Token blacklist cleanup: {len(self._blacklist)} tokens remaining")

    def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        self._running = False


class PersistentTokenBlacklist(TokenBlacklist):
    """
    Database-backed token blacklist for production environments.
    Falls back to memory if database unavailable.
    """

    def __init__(self, db: Optional[Any] = None, max_size: int = 10000):
        """
        Initialize persistent blacklist.

        Args:
            db: Database instance (optional)
            max_size: Maximum size of in-memory cache
        """
        super().__init__(max_size)
        self._db = db
        self._use_db = db is not None

    async def add_async(self, jti: str, exp: datetime) -> None:
        """Add token to blacklist with database persistence."""
        # Always add to memory cache
        self.add(jti, exp)

        # Persist to database if available
        if self._use_db and self._db:
            try:
                await self._db.add_blacklisted_token(jti, exp)
            except Exception as e:
                logger.warning(f"Failed to persist blacklisted token: {e}")

    async def is_blacklisted_async(self, jti: str) -> bool:
        """Check if token is blacklisted (checks both memory and database)."""
        # Check memory first (fast path)
        if self.is_blacklisted(jti):
            return True

        # Check database if available
        if self._use_db and self._db:
            try:
                return bool(await self._db.is_token_blacklisted(jti))
            except Exception as e:
                logger.warning(f"Failed to check blacklist in database: {e}")

        return False

    async def load_from_database(self) -> int:
        """Load active blacklisted tokens from database on startup."""
        if not self._use_db or not self._db:
            return 0

        try:
            tokens = await self._db.get_active_blacklisted_tokens()
            for jti, exp in tokens:
                self.add(jti, exp)
            logger.info(f"Loaded {len(tokens)} blacklisted tokens from database")
            return len(tokens)
        except Exception as e:
            logger.error(f"Failed to load blacklist from database: {e}")
            return 0

    async def start_cleanup_task(self, interval: int = 300) -> None:
        """
        Start background cleanup task for both memory and database.

        This method completely overrides the parent's implementation to add
        database cleanup capability while maintaining in-memory cleanup.
        
        The parent's logic is reimplemented here to avoid complexity from
        coordination between parent's task and database cleanup scheduling.

        Args:
            interval: Cleanup interval in seconds (default: 5 minutes)
        """
        self._running = True
        db_cleanup_counter = 0

        while self._running:
            await asyncio.sleep(interval)

            # In-memory cleanup (every interval)
            with self._lock:
                self._cleanup_expired()
                logger.debug(
                    f"Token blacklist cleanup: {len(self._blacklist)} tokens remaining"
                )

            # Database cleanup (every 6th interval ≈ 30 minutes)
            db_cleanup_counter += 1
            if db_cleanup_counter >= 6 and self._use_db and self._db:
                db_cleanup_counter = 0
                try:
                    deleted = await self._db.cleanup_expired_tokens()
                    if deleted > 0:
                        logger.info(
                            f"Database token cleanup: removed {deleted} expired tokens"
                        )
                except Exception as e:
                    logger.warning(f"Database token cleanup failed: {e}")


# Global token blacklist instance
_token_blacklist: Optional[TokenBlacklist] = None
_blacklist_lock = threading.Lock()


def get_token_blacklist() -> TokenBlacklist:
    """
    Get global token blacklist instance (singleton).

    Returns:
        TokenBlacklist instance
    """
    global _token_blacklist
    with _blacklist_lock:
        if _token_blacklist is None:
            _token_blacklist = TokenBlacklist()
        return _token_blacklist


# Bcrypt has a maximum password length of 72 bytes
MAX_PASSWORD_BYTES = 72

# Monkey-patch passlib to handle bcrypt 5.0.0 compatibility
# passlib 1.7.4's detect_wrap_bug creates a 200-char test password which exceeds
# bcrypt 5.0.0's strict 72-byte limit. We patch it to truncate test passwords.
import passlib.handlers.bcrypt as _pbcrypt  # noqa: E402

_original_calc_checksum = _pbcrypt._BcryptBackend._calc_checksum


def _patched_calc_checksum(self, secret):
    """Patched _calc_checksum that truncates passwords to 72 bytes for bcrypt 5.0.0."""
    if isinstance(secret, bytes) and len(secret) > MAX_PASSWORD_BYTES:
        # Truncate at UTF-8 character boundaries to avoid corruption
        truncated = secret[:MAX_PASSWORD_BYTES]
        # Find valid UTF-8 boundary by stepping back if needed
        for i in range(len(truncated), 0, -1):
            try:
                truncated[:i].decode("utf-8")
                secret = truncated[:i]
                break
            except UnicodeDecodeError:
                continue
    return _original_calc_checksum(self, secret)


_pbcrypt._BcryptBackend._calc_checksum = _patched_calc_checksum

# Now we can safely import and create the password context
from passlib.context import CryptContext  # noqa: E402

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class JWTSettings(NamedTuple):
    """JWT configuration settings."""

    secret_key: str
    algorithm: str
    expire_hours: int


# TTL-based cache for JWT settings (replaces lru_cache for key rotation support)
_jwt_settings_cache: Optional[JWTSettings] = None
_jwt_settings_cache_time: float = 0
_JWT_SETTINGS_TTL: int = 300  # 5 minutes TTL


def _get_jwt_settings() -> JWTSettings:
    """
    Get JWT settings with lazy initialization and TTL-based cache.

    This replaces lru_cache to support key rotation without server restart.
    Settings are cached for 5 minutes, then refreshed from environment.

    Returns:
        JWTSettings named tuple with secret_key, algorithm, and expire_hours

    Raises:
        ValueError: If API_SECRET_KEY is not set or invalid
    """
    global _jwt_settings_cache, _jwt_settings_cache_time
    
    now = time.monotonic()
    
    # Return cached settings if still valid
    if _jwt_settings_cache is not None and (now - _jwt_settings_cache_time) < _JWT_SETTINGS_TTL:
        return _jwt_settings_cache
    
    # Load fresh settings from environment
    secret_key = os.getenv("API_SECRET_KEY")
    if not secret_key:
        raise ValueError(
            "API_SECRET_KEY environment variable must be set. "
            "Generate a secure random key with: "
            "python -c 'import secrets; print(secrets.token_urlsafe(48))'"
        )

    # Minimum 64 characters for 256-bit security
    MIN_SECRET_KEY_LENGTH = 64
    if len(secret_key) < MIN_SECRET_KEY_LENGTH:
        raise ValueError(
            f"API_SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters for security. "
            "Generate a secure random key with: "
            "python -c 'import secrets; print(secrets.token_urlsafe(48))'"
        )

    algorithm = os.getenv("JWT_ALGORITHM", "HS256")

    # Validate algorithm against whitelist
    if algorithm not in SUPPORTED_JWT_ALGORITHMS:
        raise ValueError(
            f"Unsupported JWT algorithm: {algorithm}. "
            f"Supported algorithms: {', '.join(sorted(SUPPORTED_JWT_ALGORITHMS))}"
        )

    try:
        expire_hours = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
    except (ValueError, TypeError):
        raise ValueError("JWT_EXPIRY_HOURS environment variable must be a valid integer")

    # Update cache
    _jwt_settings_cache = JWTSettings(secret_key=secret_key, algorithm=algorithm, expire_hours=expire_hours)
    _jwt_settings_cache_time = now
    
    return _jwt_settings_cache


def invalidate_jwt_settings_cache() -> None:
    """
    Invalidate JWT settings cache.
    
    This forces a reload of settings from environment on next access.
    Useful for testing or when key rotation is performed.
    """
    global _jwt_settings_cache, _jwt_settings_cache_time
    _jwt_settings_cache = None
    _jwt_settings_cache_time = 0


def get_secret_key() -> str:
    """Get the JWT secret key."""
    return _get_jwt_settings().secret_key


def get_algorithm() -> str:
    """Get the JWT algorithm."""
    return _get_jwt_settings().algorithm


def get_token_expire_hours() -> int:
    """Get the JWT token expiry hours."""
    return _get_jwt_settings().expire_hours


def _truncate_password(password: str) -> str:
    """
    Truncate password to 72 bytes for bcrypt, handling UTF-8 safely.

    Bcrypt has a maximum password length of 72 bytes. This function explicitly
    truncates passwords to 72 bytes, ensuring that multi-byte UTF-8 characters
    are handled correctly by finding valid character boundaries.

    Args:
        password: Plain text password

    Returns:
        Truncated password (max 72 bytes when encoded as UTF-8)

    Raises:
        ValueError: If unable to truncate to valid UTF-8 boundary
    """
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        # Only take complete characters that fit into MAX_PASSWORD_BYTES
        truncated_bytes = password_bytes[:MAX_PASSWORD_BYTES]
        # If decoding fails at the boundary, move back until we hit a valid boundary
        for i in range(len(truncated_bytes), 0, -1):
            try:
                return truncated_bytes[:i].decode("utf-8")
            except UnicodeDecodeError:
                continue
        # This should never happen with valid UTF-8 input, but handle it safely
        raise ValueError("Failed to truncate password to valid UTF-8 boundary")
    return password


def validate_password_length(password: str) -> None:
    """
    Validate password doesn't exceed bcrypt limit.

    Raises ValidationError if password exceeds the maximum length,
    providing clear feedback to users instead of silently truncating.

    Args:
        password: Password to validate

    Raises:
        ValidationError: If password exceeds maximum byte length
    """
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        raise ValidationError(
            f"Password exceeds maximum length of {MAX_PASSWORD_BYTES} bytes. "
            f"Current length: {len(password_bytes)} bytes. "
            "Please use a shorter password.",
            field="password",
        )


def validate_password_complexity(password: str) -> None:
    """
    Validate password meets complexity requirements.

    Requirements:
    - At least 12 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Args:
        password: Password to validate

    Raises:
        ValidationError: If password doesn't meet requirements
    """
    errors = []

    if len(password) < 12:
        errors.append("Password must be at least 12 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")
    if not re.search(r"[0-9]", password):
        errors.append("Password must contain at least one digit")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special character")

    if errors:
        raise ValidationError("; ".join(errors), field="password")


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create JWT access token with key version tracking.

    Args:
        data: Data to encode in token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token

    """
    secret_key = get_secret_key()
    algorithm = get_algorithm()
    expire_hours = get_token_expire_hours()
    key_version = os.getenv("API_KEY_VERSION", "1")

    to_encode = data.copy()

    # Generate unique token ID for blacklist support
    jti = str(uuid.uuid4())

    # Set timestamps
    iat = datetime.now(timezone.utc)
    if expires_delta:
        expire = iat + expires_delta
    else:
        expire = iat + timedelta(hours=expire_hours)

    # Add standard and custom claims
    to_encode.update(
        {"exp": expire, "iat": iat, "jti": jti, "type": "access", "key_version": key_version}
    )

    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    if isinstance(encoded_jwt, bytes):
        return encoded_jwt.decode()
    return str(encoded_jwt)


def _check_token_blacklist(payload: Dict[str, Any]) -> None:
    """
    Check if token is blacklisted.

    Args:
        payload: JWT payload containing jti

    Raises:
        HTTPException: If token is blacklisted
    """
    jti = payload.get("jti")
    if jti and get_token_blacklist().is_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode JWT token with key rotation support.

    First tries to verify with current API_SECRET_KEY.
    If that fails, falls back to API_SECRET_KEY_PREVIOUS for backward compatibility
    during key rotation periods.

    Args:
        token: JWT token to verify

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    secret_key = get_secret_key()
    algorithm = get_algorithm()

    # Try current key first
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])

        # Check if token is blacklisted using helper
        _check_token_blacklist(payload)

        return cast(dict[str, Any], payload)
    except JWTError as primary_error:
        # Try previous key for rotation support
        previous_key = os.getenv("API_SECRET_KEY_PREVIOUS")
        if previous_key:
            try:
                logger.debug("Attempting token verification with previous key")
                payload = jwt.decode(token, previous_key, algorithms=[algorithm])

                # Check blacklist for old key tokens too using helper
                _check_token_blacklist(payload)

                logger.info("Token verified with previous key - consider refreshing token")
                return cast(dict[str, Any], payload)
            except JWTError:
                # Both keys failed, raise original error
                pass

        # Production: Don't expose internal error details for security
        if os.getenv("ENV", "production").lower() == "production":
            detail = "Could not validate credentials"
        else:
            detail = f"Could not validate credentials: {str(primary_error)}"

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password

    Raises:
        ValidationError: If password exceeds maximum byte length
    """
    validate_password_length(password)  # Validate before hashing
    # Truncate for bcrypt (defensive - validation should prevent this case)
    truncated = _truncate_password(password)
    result = pwd_context.hash(truncated)
    return str(result)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        True if password matches
    """
    truncated = _truncate_password(plain_password)
    return bool(pwd_context.verify(truncated, hashed_password))


def validate_admin_password_format() -> bool:
    """
    Validate that ADMIN_PASSWORD is in bcrypt hash format in production.

    This function should be called at startup to ensure the admin password
    is properly hashed in production environments.

    Returns:
        True if validation passes

    Raises:
        ValueError: If ADMIN_PASSWORD is not properly formatted in production
    """
    admin_password = os.getenv("ADMIN_PASSWORD")
    env = os.getenv("ENV", "production").lower()

    # Skip validation if no password is set (optional var)
    if not admin_password:
        return True

    # In production, require bcrypt hash format
    if env == "production":
        bcrypt_prefixes = ("$2b$", "$2a$", "$2y$")
        if not admin_password.startswith(bcrypt_prefixes):
            raise ValueError(
                "ADMIN_PASSWORD must be bcrypt hashed in production environment. "
                "Current value appears to be plain text. "
                'Generate a hash using: python -c "from passlib.context import CryptContext; '
                "print(CryptContext(schemes=['bcrypt']).hash('your-password'))\""
            )

    return True


def revoke_token(token: str) -> bool:
    """
    Revoke a JWT token by adding it to the blacklist.

    Args:
        token: JWT token to revoke

    Returns:
        True if token was successfully revoked

    Raises:
        HTTPException: If token is invalid or already expired
    """
    try:
        # Decode without verifying to get claims (we just need jti and exp)
        secret_key = get_secret_key()
        algorithm = get_algorithm()
        payload = jwt.decode(
            token, secret_key, algorithms=[algorithm], options={"verify_exp": False}
        )

        jti = payload.get("jti")
        if not jti:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token does not contain jti claim",
            )

        exp = payload.get("exp")
        if not exp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token does not contain exp claim",
            )

        # Convert exp to datetime
        exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)

        # Add to blacklist
        get_token_blacklist().add(jti, exp_dt)
        logger.info(f"Token {jti[:8]}... revoked successfully")
        return True

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid token: {str(e)}",
        )
