"""Extended tests for session manager functionality."""

import base64
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.security.session_manager import SessionManager


class TestSessionManagerExtended:
    """Extended tests for session manager functionality."""

    def setup_method(self):
        """Setup test session file."""
        fd, self.test_session_file = tempfile.mkstemp(suffix=".json")
        import os

        os.close(fd)

    def teardown_method(self):
        """Clean up test session file."""
        session_path = Path(self.test_session_file)
        if session_path.exists():
            session_path.unlink()

    def test_init_with_custom_buffer(self):
        """Test SessionManager initialization with custom refresh buffer."""
        manager = SessionManager(session_file=self.test_session_file, token_refresh_buffer=10)

        # Buffer should be converted to seconds (10 minutes = 600 seconds)
        assert manager.token_refresh_buffer == 600

    def test_load_session_no_file(self):
        """Test load_session when file doesn't exist."""
        # Delete file if it exists
        Path(self.test_session_file).unlink(missing_ok=True)

        manager = SessionManager(session_file=self.test_session_file)

        # Should handle missing file gracefully
        assert manager.access_token is None
        assert manager.refresh_token is None

    def test_load_session_invalid_json(self):
        """Test load_session with invalid JSON."""
        # Write invalid JSON
        with open(self.test_session_file, "w") as f:
            f.write("invalid json {")

        manager = SessionManager(session_file=self.test_session_file)

        # Should handle error and return None tokens
        assert manager.access_token is None

    def test_save_session_creates_directory(self):
        """Test save_session creates parent directory if needed."""
        # Use a path with non-existent directory
        import tempfile

        temp_dir = Path(tempfile.gettempdir()) / "test_session_dir"
        session_file = temp_dir / "session.json"

        try:
            manager = SessionManager(session_file=str(session_file))
            manager.set_tokens("test_token", "test_refresh")

            # Directory should be created
            assert temp_dir.exists()
            assert session_file.exists()
        finally:
            # Cleanup
            if session_file.exists():
                session_file.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()

    def test_set_tokens_with_jwt(self):
        """Test set_tokens with valid JWT token."""
        # Create a mock JWT token (not cryptographically valid, just for testing)
        # JWT format: header.payload.signature
        header = base64.b64encode(b'{"alg":"HS256","typ":"JWT"}').decode()
        # Set expiry to 1 hour from now
        expiry = int(time.time()) + 3600
        payload = base64.b64encode(f'{{"exp":{expiry},"user":"test"}}'.encode()).decode()
        signature = base64.b64encode(b"fake_signature").decode()

        mock_token = f"{header}.{payload}.{signature}"

        with patch("src.utils.security.session_manager.jwt_module") as mock_jwt:
            mock_jwt.decode.return_value = {"exp": expiry, "user": "test"}

            manager = SessionManager(session_file=self.test_session_file)
            manager.set_tokens(mock_token, "refresh_token")

            assert manager.access_token == mock_token
            assert manager.refresh_token == "refresh_token"
            assert manager.token_expiry == expiry

    def test_set_tokens_without_pyjwt(self):
        """Test set_tokens when pyjwt is not installed."""
        with patch("src.utils.security.session_manager.jwt_module", None):
            manager = SessionManager(session_file=self.test_session_file)
            manager.set_tokens("test_token", "refresh_token")

            assert manager.access_token == "test_token"
            assert manager.refresh_token == "refresh_token"
            assert manager.token_expiry is None

    def test_set_tokens_jwt_decode_error(self):
        """Test set_tokens handles JWT decode errors."""
        with patch("src.utils.security.session_manager.jwt_module") as mock_jwt:
            mock_jwt.decode.side_effect = Exception("Invalid token")

            manager = SessionManager(session_file=self.test_session_file)
            manager.set_tokens("invalid_token", "refresh_token")

            assert manager.access_token == "invalid_token"
            assert manager.token_expiry is None

    def test_set_tokens_jwt_without_exp(self):
        """Test set_tokens with JWT that doesn't have exp claim."""
        with patch("src.utils.security.session_manager.jwt_module") as mock_jwt:
            mock_jwt.decode.return_value = {"user": "test"}  # No exp claim

            manager = SessionManager(session_file=self.test_session_file)
            manager.set_tokens("token_without_exp", "refresh_token")

            assert manager.access_token == "token_without_exp"
            assert manager.token_expiry is None

    def test_is_token_expired_no_token(self):
        """Test is_token_expired when no token is set."""
        manager = SessionManager(session_file=self.test_session_file)

        assert manager.is_token_expired() is True

    def test_is_token_expired_no_expiry(self):
        """Test is_token_expired when expiry is not known."""
        manager = SessionManager(session_file=self.test_session_file)
        manager.access_token = "test_token"
        manager.token_expiry = None

        # Should return False (assume valid if we can't determine)
        assert manager.is_token_expired() is False

    def test_is_token_expired_within_buffer(self):
        """Test is_token_expired when token expires within buffer time."""
        manager = SessionManager(session_file=self.test_session_file, token_refresh_buffer=5)
        manager.access_token = "test_token"

        # Set expiry to 4 minutes from now (buffer is 5 minutes)
        manager.token_expiry = int(time.time()) + 240

        # Should be considered expired (within buffer)
        assert manager.is_token_expired() is True

    def test_is_token_expired_outside_buffer(self):
        """Test is_token_expired when token is valid for longer than buffer."""
        manager = SessionManager(session_file=self.test_session_file, token_refresh_buffer=5)
        manager.access_token = "test_token"

        # Set expiry to 10 minutes from now (buffer is 5 minutes)
        manager.token_expiry = int(time.time()) + 600

        # Should not be considered expired
        assert manager.is_token_expired() is False

    def test_is_token_expired_already_expired(self):
        """Test is_token_expired when token is already expired."""
        manager = SessionManager(session_file=self.test_session_file)
        manager.access_token = "test_token"

        # Set expiry to past
        manager.token_expiry = int(time.time()) - 3600

        assert manager.is_token_expired() is True

    @pytest.mark.asyncio
    async def test_refresh_token_if_needed_not_expired(self):
        """Test refresh_token_if_needed when token is still valid."""
        manager = SessionManager(session_file=self.test_session_file)
        manager.access_token = "test_token"
        manager.token_expiry = int(time.time()) + 3600  # 1 hour from now

        refresh_callback = AsyncMock()

        result = await manager.refresh_token_if_needed(refresh_callback)

        assert result is True
        refresh_callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_token_if_needed_success(self):
        """Test successful token refresh."""
        manager = SessionManager(session_file=self.test_session_file)
        manager.access_token = "old_token"
        manager.refresh_token = "old_refresh"
        manager.token_expiry = int(time.time()) - 100  # Expired

        # Mock refresh callback
        new_expiry = int(time.time()) + 3600

        with patch("src.utils.security.session_manager.jwt_module") as mock_jwt:
            mock_jwt.decode.return_value = {"exp": new_expiry}

            refresh_callback = AsyncMock(
                return_value={
                    "access_token": "new_token",
                    "refresh_token": "new_refresh",
                }
            )

            result = await manager.refresh_token_if_needed(refresh_callback)

            assert result is True
            assert manager.access_token == "new_token"
            assert manager.refresh_token == "new_refresh"
            refresh_callback.assert_called_once_with("old_refresh")

    @pytest.mark.asyncio
    async def test_refresh_token_if_needed_no_new_access_token(self):
        """Test token refresh when callback doesn't return access_token."""
        manager = SessionManager(session_file=self.test_session_file)
        manager.access_token = "old_token"
        manager.token_expiry = int(time.time()) - 100  # Expired

        refresh_callback = AsyncMock(return_value={"refresh_token": "new_refresh"})

        result = await manager.refresh_token_if_needed(refresh_callback)

        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_token_if_needed_callback_error(self):
        """Test token refresh when callback raises error."""
        manager = SessionManager(session_file=self.test_session_file)
        manager.access_token = "old_token"
        manager.token_expiry = int(time.time()) - 100  # Expired

        refresh_callback = AsyncMock(side_effect=Exception("Refresh failed"))

        result = await manager.refresh_token_if_needed(refresh_callback)

        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_token_if_needed_keeps_old_refresh_token(self):
        """Test that old refresh token is kept if new one not provided."""
        manager = SessionManager(session_file=self.test_session_file)
        manager.access_token = "old_token"
        manager.refresh_token = "old_refresh"
        manager.token_expiry = int(time.time()) - 100  # Expired

        new_expiry = int(time.time()) + 3600

        with patch("src.utils.security.session_manager.jwt_module") as mock_jwt:
            mock_jwt.decode.return_value = {"exp": new_expiry}

            refresh_callback = AsyncMock(
                return_value={"access_token": "new_token"}  # No refresh_token
            )

            result = await manager.refresh_token_if_needed(refresh_callback)

            assert result is True
            assert manager.refresh_token == "old_refresh"  # Should keep old one

    def test_get_auth_header_with_token(self):
        """Test get_auth_header when token is set."""
        manager = SessionManager(session_file=self.test_session_file)
        manager.access_token = "test_token_123"

        header = manager.get_auth_header()

        assert header == {"Authorization": "Bearer test_token_123"}

    def test_get_auth_header_without_token(self):
        """Test get_auth_header when token is not set."""
        manager = SessionManager(session_file=self.test_session_file)
        manager.access_token = None

        header = manager.get_auth_header()

        assert header == {}

    def test_clear_session(self):
        """Test session clearing."""
        manager = SessionManager(session_file=self.test_session_file)
        manager.set_tokens("test_token", "test_refresh")

        # Verify file exists
        assert Path(self.test_session_file).exists()

        manager.clear_session()

        assert manager.access_token is None
        assert manager.refresh_token is None
        assert manager.token_expiry is None
        # File should be deleted
        assert not Path(self.test_session_file).exists()

    def test_clear_session_no_file(self):
        """Test clearing session when file doesn't exist."""
        Path(self.test_session_file).unlink(missing_ok=True)

        manager = SessionManager(session_file=self.test_session_file)
        manager.access_token = "test_token"

        # Should not raise error
        manager.clear_session()

        assert manager.access_token is None

    def test_has_valid_session_true(self):
        """Test has_valid_session when session is valid."""
        manager = SessionManager(session_file=self.test_session_file)
        manager.access_token = "test_token"
        manager.token_expiry = int(time.time()) + 3600

        assert manager.has_valid_session() is True

    def test_has_valid_session_false_no_token(self):
        """Test has_valid_session when no token is set."""
        manager = SessionManager(session_file=self.test_session_file)

        assert manager.has_valid_session() is False

    def test_has_valid_session_false_expired(self):
        """Test has_valid_session when token is expired."""
        manager = SessionManager(session_file=self.test_session_file)
        manager.access_token = "test_token"
        manager.token_expiry = int(time.time()) - 100

        assert manager.has_valid_session() is False

    def test_save_and_load_roundtrip(self):
        """Test that save and load work correctly together."""
        manager1 = SessionManager(session_file=self.test_session_file)
        manager1.access_token = "test_access"
        manager1.refresh_token = "test_refresh"
        manager1.token_expiry = 1234567890

        manager1.save_session()

        # Load in new manager
        manager2 = SessionManager(session_file=self.test_session_file)

        assert manager2.access_token == "test_access"
        assert manager2.refresh_token == "test_refresh"
        assert manager2.token_expiry == 1234567890


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
