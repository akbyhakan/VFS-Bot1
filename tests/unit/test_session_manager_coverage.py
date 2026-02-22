"""Additional coverage tests for utils/security/session_manager module."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.security.session_manager import SessionManager, SessionMetadata


@pytest.fixture
def tmp_session_file(tmp_path):
    """Return a temp path that does not yet exist."""
    return str(tmp_path / "session_test.json")


@pytest.fixture
def manager(tmp_session_file):
    """SessionManager backed by a temp file (no pre-existing session)."""
    with patch.object(Path, "exists", return_value=False):
        sm = SessionManager(session_file=tmp_session_file)
    return sm


# ---------------------------------------------------------------------------
# set_tokens
# ---------------------------------------------------------------------------


class TestSetTokens:
    """Tests for SessionManager.set_tokens()."""

    def test_set_tokens_without_jwt_module(self, manager):
        """When jwt_module is None, token_expiry stays None."""
        with patch("src.utils.security.session_manager.jwt_module", None):
            with patch.object(manager, "save_session"):
                manager.set_tokens("my_token", "my_refresh")

        assert manager.access_token == "my_token"
        assert manager.refresh_token == "my_refresh"
        assert manager.token_expiry is None

    def test_set_tokens_with_jwt_decode_success(self, manager):
        """When jwt_module is available and token has exp, token_expiry is set."""
        future_exp = int(time.time()) + 3600
        mock_jwt = MagicMock()
        mock_jwt.decode.return_value = {"exp": future_exp}

        with patch("src.utils.security.session_manager.jwt_module", mock_jwt):
            with patch.object(manager, "save_session"):
                manager.set_tokens("jwt_token")

        assert manager.token_expiry == future_exp

    def test_set_tokens_jwt_decode_no_exp(self, manager):
        """When decoded token has no exp claim, token_expiry stays None."""
        mock_jwt = MagicMock()
        mock_jwt.decode.return_value = {}

        with patch("src.utils.security.session_manager.jwt_module", mock_jwt):
            with patch.object(manager, "save_session"):
                manager.set_tokens("no_exp_token")

        assert manager.token_expiry is None

    def test_set_tokens_jwt_decode_exception(self, manager):
        """Decode exception is handled gracefully; token_expiry stays None."""
        mock_jwt = MagicMock()
        mock_jwt.decode.side_effect = Exception("bad token")

        with patch("src.utils.security.session_manager.jwt_module", mock_jwt):
            with patch.object(manager, "save_session"):
                manager.set_tokens("bad_token")

        assert manager.token_expiry is None


# ---------------------------------------------------------------------------
# is_token_expired
# ---------------------------------------------------------------------------


class TestIsTokenExpired:
    """Tests for SessionManager.is_token_expired()."""

    def test_no_access_token_returns_true(self, manager):
        """No access token → expired."""
        manager.access_token = None
        assert manager.is_token_expired() is True

    def test_no_expiry_returns_false(self, manager):
        """Token present but no expiry → assume valid."""
        manager.access_token = "token"
        manager.token_expiry = None
        assert manager.is_token_expired() is False

    def test_valid_token_not_expired(self, manager):
        """Token expiring far in the future is not expired."""
        manager.access_token = "token"
        manager.token_expiry = int(time.time()) + 7200
        assert manager.is_token_expired() is False

    def test_expired_token(self, manager):
        """Token past expiry is expired."""
        manager.access_token = "token"
        manager.token_expiry = int(time.time()) - 100
        assert manager.is_token_expired() is True

    def test_token_within_buffer_is_expired(self, manager):
        """Token expiring within refresh_buffer is treated as expired."""
        manager.access_token = "token"
        # token_refresh_buffer defaults to 300 seconds (5 min)
        manager.token_expiry = int(time.time()) + 60  # only 1 min left → expired
        assert manager.is_token_expired() is True


# ---------------------------------------------------------------------------
# refresh_token_if_needed
# ---------------------------------------------------------------------------


class TestRefreshTokenIfNeeded:
    """Tests for SessionManager.refresh_token_if_needed()."""

    @pytest.mark.asyncio
    async def test_valid_token_skips_refresh(self, manager):
        """If token is not expired, refresh callback is not called."""
        manager.access_token = "valid"
        manager.token_expiry = int(time.time()) + 7200

        callback = AsyncMock()
        result = await manager.refresh_token_if_needed(callback)

        assert result is True
        callback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_expired_token_refresh_succeeds(self, manager):
        """Expired token triggers callback; new tokens are set."""
        manager.access_token = "old"
        manager.token_expiry = int(time.time()) - 100
        manager.refresh_token = "old_refresh"

        new_tokens = {"access_token": "new_access", "refresh_token": "new_refresh"}
        callback = AsyncMock(return_value=new_tokens)

        with patch.object(manager, "set_tokens"):
            result = await manager.refresh_token_if_needed(callback)

        assert result is True
        callback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_refresh_callback_returns_none(self, manager):
        """If callback returns None, refresh returns False."""
        manager.access_token = "old"
        manager.token_expiry = int(time.time()) - 100

        callback = AsyncMock(return_value=None)
        result = await manager.refresh_token_if_needed(callback)

        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_callback_raises_exception(self, manager):
        """If callback raises, refresh returns False."""
        manager.access_token = "old"
        manager.token_expiry = int(time.time()) - 100

        callback = AsyncMock(side_effect=Exception("network error"))
        result = await manager.refresh_token_if_needed(callback)

        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_returns_dict_without_access_token(self, manager):
        """If callback returns dict but no access_token key, returns False."""
        manager.access_token = "old"
        manager.token_expiry = int(time.time()) - 100

        callback = AsyncMock(return_value={"refresh_token": "new_refresh"})
        result = await manager.refresh_token_if_needed(callback)

        assert result is False


# ---------------------------------------------------------------------------
# get_auth_header
# ---------------------------------------------------------------------------


class TestGetAuthHeader:
    """Tests for SessionManager.get_auth_header()."""

    def test_with_token_returns_bearer_header(self, manager):
        """get_auth_header returns Authorization header when token present."""
        manager.access_token = "my_token"
        header = manager.get_auth_header()
        assert header == {"Authorization": "Bearer my_token"}

    def test_without_token_returns_empty_dict(self, manager):
        """get_auth_header returns empty dict when no token."""
        manager.access_token = None
        header = manager.get_auth_header()
        assert header == {}


# ---------------------------------------------------------------------------
# clear_session
# ---------------------------------------------------------------------------


class TestClearSession:
    """Tests for SessionManager.clear_session()."""

    def test_clear_session_resets_tokens(self, manager):
        """clear_session nullifies all token attributes."""
        manager.access_token = "tok"
        manager.refresh_token = "ref"
        manager.token_expiry = 12345

        with patch.object(Path, "exists", return_value=False):
            manager.clear_session()

        assert manager.access_token is None
        assert manager.refresh_token is None
        assert manager.token_expiry is None

    def test_clear_session_deletes_file_when_exists(self, tmp_session_file):
        """clear_session deletes the session file if it exists."""
        # Create the file first
        Path(tmp_session_file).touch()

        with patch.object(Path, "exists", return_value=False):
            sm = SessionManager(session_file=tmp_session_file)

        # Actually create the file so clear_session can detect and delete it
        sm.session_file.touch()

        sm.clear_session()

        assert not sm.session_file.exists()

    def test_clear_session_no_file_no_error(self, manager):
        """clear_session does not raise when file doesn't exist."""
        with patch.object(Path, "exists", return_value=False):
            manager.clear_session()  # should not raise


# ---------------------------------------------------------------------------
# _hash_user_agent
# ---------------------------------------------------------------------------


class TestHashUserAgent:
    """Tests for SessionManager._hash_user_agent()."""

    def test_returns_16_char_string(self, manager):
        """Hash is truncated to 16 chars."""
        result = manager._hash_user_agent("Mozilla/5.0 TestBrowser")
        assert isinstance(result, str)
        assert len(result) == 16

    def test_deterministic(self, manager):
        """Same input always produces same hash."""
        ua = "Mozilla/5.0 TestBrowser"
        assert manager._hash_user_agent(ua) == manager._hash_user_agent(ua)

    def test_different_ua_different_hash(self, manager):
        """Different inputs produce different hashes."""
        h1 = manager._hash_user_agent("BrowserA/1.0")
        h2 = manager._hash_user_agent("BrowserB/2.0")
        assert h1 != h2


# ---------------------------------------------------------------------------
# set_session_binding
# ---------------------------------------------------------------------------


class TestSetSessionBinding:
    """Tests for SessionManager.set_session_binding()."""

    def test_disabled_binding_is_no_op(self, tmp_session_file):
        """set_session_binding does nothing when binding is disabled."""
        with patch.object(Path, "exists", return_value=False):
            sm = SessionManager(session_file=tmp_session_file, enable_session_binding=False)

        sm.set_session_binding(ip_address="1.2.3.4", user_agent="TestBrowser")

        assert sm.metadata is None

    def test_enabled_binding_creates_metadata(self, tmp_session_file):
        """set_session_binding creates SessionMetadata when enabled."""
        with patch.object(Path, "exists", return_value=False):
            sm = SessionManager(session_file=tmp_session_file, enable_session_binding=True)

        with patch.object(sm, "save_session"):
            sm.set_session_binding(ip_address="1.2.3.4", user_agent="TestBrowser")

        assert sm.metadata is not None
        assert sm.metadata.ip_address == "1.2.3.4"

    def test_enabled_binding_updates_existing_metadata(self, tmp_session_file):
        """set_session_binding updates existing metadata fields."""
        with patch.object(Path, "exists", return_value=False):
            sm = SessionManager(session_file=tmp_session_file, enable_session_binding=True)

        sm.metadata = SessionMetadata(ip_address="0.0.0.0")

        with patch.object(sm, "save_session"):
            sm.set_session_binding(ip_address="9.9.9.9", user_agent="NewBrowser")

        assert sm.metadata.ip_address == "9.9.9.9"


# ---------------------------------------------------------------------------
# validate_session_binding
# ---------------------------------------------------------------------------


class TestValidateSessionBinding:
    """Tests for SessionManager.validate_session_binding()."""

    def test_disabled_always_returns_true(self, tmp_session_file):
        """validate_session_binding returns True when binding disabled."""
        with patch.object(Path, "exists", return_value=False):
            sm = SessionManager(session_file=tmp_session_file, enable_session_binding=False)

        assert sm.validate_session_binding(ip_address="any", user_agent="any") is True

    def test_no_metadata_returns_true(self, tmp_session_file):
        """validate_session_binding returns True when no metadata exists."""
        with patch.object(Path, "exists", return_value=False):
            sm = SessionManager(session_file=tmp_session_file, enable_session_binding=True)

        sm.metadata = None
        assert sm.validate_session_binding(ip_address="1.2.3.4") is True

    def test_ip_mismatch_returns_false(self, tmp_session_file):
        """Mismatched IP returns False."""
        with patch.object(Path, "exists", return_value=False):
            sm = SessionManager(session_file=tmp_session_file, enable_session_binding=True)

        sm.metadata = SessionMetadata(ip_address="1.1.1.1")

        assert sm.validate_session_binding(ip_address="2.2.2.2") is False

    def test_ua_mismatch_returns_false(self, tmp_session_file):
        """Mismatched User-Agent returns False."""
        with patch.object(Path, "exists", return_value=False):
            sm = SessionManager(session_file=tmp_session_file, enable_session_binding=True)

        sm.metadata = SessionMetadata(user_agent_hash=sm._hash_user_agent("OldBrowser"))

        assert sm.validate_session_binding(user_agent="NewBrowser") is False

    def test_valid_binding_returns_true(self, tmp_session_file):
        """Matching IP and UA returns True."""
        with patch.object(Path, "exists", return_value=False):
            sm = SessionManager(session_file=tmp_session_file, enable_session_binding=True)

        ua = "TestBrowser/1.0"
        ip = "10.0.0.1"
        sm.metadata = SessionMetadata(
            ip_address=ip, user_agent_hash=sm._hash_user_agent(ua), last_validated=0
        )

        with patch.object(sm, "save_session"):
            result = sm.validate_session_binding(ip_address=ip, user_agent=ua)

        assert result is True


# ---------------------------------------------------------------------------
# has_valid_session
# ---------------------------------------------------------------------------


class TestHasValidSession:
    """Tests for SessionManager.has_valid_session()."""

    def test_no_token_returns_false(self, manager):
        """No token → no valid session."""
        manager.access_token = None
        assert manager.has_valid_session() is False

    def test_valid_token_returns_true(self, manager):
        """Non-expired token → valid session."""
        manager.access_token = "tok"
        manager.token_expiry = int(time.time()) + 3600
        assert manager.has_valid_session() is True


# ---------------------------------------------------------------------------
# sync_from_api_client
# ---------------------------------------------------------------------------


class TestSyncFromApiClient:
    """Tests for SessionManager.sync_from_api_client()."""

    def test_none_session_is_no_op(self, manager):
        """None vfs_session does nothing and does not raise."""
        manager.sync_from_api_client(None)
        assert manager.access_token is None

    def test_session_without_access_token_attr_raises(self, manager):
        """vfs_session missing access_token raises AttributeError."""
        with pytest.raises(AttributeError):
            manager.sync_from_api_client(object())

    def test_valid_session_sets_tokens(self, manager):
        """access_token is synced from vfs_session."""
        vfs_session = MagicMock()
        vfs_session.access_token = "synced_token"
        vfs_session.refresh_token = "synced_refresh"

        with patch.object(manager, "set_tokens") as mock_set:
            manager.sync_from_api_client(vfs_session)

        mock_set.assert_called_once_with("synced_token", "synced_refresh")

    def test_empty_access_token_is_no_op(self, manager):
        """Empty access_token logs a warning and does not call set_tokens."""
        vfs_session = MagicMock()
        vfs_session.access_token = ""

        with patch.object(manager, "set_tokens") as mock_set:
            manager.sync_from_api_client(vfs_session)

        mock_set.assert_not_called()
