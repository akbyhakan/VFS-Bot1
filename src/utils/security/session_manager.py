"""Manage JWT tokens with automatic refresh before expiry."""

import json
import logging
import os
import stat
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, Optional

try:
    import jwt as jwt_module
except ImportError:
    jwt_module = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class SessionManager:
    """Manage JWT session tokens with auto-refresh."""

    def __init__(self, session_file: str = "data/session.json", token_refresh_buffer: int = 5):
        """
        Initialize session manager.

        Args:
            session_file: Path to session file
            token_refresh_buffer: Minutes before expiry to refresh token
        """
        self.session_file = Path(session_file)
        self.token_refresh_buffer = token_refresh_buffer * 60  # Convert to seconds

        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expiry: Optional[int] = None

        if jwt_module is None:
            logger.warning("pyjwt not installed, JWT decoding will be disabled")

        # Load existing session if available
        self.load_session()

    def load_session(self) -> bool:
        """
        Load session from file.

        Returns:
            True if session loaded successfully
        """
        try:
            if not self.session_file.exists():
                logger.info("No existing session file found")
                return False

            with open(self.session_file, "r") as f:
                data = json.load(f)

            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            self.token_expiry = data.get("token_expiry")

            logger.info("Session loaded from file")
            return True

        except Exception as e:
            logger.error(f"Error loading session: {e}")
            return False

    def save_session(self) -> bool:
        """
        Save session to file.

        Returns:
            True if session saved successfully
        """
        try:
            # Create data directory if it doesn't exist
            self.session_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "token_expiry": self.token_expiry,
            }

            # Atomic write with secure permissions from start
            fd, temp_path = tempfile.mkstemp(
                dir=self.session_file.parent, text=True, prefix=".session_"
            )
            try:
                # Set secure permissions (0600) before writing data
                os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
                with os.fdopen(fd, "w") as f:
                    json.dump(data, f, indent=2)
                # Atomically replace the old file
                os.rename(temp_path, self.session_file)
                logger.info("Session saved securely to file")
                return True
            except Exception as e:
                # Close fd if it's still open (fdopen takes ownership normally)
                try:
                    os.close(fd)
                except OSError:
                    pass  # fd was already closed by fdopen
                logger.error(f"Failed to save session: {e}")
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                return False

        except Exception as e:
            logger.error(f"Error saving session: {e}")
            return False

    def set_tokens(self, access_token: str, refresh_token: Optional[str] = None) -> None:
        """
        Set tokens and decode JWT to extract expiry time.

        Args:
            access_token: JWT access token
            refresh_token: Optional JWT refresh token
        """
        self.access_token = access_token
        self.refresh_token = refresh_token

        # Decode token to get expiry
        if jwt_module is not None:
            try:
                # Decode without verification to extract claims
                # Note: Signature verification is disabled because we're only
                # reading the expiry time, not validating the token's authenticity.
                # The token is already trusted as it comes from the service we're automating.
                decoded = jwt_module.decode(access_token, options={"verify_signature": False})
                self.token_expiry = decoded.get("exp")

                if self.token_expiry:
                    logger.info(f"Token expiry set to: {time.ctime(self.token_expiry)}")
                else:
                    logger.warning("Token does not contain 'exp' claim")
            except Exception as e:
                logger.error(f"Error decoding token: {e}")
                self.token_expiry = None
        else:
            logger.warning("Cannot decode token, pyjwt not installed")
            self.token_expiry = None

        # Save to file
        self.save_session()

    def is_token_expired(self) -> bool:
        """
        Check if token is expired with 5-minute buffer.

        Returns:
            True if token is expired or will expire soon
        """
        if not self.access_token:
            return True

        if not self.token_expiry:
            # If we can't determine expiry, assume it's valid
            return False

        current_time = int(time.time())
        # Check if token will expire within buffer time
        return current_time >= (self.token_expiry - self.token_refresh_buffer)

    async def refresh_token_if_needed(self, refresh_callback: Callable) -> bool:
        """
        Auto-refresh token if needed using callback.

        Args:
            refresh_callback: Async function to call for token refresh

        Returns:
            True if token is valid (refreshed if needed)
        """
        if not self.is_token_expired():
            logger.debug("Token is still valid")
            return True

        logger.info("Token expired or expiring soon, refreshing...")

        try:
            # Call refresh callback
            new_tokens = await refresh_callback(self.refresh_token)

            if new_tokens:
                access_token = new_tokens.get("access_token")
                refresh_token = new_tokens.get("refresh_token", self.refresh_token)

                if access_token:
                    self.set_tokens(access_token, refresh_token)
                    logger.info("Token refreshed successfully")
                    return True

            logger.error("Token refresh failed")
            return False

        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return False

    def get_auth_header(self) -> Dict[str, str]:
        """
        Return Bearer token header.

        Returns:
            Dictionary with Authorization header
        """
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    def clear_session(self) -> None:
        """Reset all session data."""
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None

        # Delete session file if it exists
        try:
            if self.session_file.exists():
                self.session_file.unlink()
                logger.info("Session file deleted")
        except Exception as e:
            logger.error(f"Error deleting session file: {e}")

        logger.info("Session cleared")

    def has_valid_session(self) -> bool:
        """
        Check if there's a valid session.

        Returns:
            True if session is valid
        """
        return self.access_token is not None and not self.is_token_expired()
