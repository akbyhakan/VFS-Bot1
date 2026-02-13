"""Password encryption utilities using Fernet symmetric encryption."""

import asyncio
import hashlib
import os
import threading
import time
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from loguru import logger

from src.core.environment import Environment


def _normalize_key(key: Optional[str | bytes]) -> str:
    """
    Normalize encryption key to string format.

    Args:
        key: Encryption key as string or bytes

    Returns:
        Key as string
    """
    if isinstance(key, bytes):
        return key.decode()
    elif isinstance(key, str):
        return key
    else:
        raise ValueError("Encryption key must be string or bytes")


class PasswordEncryption:
    """Handles password encryption and decryption using Fernet."""

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption with key.

        Args:
            encryption_key: Base64-encoded Fernet key. If None, reads from env.

        Raises:
            ValueError: If encryption key is not provided or invalid
        """
        key = encryption_key or os.getenv("ENCRYPTION_KEY")
        if not key:
            raise ValueError(
                "ENCRYPTION_KEY must be set in environment variables. "
                'Generate one with: python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )

        try:
            # Normalize and store key for comparison
            self._key = _normalize_key(key)
            # Generate key hash for identification
            self._key_hash = hashlib.sha256(self._key.encode()).hexdigest()[:16]
            # Create cipher with normalized key
            cipher_key = key.encode() if isinstance(key, str) else key
            
            # Build key list: new key first, then old key (if available)
            fernet_keys = [Fernet(cipher_key)]
            old_key = os.getenv("ENCRYPTION_KEY_OLD")
            if old_key:
                try:
                    old_cipher_key = old_key.encode() if isinstance(old_key, str) else old_key
                    fernet_keys.append(Fernet(old_cipher_key))
                    logger.info("Old encryption key loaded for key rotation support")
                except Exception as e:
                    logger.warning(f"Failed to load old encryption key: {e}")
            
            self.cipher = MultiFernet(fernet_keys)

            # Only log key hash in non-production environments
            if not Environment.is_production():
                logger.debug(f"Password encryption initialized (key hash: {self._key_hash})")
            else:
                logger.info("Password encryption initialized successfully")
        except Exception as e:
            raise ValueError(f"Invalid ENCRYPTION_KEY: {e}") from e

    @property
    def key_hash(self) -> str:
        """Return truncated hash of current key for identification."""
        return self._key_hash

    def can_decrypt(self, encrypted_data: str) -> bool:
        """
        Check if current key can decrypt the given data.

        Args:
            encrypted_data: Encrypted data to test

        Returns:
            True if data can be decrypted with current key
        """
        try:
            self.cipher.decrypt(encrypted_data.encode())
            return True
        except InvalidToken:
            return False
        except Exception:
            return False

    def needs_migration(self, encrypted_data: str) -> bool:
        """
        Check if encrypted data needs to be migrated from old key to new key.

        Args:
            encrypted_data: Encrypted data to check

        Returns:
            True if data is encrypted with old key and needs migration
        """
        # MultiFernet can decrypt with any key in the list
        # To check if migration is needed, try decrypting with just the first (new) key
        try:
            # Create a Fernet with only the first key (new key)
            first_key = self._key.encode() if isinstance(self._key, str) else self._key
            first_cipher = Fernet(first_key)
            first_cipher.decrypt(encrypted_data.encode())
            # If first key can decrypt it, no migration needed
            return False
        except InvalidToken:
            # First key can't decrypt it, check if MultiFernet can (old key)
            try:
                self.cipher.decrypt(encrypted_data.encode())
                # MultiFernet can decrypt it (using old key), so migration is needed
                return True
            except InvalidToken:
                # Cannot be decrypted at all
                return False
            except Exception:
                return False
        except Exception:
            return False

    def migrate_to_new_key(self, encrypted_data: str) -> str:
        """
        Migrate encrypted data from old key to new key using MultiFernet.rotate().

        Args:
            encrypted_data: Data encrypted with old key

        Returns:
            Data re-encrypted with new key

        Raises:
            ValueError: If migration fails
        """
        try:
            # MultiFernet.rotate() automatically decrypts with any key and re-encrypts with the first (new) key
            rotated = self.cipher.rotate(encrypted_data.encode())
            return rotated.decode()
        except Exception as e:
            logger.error(f"Failed to migrate encryption data: {e}")
            raise ValueError(f"Encryption migration failed: {e}") from e
        except Exception as e:
            logger.error(f"Failed to migrate encryption data: {e}")
            raise ValueError(f"Encryption migration failed: {e}") from e

    @staticmethod
    def migrate_data(old_key: str, new_key: str, encrypted_data: str) -> str:
        """
        Re-encrypt data with a new key.

        Args:
            old_key: Old encryption key (base64 encoded)
            new_key: New encryption key (base64 encoded)
            encrypted_data: Data encrypted with old key

        Returns:
            Data encrypted with new key

        Raises:
            ValueError: If decryption with old key or encryption with new key fails
        """
        try:
            # Create ciphers with both keys
            old_cipher = Fernet(old_key.encode() if isinstance(old_key, str) else old_key)
            new_cipher = Fernet(new_key.encode() if isinstance(new_key, str) else new_key)

            # Decrypt with old key
            decrypted = old_cipher.decrypt(encrypted_data.encode())

            # Encrypt with new key
            return new_cipher.encrypt(decrypted).decode()
        except Exception as e:
            logger.error(f"Failed to migrate encryption data: {e}")
            raise ValueError(f"Encryption migration failed: {e}") from e

    def encrypt_password(self, password: str) -> str:
        """
        Encrypt a password.

        Args:
            password: Plain text password

        Returns:
            Encrypted password (base64 encoded)
        """
        try:
            encrypted = self.cipher.encrypt(password.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Failed to encrypt password: {e}")
            raise

    def decrypt_password(self, encrypted_password: str) -> str:
        """
        Decrypt an encrypted password with key rotation support.
        
        MultiFernet automatically tries all keys in the list, so no manual fallback needed.

        Args:
            encrypted_password: Encrypted password (base64 encoded)

        Returns:
            Decrypted plain text password

        Raises:
            ValueError: If decryption fails
        """
        try:
            decrypted = self.cipher.decrypt(encrypted_password.encode())
            return decrypted.decode()
        except InvalidToken:
            logger.error("Failed to decrypt password: invalid token or key")
            raise ValueError("Invalid encryption key or corrupted password")
        except Exception as e:
            logger.error(f"Failed to decrypt password: {e}")
            raise


# Global instance
_encryption_instance: Optional[PasswordEncryption] = None
_encryption_lock = threading.Lock()
_encryption_lock_async: Optional[asyncio.Lock] = None
_async_lock_creation_lock = threading.Lock()  # Protects async lock creation

# TTL cache for os.getenv() optimization
_last_key_check_time: float = 0.0
_KEY_CHECK_INTERVAL: float = 60.0  # Check env key every 60 seconds


def reset_encryption() -> None:
    """
    Reset the global encryption instance.
    Thread-safe implementation.
    """
    global _encryption_instance, _last_key_check_time
    with _encryption_lock:
        _encryption_instance = None
        _last_key_check_time = 0.0  # Reset TTL to force key check on next access
        logger.info("Encryption instance reset")


def get_encryption() -> PasswordEncryption:
    """
    Get global encryption instance (singleton) with double-checked locking and TTL cache.

    Optimized implementation that only acquires lock when instance doesn't exist,
    improving performance under high load. Uses TTL-based caching to minimize
    expensive os.getenv() calls on the hotpath.

    Returns:
        PasswordEncryption instance

    Thread Safety:
        Uses double-checked locking pattern to minimize lock contention.
        First check without lock (fast path), then recheck after acquiring lock.
    """
    global _encryption_instance, _last_key_check_time

    # First check without lock (fast path for existing instance)
    if _encryption_instance is not None:
        current_time = time.monotonic()

        # Only check env key if TTL has expired
        if current_time - _last_key_check_time < _KEY_CHECK_INTERVAL:
            # Fast path: instance exists and TTL not expired - no env check needed
            return _encryption_instance

        # TTL expired - check if key changed
        current_key = os.getenv("ENCRYPTION_KEY")
        if current_key and _normalize_key(current_key) == _encryption_instance._key:
            # Key unchanged - update check time and return
            _last_key_check_time = current_time
            return _encryption_instance
        # Key changed or no cached instance - recreate with new key

    # Acquire lock only if instance doesn't exist or key changed
    with _encryption_lock:
        current_time = time.monotonic()
        current_key = os.getenv("ENCRYPTION_KEY")

        # Double-check after acquiring lock
        if _encryption_instance is None or (
            current_key and _normalize_key(current_key) != _encryption_instance._key
        ):
            _encryption_instance = PasswordEncryption()
            _last_key_check_time = current_time
        else:
            # Instance exists and key matches - update check time
            _last_key_check_time = current_time

        # Ensure _encryption_instance is not None before returning
        if _encryption_instance is None:
            raise RuntimeError("Failed to initialize PasswordEncryption instance")
        return _encryption_instance


def _get_async_lock() -> asyncio.Lock:
    """
    Get or create async lock - must be called within event loop.
    Thread-safe creation using threading.Lock.

    Raises:
        RuntimeError: If called outside of an event loop
    """
    global _encryption_lock_async

    # Verify we're in an event loop
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        raise RuntimeError(
            "Async encryption lock must be accessed within an event loop. "
            "Use get_encryption() for synchronous contexts."
        )

    # Use threading lock to prevent race condition during async lock creation
    with _async_lock_creation_lock:
        if _encryption_lock_async is None:
            _encryption_lock_async = asyncio.Lock()
    return _encryption_lock_async


async def get_encryption_async() -> PasswordEncryption:
    """
    Get global encryption instance (singleton) - async-safe.

    Always uses async lock to prevent race conditions during key changes.
    Recreates instance if encryption key changes.

    Returns:
        PasswordEncryption instance
    """
    global _encryption_instance

    # Get or create async lock within event loop context
    lock = _get_async_lock()

    # Always acquire async lock to prevent race conditions
    async with lock:
        current_key = os.getenv("ENCRYPTION_KEY")
        if _encryption_instance is None or (
            current_key and _normalize_key(current_key) != _encryption_instance._key
        ):
            _encryption_instance = PasswordEncryption()
        return _encryption_instance


def encrypt_password(password: str) -> str:
    """
    Encrypt a password using global instance.

    Args:
        password: Plain text password

    Returns:
        Encrypted password
    """
    return get_encryption().encrypt_password(password)


def decrypt_password(encrypted_password: str) -> str:
    """
    Decrypt a password using global instance.

    Args:
        encrypted_password: Encrypted password

    Returns:
        Decrypted password
    """
    return get_encryption().decrypt_password(encrypted_password)
