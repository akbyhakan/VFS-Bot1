"""Tests for session manager."""

import pytest
from pathlib import Path
import sys
import tempfile
import shutil
import json
import time
from unittest.mock import patch, AsyncMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.security.session_manager import SessionManager


class TestSessionManager:
    """Test session manager functionality."""

    @pytest.fixture
    def temp_session_file(self):
        """Create temporary session file."""
        temp_dir = Path(tempfile.mkdtemp())
        session_file = temp_dir / "session.json"
        yield session_file
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

    def test_init_default(self, temp_session_file):
        """Test SessionManager initialization with defaults."""
        sm = SessionManager(session_file=str(temp_session_file))

        assert sm.session_file == temp_session_file
        assert sm.token_refresh_buffer == 5 * 60  # 5 minutes in seconds
        assert sm.access_token is None
        assert sm.refresh_token is None
        assert sm.token_expiry is None

    def test_init_custom_buffer(self, temp_session_file):
        """Test SessionManager with custom refresh buffer."""
        sm = SessionManager(session_file=str(temp_session_file), token_refresh_buffer=10)

        assert sm.token_refresh_buffer == 10 * 60  # 10 minutes in seconds

    def test_load_session_no_file(self, temp_session_file):
        """Test load_session when file doesn't exist."""
        sm = SessionManager(session_file=str(temp_session_file))

        result = sm.load_session()

        assert result is False
        assert sm.access_token is None

    def test_load_session_success(self, temp_session_file):
        """Test load_session with valid session file."""
        session_data = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_expiry": int(time.time()) + 3600,
        }
        temp_session_file.parent.mkdir(parents=True, exist_ok=True)
        temp_session_file.write_text(json.dumps(session_data))

        sm = SessionManager(session_file=str(temp_session_file))

        assert sm.access_token == "test_access_token"
        assert sm.refresh_token == "test_refresh_token"
        assert sm.token_expiry is not None

    def test_load_session_exception(self, temp_session_file):
        """Test load_session handles exceptions."""
        temp_session_file.parent.mkdir(parents=True, exist_ok=True)
        temp_session_file.write_text("invalid json")

        sm = SessionManager(session_file=str(temp_session_file))

        assert sm.access_token is None

    def test_save_session(self, temp_session_file):
        """Test save_session."""
        sm = SessionManager(session_file=str(temp_session_file))
        sm.access_token = "test_access"
        sm.refresh_token = "test_refresh"
        sm.token_expiry = 1234567890

        result = sm.save_session()

        assert result is True
        assert temp_session_file.exists()

        # Verify contents
        data = json.loads(temp_session_file.read_text())
        assert data["access_token"] == "test_access"
        assert data["refresh_token"] == "test_refresh"
        assert data["token_expiry"] == 1234567890

    def test_save_session_creates_directory(self, temp_session_file):
        """Test save_session creates directory if needed."""
        sm = SessionManager(session_file=str(temp_session_file))
        sm.access_token = "test_access"

        result = sm.save_session()

        assert result is True
        assert temp_session_file.parent.exists()

    def test_save_session_exception(self):
        """Test save_session handles exceptions."""
        sm = SessionManager(session_file="/invalid/path/session.json")
        sm.access_token = "test_access"

        result = sm.save_session()

        assert result is False

    def test_set_tokens_basic(self, temp_session_file):
        """Test set_tokens without JWT decoding."""
        with patch("src.utils.security.session_manager.jwt_module", None):
            sm = SessionManager(session_file=str(temp_session_file))
            sm.set_tokens("test_access", "test_refresh")

            assert sm.access_token == "test_access"
            assert sm.refresh_token == "test_refresh"
            assert sm.token_expiry is None

    def test_set_tokens_with_jwt(self, temp_session_file):
        """Test set_tokens with JWT decoding."""
        mock_jwt = type("MockJWT", (), {})()
        mock_jwt.decode = lambda token, **kwargs: {"exp": 1234567890}

        with patch("src.utils.security.session_manager.jwt_module", mock_jwt):
            sm = SessionManager(session_file=str(temp_session_file))
            sm.set_tokens("test_access")

            assert sm.access_token == "test_access"
            assert sm.token_expiry == 1234567890

    def test_set_tokens_jwt_no_exp(self, temp_session_file):
        """Test set_tokens when JWT has no exp claim."""
        mock_jwt = type("MockJWT", (), {})()
        mock_jwt.decode = lambda token, **kwargs: {}

        with patch("src.utils.security.session_manager.jwt_module", mock_jwt):
            sm = SessionManager(session_file=str(temp_session_file))
            sm.set_tokens("test_access")

            assert sm.token_expiry is None

    def test_set_tokens_jwt_exception(self, temp_session_file):
        """Test set_tokens handles JWT decode exceptions."""
        mock_jwt = type("MockJWT", (), {})()
        mock_jwt.decode = lambda token, **kwargs: (_ for _ in ()).throw(Exception("Decode error"))

        with patch("src.utils.security.session_manager.jwt_module", mock_jwt):
            sm = SessionManager(session_file=str(temp_session_file))
            sm.set_tokens("test_access")

            assert sm.access_token == "test_access"
            assert sm.token_expiry is None

    def test_is_token_expired_no_token(self, temp_session_file):
        """Test is_token_expired with no token."""
        sm = SessionManager(session_file=str(temp_session_file))

        assert sm.is_token_expired() is True

    def test_is_token_expired_no_expiry(self, temp_session_file):
        """Test is_token_expired with no expiry time."""
        sm = SessionManager(session_file=str(temp_session_file))
        sm.access_token = "test_token"
        sm.token_expiry = None

        assert sm.is_token_expired() is False

    def test_is_token_expired_valid(self, temp_session_file):
        """Test is_token_expired with valid token."""
        sm = SessionManager(session_file=str(temp_session_file))
        sm.access_token = "test_token"
        sm.token_expiry = int(time.time()) + 3600  # Expires in 1 hour

        assert sm.is_token_expired() is False

    def test_is_token_expired_expiring_soon(self, temp_session_file):
        """Test is_token_expired when token expiring within buffer."""
        sm = SessionManager(session_file=str(temp_session_file), token_refresh_buffer=10)
        sm.access_token = "test_token"
        sm.token_expiry = int(time.time()) + 300  # Expires in 5 minutes

        # Buffer is 10 minutes, so should be considered expired
        assert sm.is_token_expired() is True

    def test_is_token_expired_already_expired(self, temp_session_file):
        """Test is_token_expired with expired token."""
        sm = SessionManager(session_file=str(temp_session_file))
        sm.access_token = "test_token"
        sm.token_expiry = int(time.time()) - 3600  # Expired 1 hour ago

        assert sm.is_token_expired() is True

    @pytest.mark.asyncio
    async def test_refresh_token_if_needed_valid(self, temp_session_file):
        """Test refresh_token_if_needed with valid token."""
        sm = SessionManager(session_file=str(temp_session_file))
        sm.access_token = "test_token"
        sm.token_expiry = int(time.time()) + 3600

        callback = AsyncMock()

        result = await sm.refresh_token_if_needed(callback)

        assert result is True
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_token_if_needed_expired(self, temp_session_file):
        """Test refresh_token_if_needed with expired token."""
        sm = SessionManager(session_file=str(temp_session_file))
        sm.access_token = "old_token"
        sm.refresh_token = "refresh_token"
        sm.token_expiry = int(time.time()) - 3600  # Expired

        callback = AsyncMock(return_value={"access_token": "new_token"})

        result = await sm.refresh_token_if_needed(callback)

        assert result is True
        assert sm.access_token == "new_token"
        callback.assert_awaited_once_with("refresh_token")

    @pytest.mark.asyncio
    async def test_refresh_token_if_needed_with_new_refresh_token(self, temp_session_file):
        """Test refresh_token_if_needed updates refresh token."""
        sm = SessionManager(session_file=str(temp_session_file))
        sm.access_token = "old_token"
        sm.token_expiry = int(time.time()) - 3600

        callback = AsyncMock(
            return_value={"access_token": "new_access", "refresh_token": "new_refresh"}
        )

        result = await sm.refresh_token_if_needed(callback)

        assert result is True
        assert sm.access_token == "new_access"
        assert sm.refresh_token == "new_refresh"

    @pytest.mark.asyncio
    async def test_refresh_token_if_needed_failed(self, temp_session_file):
        """Test refresh_token_if_needed when refresh fails."""
        sm = SessionManager(session_file=str(temp_session_file))
        sm.access_token = "old_token"
        sm.token_expiry = int(time.time()) - 3600

        callback = AsyncMock(return_value=None)

        result = await sm.refresh_token_if_needed(callback)

        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_token_if_needed_exception(self, temp_session_file):
        """Test refresh_token_if_needed handles exceptions."""
        sm = SessionManager(session_file=str(temp_session_file))
        sm.access_token = "old_token"
        sm.token_expiry = int(time.time()) - 3600

        callback = AsyncMock(side_effect=Exception("Refresh error"))

        result = await sm.refresh_token_if_needed(callback)

        assert result is False

    def test_get_auth_header_with_token(self, temp_session_file):
        """Test get_auth_header with token."""
        sm = SessionManager(session_file=str(temp_session_file))
        sm.access_token = "test_token"

        header = sm.get_auth_header()

        assert header == {"Authorization": "Bearer test_token"}

    def test_get_auth_header_no_token(self, temp_session_file):
        """Test get_auth_header without token."""
        sm = SessionManager(session_file=str(temp_session_file))

        header = sm.get_auth_header()

        assert header == {}

    def test_clear_session(self, temp_session_file):
        """Test clear_session."""
        # Create session file
        temp_session_file.parent.mkdir(parents=True, exist_ok=True)
        temp_session_file.write_text('{"access_token": "test"}')

        sm = SessionManager(session_file=str(temp_session_file))
        sm.access_token = "test_token"
        sm.refresh_token = "refresh_token"
        sm.token_expiry = 1234567890

        sm.clear_session()

        assert sm.access_token is None
        assert sm.refresh_token is None
        assert sm.token_expiry is None
        assert not temp_session_file.exists()

    def test_clear_session_no_file(self, temp_session_file):
        """Test clear_session when file doesn't exist."""
        sm = SessionManager(session_file=str(temp_session_file))
        sm.access_token = "test_token"

        # Should not raise exception
        sm.clear_session()

        assert sm.access_token is None

    def test_has_valid_session_true(self, temp_session_file):
        """Test has_valid_session with valid session."""
        sm = SessionManager(session_file=str(temp_session_file))
        sm.access_token = "test_token"
        sm.token_expiry = int(time.time()) + 3600

        assert sm.has_valid_session() is True

    def test_has_valid_session_false_no_token(self, temp_session_file):
        """Test has_valid_session with no token."""
        sm = SessionManager(session_file=str(temp_session_file))

        assert sm.has_valid_session() is False

    def test_has_valid_session_false_expired(self, temp_session_file):
        """Test has_valid_session with expired token."""
        sm = SessionManager(session_file=str(temp_session_file))
        sm.access_token = "test_token"
        sm.token_expiry = int(time.time()) - 3600

        assert sm.has_valid_session() is False
