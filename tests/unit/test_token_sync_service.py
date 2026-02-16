"""Tests for TokenSyncService."""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.account.token_sync_service import TokenSyncService


@pytest.fixture
def mock_session_manager():
    """Create a mock SessionManager."""
    manager = MagicMock()
    manager.set_tokens = MagicMock()
    return manager


@pytest.fixture
def mock_vfs_session():
    """Create a mock VFSSession."""
    session = MagicMock()
    session.access_token = "test_access_token"
    session.refresh_token = "test_refresh_token"
    session.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    return session


@pytest.fixture
def mock_vfs_api_client(mock_vfs_session):
    """Create a mock VFSApiClient."""
    client = MagicMock()
    client.session = mock_vfs_session
    client._refresh_token = AsyncMock()
    return client


class TestTokenSyncService:
    """Test TokenSyncService functionality."""

    def test_initialization_with_session_manager(self, mock_session_manager):
        """Test initialization with SessionManager enabled."""
        service = TokenSyncService(
            session_manager=mock_session_manager, token_refresh_buffer_minutes=10
        )

        assert service.session_manager is mock_session_manager
        assert service.token_refresh_buffer_minutes == 10

    def test_initialization_without_session_manager(self):
        """Test initialization with SessionManager disabled (anti-detection off)."""
        service = TokenSyncService(session_manager=None)

        assert service.session_manager is None
        # Should use default from environment or fallback
        assert service.token_refresh_buffer_minutes >= 0

    def test_initialization_with_env_var(self):
        """Test initialization reads TOKEN_REFRESH_BUFFER_MINUTES from environment."""
        with patch.dict(os.environ, {"TOKEN_REFRESH_BUFFER_MINUTES": "15"}):
            service = TokenSyncService()
            assert service.token_refresh_buffer_minutes == 15

    def test_sync_from_vfs_session_success(self, mock_session_manager, mock_vfs_session):
        """Test successful token sync from VFSSession to SessionManager."""
        service = TokenSyncService(session_manager=mock_session_manager)
        service.sync_from_vfs_session(mock_vfs_session)

        # Verify set_tokens was called with correct arguments
        mock_session_manager.set_tokens.assert_called_once_with(
            "test_access_token", "test_refresh_token"
        )

    def test_sync_from_vfs_session_when_disabled(self, mock_vfs_session):
        """Test sync does nothing when SessionManager is None."""
        service = TokenSyncService(session_manager=None)
        service.sync_from_vfs_session(mock_vfs_session)

        # Should not raise any errors, just skip silently

    def test_sync_from_vfs_session_with_none_session(self, mock_session_manager):
        """Test sync handles None VFSSession gracefully."""
        service = TokenSyncService(session_manager=mock_session_manager)
        service.sync_from_vfs_session(None)

        # set_tokens should not be called
        mock_session_manager.set_tokens.assert_not_called()

    def test_sync_from_vfs_session_with_none_access_token(self, mock_session_manager):
        """Test sync handles None access_token gracefully."""
        service = TokenSyncService(session_manager=mock_session_manager)

        vfs_session = MagicMock()
        vfs_session.access_token = None
        vfs_session.refresh_token = "test_refresh_token"

        service.sync_from_vfs_session(vfs_session)

        # set_tokens should not be called when access_token is None
        mock_session_manager.set_tokens.assert_not_called()

    def test_sync_from_vfs_session_handles_exception(self, mock_session_manager):
        """Test sync handles exceptions during set_tokens."""
        mock_session_manager.set_tokens.side_effect = Exception("Set tokens failed")

        service = TokenSyncService(session_manager=mock_session_manager)

        vfs_session = MagicMock()
        vfs_session.access_token = "test_token"
        vfs_session.refresh_token = "test_refresh"

        # Should not raise exception, just log error
        service.sync_from_vfs_session(vfs_session)

    def test_should_proactive_refresh_when_within_buffer(self):
        """Test should_proactive_refresh returns True when within buffer period."""
        service = TokenSyncService(token_refresh_buffer_minutes=5)

        # Token expires in 3 minutes (less than 5 minute buffer)
        vfs_session = MagicMock()
        vfs_session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=3)

        assert service.should_proactive_refresh(vfs_session) is True

    def test_should_proactive_refresh_when_outside_buffer(self):
        """Test should_proactive_refresh returns False when outside buffer period."""
        service = TokenSyncService(token_refresh_buffer_minutes=5)

        # Token expires in 10 minutes (more than 5 minute buffer)
        vfs_session = MagicMock()
        vfs_session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        assert service.should_proactive_refresh(vfs_session) is False

    def test_should_proactive_refresh_when_expired(self):
        """Test should_proactive_refresh returns True when token already expired."""
        service = TokenSyncService(token_refresh_buffer_minutes=5)

        # Token expired 1 minute ago
        vfs_session = MagicMock()
        vfs_session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)

        assert service.should_proactive_refresh(vfs_session) is True

    def test_should_proactive_refresh_with_none_session(self):
        """Test should_proactive_refresh handles None session gracefully."""
        service = TokenSyncService(token_refresh_buffer_minutes=5)

        assert service.should_proactive_refresh(None) is False

    def test_should_proactive_refresh_with_naive_datetime(self):
        """Test should_proactive_refresh handles naive datetime (no timezone)."""
        service = TokenSyncService(token_refresh_buffer_minutes=5)

        # Create naive datetime (no timezone info)
        vfs_session = MagicMock()
        vfs_session.expires_at = datetime.now() + timedelta(minutes=3)

        # Should handle gracefully by adding timezone
        result = service.should_proactive_refresh(vfs_session)
        assert isinstance(result, bool)

    def test_should_proactive_refresh_handles_exception(self):
        """Test should_proactive_refresh returns False on exception."""
        service = TokenSyncService(token_refresh_buffer_minutes=5)

        vfs_session = MagicMock()
        # Simulate exception when accessing expires_at
        vfs_session.expires_at = property(lambda self: 1 / 0)

        # Should return False on error
        assert service.should_proactive_refresh(vfs_session) is False

    @pytest.mark.asyncio
    async def test_ensure_fresh_token_no_refresh_needed(self, mock_vfs_api_client):
        """Test ensure_fresh_token when token is still fresh."""
        service = TokenSyncService(token_refresh_buffer_minutes=5)

        # Token expires in 10 minutes (outside buffer)
        mock_vfs_api_client.session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        result = await service.ensure_fresh_token(mock_vfs_api_client)

        assert result is True
        # _refresh_token should not be called
        mock_vfs_api_client._refresh_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_fresh_token_refresh_needed_success(
        self, mock_vfs_api_client, mock_session_manager
    ):
        """Test ensure_fresh_token when refresh is needed and succeeds."""
        service = TokenSyncService(
            session_manager=mock_session_manager, token_refresh_buffer_minutes=5
        )

        # Token expires in 3 minutes (within buffer)
        mock_vfs_api_client.session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=3)

        result = await service.ensure_fresh_token(mock_vfs_api_client)

        assert result is True
        # _refresh_token should be called
        mock_vfs_api_client._refresh_token.assert_called_once()
        # Token should be synced to SessionManager
        mock_session_manager.set_tokens.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_fresh_token_refresh_needed_failure(
        self, mock_vfs_api_client, mock_session_manager
    ):
        """Test ensure_fresh_token when refresh is needed but fails."""
        service = TokenSyncService(
            session_manager=mock_session_manager, token_refresh_buffer_minutes=5
        )

        # Token expires in 3 minutes (within buffer)
        mock_vfs_api_client.session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=3)

        # Make refresh fail
        mock_vfs_api_client._refresh_token.side_effect = Exception("Refresh failed")

        result = await service.ensure_fresh_token(mock_vfs_api_client)

        assert result is False
        # _refresh_token should be attempted
        mock_vfs_api_client._refresh_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_fresh_token_with_none_client(self):
        """Test ensure_fresh_token handles None client gracefully."""
        service = TokenSyncService(token_refresh_buffer_minutes=5)

        result = await service.ensure_fresh_token(None)

        assert result is False

    @pytest.mark.asyncio
    async def test_ensure_fresh_token_client_without_session(self):
        """Test ensure_fresh_token handles client without session attribute."""
        service = TokenSyncService(token_refresh_buffer_minutes=5)

        client = MagicMock(spec=[])  # No session attribute

        result = await service.ensure_fresh_token(client)

        assert result is False

    @pytest.mark.asyncio
    async def test_ensure_fresh_token_client_without_refresh_method(self):
        """Test ensure_fresh_token handles client without _refresh_token method."""
        service = TokenSyncService(token_refresh_buffer_minutes=5)

        client = MagicMock()
        client.session = MagicMock()
        client.session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=3)
        # Remove _refresh_token method
        del client._refresh_token

        result = await service.ensure_fresh_token(client)

        assert result is False

    @pytest.mark.asyncio
    async def test_ensure_fresh_token_syncs_after_refresh(
        self, mock_vfs_api_client, mock_session_manager
    ):
        """Test that ensure_fresh_token syncs token after successful refresh."""
        service = TokenSyncService(
            session_manager=mock_session_manager, token_refresh_buffer_minutes=5
        )

        # Token expires in 2 minutes (within buffer)
        original_expires = datetime.now(timezone.utc) + timedelta(minutes=2)
        mock_vfs_api_client.session.expires_at = original_expires

        # After refresh, update the expires_at to simulate successful refresh
        async def refresh_side_effect():
            mock_vfs_api_client.session.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            mock_vfs_api_client.session.access_token = "new_access_token"
            mock_vfs_api_client.session.refresh_token = "new_refresh_token"

        mock_vfs_api_client._refresh_token.side_effect = refresh_side_effect

        result = await service.ensure_fresh_token(mock_vfs_api_client)

        assert result is True
        # Verify refresh was called
        mock_vfs_api_client._refresh_token.assert_called_once()
        # Verify sync was called with new tokens
        mock_session_manager.set_tokens.assert_called_once_with(
            "new_access_token", "new_refresh_token"
        )


class TestTokenSyncServiceIntegration:
    """Integration tests for TokenSyncService with real-like scenarios."""

    @pytest.mark.asyncio
    async def test_full_workflow_with_proactive_refresh(self, mock_session_manager):
        """Test complete workflow: check -> refresh -> sync."""
        service = TokenSyncService(
            session_manager=mock_session_manager, token_refresh_buffer_minutes=5
        )

        # Create a VFS API client mock
        client = MagicMock()
        client.session = MagicMock()
        client.session.access_token = "old_token"
        client.session.refresh_token = "old_refresh"
        client.session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=3)

        # Mock refresh to update tokens
        async def refresh():
            client.session.access_token = "new_token"
            client.session.refresh_token = "new_refresh"
            client.session.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        client._refresh_token = AsyncMock(side_effect=refresh)

        # Execute workflow
        result = await service.ensure_fresh_token(client)

        assert result is True
        # Verify SessionManager was updated with new tokens
        mock_session_manager.set_tokens.assert_called_once_with("new_token", "new_refresh")

    def test_multiple_sync_calls_idempotent(self, mock_session_manager, mock_vfs_session):
        """Test that multiple sync calls with same session are idempotent."""
        service = TokenSyncService(session_manager=mock_session_manager)

        # Call sync multiple times
        service.sync_from_vfs_session(mock_vfs_session)
        service.sync_from_vfs_session(mock_vfs_session)
        service.sync_from_vfs_session(mock_vfs_session)

        # set_tokens should be called 3 times with same arguments
        assert mock_session_manager.set_tokens.call_count == 3
        # All calls should have same arguments
        for call in mock_session_manager.set_tokens.call_args_list:
            assert call[0] == ("test_access_token", "test_refresh_token")
