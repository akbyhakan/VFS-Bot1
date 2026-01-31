"""Extended tests for session manager."""

import pytest
import pytest_asyncio
from pathlib import Path
import sys
import json
import time
import os
from unittest.mock import AsyncMock, mock_open, patch, MagicMock
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.security.session_manager import SessionManager


@pytest.fixture
def temp_session_file():
    """Create a temporary session file."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


def test_session_manager_initialization():
    """Test session manager initialization."""
    manager = SessionManager(session_file="data/test_session.json", token_refresh_buffer=10)

    assert manager.session_file == Path("data/test_session.json")
    assert manager.token_refresh_buffer == 600  # 10 minutes * 60 seconds
    assert manager.access_token is None
    assert manager.refresh_token is None
    assert manager.token_expiry is None


def test_session_manager_default_values():
    """Test session manager default values."""
    manager = SessionManager()

    assert manager.session_file == Path("data/session.json")
    assert manager.token_refresh_buffer == 300  # 5 minutes * 60 seconds


def test_load_session_file_not_exists():
    """Test loading session when file doesn't exist."""
    with patch.object(Path, "exists", return_value=False):
        manager = SessionManager("nonexistent.json")
        result = manager.load_session()

        assert result is False


def test_load_session_success(temp_session_file):
    """Test successful session loading."""
    session_data = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "token_expiry": int(time.time()) + 3600,
    }

    # Save encrypted session data
    from src.utils.encryption import encrypt_password

    json_data = json.dumps(session_data)
    encrypted_data = encrypt_password(json_data)

    with open(temp_session_file, "w") as f:
        f.write(encrypted_data)

    manager = SessionManager(session_file=temp_session_file)

    assert manager.access_token == "test_access_token"
    assert manager.refresh_token == "test_refresh_token"
    assert manager.token_expiry == session_data["token_expiry"]


def test_load_session_error_handling():
    """Test session loading error handling."""
    with patch("builtins.open", side_effect=Exception("Read error")):
        with patch.object(Path, "exists", return_value=True):
            manager = SessionManager("test.json")
            result = manager.load_session()

            assert result is False


def test_save_session_success(temp_session_file):
    """Test successful session saving."""
    manager = SessionManager(session_file=temp_session_file)
    manager.access_token = "test_access"
    manager.refresh_token = "test_refresh"
    manager.token_expiry = 1234567890

    result = manager.save_session()
    assert result is True

    # Verify file contents - now encrypted
    from src.utils.encryption import decrypt_password

    with open(temp_session_file, "r") as f:
        encrypted_content = f.read()

    # Decrypt and parse
    decrypted_data = decrypt_password(encrypted_content)
    data = json.loads(decrypted_data)

    assert data["access_token"] == "test_access"
    assert data["refresh_token"] == "test_refresh"
    assert data["token_expiry"] == 1234567890


def test_save_session_creates_directory():
    """Test that save_session creates parent directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "new_dir" / "session.json"
        manager = SessionManager(session_file=str(session_file))
        manager.access_token = "test"

        result = manager.save_session()
        assert result is True
        assert session_file.parent.exists()


def test_save_session_error_handling():
    """Test session saving error handling."""
    with patch("tempfile.mkstemp", side_effect=Exception("Write error")):
        manager = SessionManager("test.json")
        manager.access_token = "test"

        result = manager.save_session()
        assert result is False


def test_set_tokens_without_jwt():
    """Test setting tokens without pyjwt installed."""
    with patch("src.utils.security.session_manager.jwt_module", None):
        manager = SessionManager("test.json")
        with patch.object(manager, "save_session"):
            manager.set_tokens("test_access_token", "test_refresh_token")

            assert manager.access_token == "test_access_token"
            assert manager.refresh_token == "test_refresh_token"
            assert manager.token_expiry is None


def test_set_tokens_with_jwt():
    """Test setting tokens with JWT decoding."""
    mock_jwt = MagicMock()
    expiry_time = int(time.time()) + 3600
    mock_jwt.decode.return_value = {"exp": expiry_time}

    with patch("src.utils.security.session_manager.jwt_module", mock_jwt):
        manager = SessionManager("test.json")
        with patch.object(manager, "save_session"):
            manager.set_tokens("test_token")

            assert manager.access_token == "test_token"
            assert manager.token_expiry == expiry_time


def test_set_tokens_jwt_decode_error():
    """Test setting tokens when JWT decode fails."""
    mock_jwt = MagicMock()
    mock_jwt.decode.side_effect = Exception("Decode error")

    with patch("src.utils.security.session_manager.jwt_module", mock_jwt):
        manager = SessionManager("test.json")
        with patch.object(manager, "save_session"):
            manager.set_tokens("invalid_token")

            assert manager.access_token == "invalid_token"
            assert manager.token_expiry is None


def test_set_tokens_no_exp_claim():
    """Test setting tokens when JWT has no exp claim."""
    mock_jwt = MagicMock()
    mock_jwt.decode.return_value = {}  # No 'exp' claim

    with patch("src.utils.security.session_manager.jwt_module", mock_jwt):
        manager = SessionManager("test.json")
        with patch.object(manager, "save_session"):
            manager.set_tokens("test_token")

            assert manager.token_expiry is None


def test_is_token_expired_no_token():
    """Test is_token_expired with no token."""
    manager = SessionManager("test.json")
    assert manager.is_token_expired() is True


def test_is_token_expired_no_expiry():
    """Test is_token_expired with no expiry set."""
    manager = SessionManager("test.json")
    manager.access_token = "test_token"
    manager.token_expiry = None

    assert manager.is_token_expired() is False


def test_is_token_expired_valid_token():
    """Test is_token_expired with valid token."""
    manager = SessionManager("test.json", token_refresh_buffer=5)
    manager.access_token = "test_token"
    manager.token_expiry = int(time.time()) + 600  # 10 minutes from now

    assert manager.is_token_expired() is False


def test_is_token_expired_expiring_soon():
    """Test is_token_expired when token expires within buffer."""
    manager = SessionManager("test.json", token_refresh_buffer=5)
    manager.access_token = "test_token"
    # Token expires in 4 minutes (less than 5 minute buffer)
    manager.token_expiry = int(time.time()) + 240

    assert manager.is_token_expired() is True


def test_is_token_expired_already_expired():
    """Test is_token_expired with already expired token."""
    manager = SessionManager("test.json")
    manager.access_token = "test_token"
    manager.token_expiry = int(time.time()) - 100  # Expired 100 seconds ago

    assert manager.is_token_expired() is True


@pytest.mark.asyncio
async def test_refresh_token_if_needed_not_needed():
    """Test refresh_token_if_needed when token is still valid."""
    manager = SessionManager("test.json")
    manager.access_token = "test_token"
    manager.token_expiry = int(time.time()) + 3600

    refresh_callback = AsyncMock()
    result = await manager.refresh_token_if_needed(refresh_callback)

    assert result is True
    refresh_callback.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_token_if_needed_success():
    """Test successful token refresh."""
    manager = SessionManager("test.json")
    manager.access_token = "old_token"
    manager.refresh_token = "old_refresh"
    manager.token_expiry = int(time.time()) - 100  # Expired

    refresh_callback = AsyncMock(
        return_value={"access_token": "new_token", "refresh_token": "new_refresh"}
    )

    with patch.object(manager, "set_tokens"):
        result = await manager.refresh_token_if_needed(refresh_callback)

        assert result is True
        refresh_callback.assert_called_once_with("old_refresh")


@pytest.mark.asyncio
async def test_refresh_token_if_needed_failure():
    """Test token refresh failure."""
    manager = SessionManager("test.json")
    manager.access_token = "old_token"
    manager.token_expiry = int(time.time()) - 100  # Expired

    refresh_callback = AsyncMock(return_value=None)
    result = await manager.refresh_token_if_needed(refresh_callback)

    assert result is False


@pytest.mark.asyncio
async def test_refresh_token_if_needed_exception():
    """Test token refresh with exception."""
    manager = SessionManager("test.json")
    manager.access_token = "old_token"
    manager.token_expiry = int(time.time()) - 100  # Expired

    refresh_callback = AsyncMock(side_effect=Exception("Refresh failed"))
    result = await manager.refresh_token_if_needed(refresh_callback)

    assert result is False


@pytest.mark.asyncio
async def test_refresh_token_keeps_old_refresh_token():
    """Test that refresh keeps old refresh token if not provided."""
    manager = SessionManager("test.json")
    manager.access_token = "old_token"
    manager.refresh_token = "old_refresh"
    manager.token_expiry = int(time.time()) - 100  # Expired

    # New response doesn't include refresh_token
    refresh_callback = AsyncMock(return_value={"access_token": "new_token"})

    with patch.object(manager, "set_tokens") as mock_set:
        await manager.refresh_token_if_needed(refresh_callback)
        mock_set.assert_called_once_with("new_token", "old_refresh")


def test_get_auth_header_with_token():
    """Test get_auth_header with token."""
    manager = SessionManager("test.json")
    manager.access_token = "test_token"

    header = manager.get_auth_header()
    assert header == {"Authorization": "Bearer test_token"}


def test_get_auth_header_without_token():
    """Test get_auth_header without token."""
    manager = SessionManager("test.json")

    header = manager.get_auth_header()
    assert header == {}


def test_clear_session(temp_session_file):
    """Test clearing session."""
    # Create session file
    with open(temp_session_file, "w") as f:
        json.dump({"access_token": "test"}, f)

    manager = SessionManager(session_file=temp_session_file)
    manager.access_token = "test_token"
    manager.refresh_token = "test_refresh"
    manager.token_expiry = 123456

    manager.clear_session()

    assert manager.access_token is None
    assert manager.refresh_token is None
    assert manager.token_expiry is None
    assert not Path(temp_session_file).exists()


def test_clear_session_file_not_exists():
    """Test clearing session when file doesn't exist."""
    manager = SessionManager("nonexistent.json")
    manager.access_token = "test"

    # Should not raise exception
    manager.clear_session()
    assert manager.access_token is None


def test_has_valid_session_valid():
    """Test has_valid_session with valid session."""
    manager = SessionManager("test.json")
    manager.access_token = "test_token"
    manager.token_expiry = int(time.time()) + 3600

    assert manager.has_valid_session() is True


def test_has_valid_session_no_token():
    """Test has_valid_session without token."""
    manager = SessionManager("test.json")

    assert manager.has_valid_session() is False


def test_has_valid_session_expired():
    """Test has_valid_session with expired token."""
    manager = SessionManager("test.json")
    manager.access_token = "test_token"
    manager.token_expiry = int(time.time()) - 100

    assert manager.has_valid_session() is False


def test_token_refresh_buffer_conversion():
    """Test that token_refresh_buffer is converted to seconds."""
    manager = SessionManager("test.json", token_refresh_buffer=10)
    assert manager.token_refresh_buffer == 600  # 10 * 60


def test_session_file_permissions(tmp_path):
    """Test that session file has correct permissions (Unix only)."""
    import platform

    # Skip on Windows
    if platform.system() == "Windows":
        pytest.skip("File permissions test not applicable on Windows")

    import stat

    session_file = tmp_path / "session.json"
    manager = SessionManager(session_file=str(session_file))
    manager.set_tokens("test_token")

    # Check file permissions (should be 0600 - owner read/write only)
    mode = os.stat(session_file).st_mode
    # Check that group and other have no permissions
    assert mode & stat.S_IRWXG == 0  # No group permissions
    assert mode & stat.S_IRWXO == 0  # No other permissions
    # Check that owner has read and write
    assert mode & stat.S_IRUSR != 0  # Owner can read
    assert mode & stat.S_IWUSR != 0  # Owner can write
