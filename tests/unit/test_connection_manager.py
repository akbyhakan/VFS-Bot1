"""Unit tests for WebSocket ConnectionManager."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from web.websocket.manager import ConnectionManager


def make_mock_websocket():
    """Create a mock WebSocket object."""
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


class TestConnectionManagerConnect:
    """Tests for ConnectionManager.connect method."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        result = await manager.connect(ws)
        assert result is True
        assert ws in manager._connections

    @pytest.mark.asyncio
    async def test_connect_initializes_rate_limit(self):
        """Test that connect initializes rate limit bucket."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        await manager.connect(ws)
        assert ws in manager._rate_limits
        assert "tokens" in manager._rate_limits[ws]

    @pytest.mark.asyncio
    async def test_connect_enforces_max_connections(self):
        """Test that connection is rejected when limit is reached."""
        manager = ConnectionManager()
        manager.MAX_CONNECTIONS = 2

        ws1 = make_mock_websocket()
        ws2 = make_mock_websocket()
        ws3 = make_mock_websocket()

        assert await manager.connect(ws1) is True
        assert await manager.connect(ws2) is True
        assert await manager.connect(ws3) is False
        assert ws3 not in manager._connections

    @pytest.mark.asyncio
    async def test_connect_multiple_connections(self):
        """Test multiple connections are tracked."""
        manager = ConnectionManager()

        ws_list = [make_mock_websocket() for _ in range(5)]
        for ws in ws_list:
            result = await manager.connect(ws)
            assert result is True

        assert len(manager._connections) == 5


class TestConnectionManagerDisconnect:
    """Tests for ConnectionManager.disconnect method."""

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self):
        """Test disconnect removes the connection."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        await manager.connect(ws)
        assert ws in manager._connections

        await manager.disconnect(ws)
        assert ws not in manager._connections

    @pytest.mark.asyncio
    async def test_disconnect_cleans_rate_limit(self):
        """Test disconnect removes rate limit data."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        await manager.connect(ws)
        await manager.disconnect(ws)

        assert ws not in manager._rate_limits

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_connection(self):
        """Test disconnect of nonexistent connection doesn't raise."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        # Should not raise
        await manager.disconnect(ws)


class TestConnectionManagerSendMessage:
    """Tests for ConnectionManager.send_message method."""

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """Test successful message send."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        await manager.connect(ws)
        result = await manager.send_message(ws, {"type": "test", "data": {}})

        assert result is True
        ws.send_json.assert_called_once_with({"type": "test", "data": {}})

    @pytest.mark.asyncio
    async def test_send_message_rate_limited(self):
        """Test message rejected when rate limited."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        await manager.connect(ws)

        # Exhaust all tokens
        manager._rate_limits[ws]["tokens"] = 0

        result = await manager.send_message(ws, {"type": "test"})
        assert result is False
        ws.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_message_handles_exception(self):
        """Test send_message returns False on exception."""
        manager = ConnectionManager()
        ws = make_mock_websocket()
        ws.send_json = AsyncMock(side_effect=RuntimeError("Connection error"))

        await manager.connect(ws)
        result = await manager.send_message(ws, {"type": "test"})
        assert result is False


class TestConnectionManagerBroadcast:
    """Tests for ConnectionManager.broadcast method."""

    @pytest.mark.asyncio
    async def test_broadcast_to_all_connections(self):
        """Test broadcast sends to all connected clients."""
        manager = ConnectionManager()
        ws1 = make_mock_websocket()
        ws2 = make_mock_websocket()

        await manager.connect(ws1)
        await manager.connect(ws2)

        await manager.broadcast({"type": "update", "data": {}})

        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_cleans_disconnected(self):
        """Test broadcast removes disconnected clients."""
        manager = ConnectionManager()
        ws1 = make_mock_websocket()
        ws2 = make_mock_websocket()
        ws2.send_json = AsyncMock(side_effect=RuntimeError("Disconnected"))

        await manager.connect(ws1)
        await manager.connect(ws2)

        await manager.broadcast({"type": "update"})

        # ws2 should be removed
        assert ws2 not in manager._connections
        assert ws1 in manager._connections

    @pytest.mark.asyncio
    async def test_broadcast_empty_connections(self):
        """Test broadcast with no connections doesn't raise."""
        manager = ConnectionManager()
        # Should not raise
        await manager.broadcast({"type": "test"})


class TestConnectionManagerRateLimit:
    """Tests for _check_rate_limit token bucket algorithm."""

    def test_rate_limit_initializes_bucket(self):
        """Test that rate limit bucket is created on first check."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        result = manager._check_rate_limit(ws)
        assert result is True
        assert ws in manager._rate_limits

    def test_rate_limit_allows_burst(self):
        """Test that burst messages are allowed up to BURST_SIZE."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        # Should allow BURST_SIZE messages immediately
        allowed = sum(1 for _ in range(manager.BURST_SIZE) if manager._check_rate_limit(ws))
        assert allowed == manager.BURST_SIZE

    def test_rate_limit_rejects_after_burst(self):
        """Test that messages are rejected after burst is exhausted."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        # Exhaust all tokens
        for _ in range(manager.BURST_SIZE):
            manager._check_rate_limit(ws)

        # Next message should be rejected
        result = manager._check_rate_limit(ws)
        assert result is False

    def test_rate_limit_refills_over_time(self):
        """Test that tokens are refilled over time."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        # Exhaust tokens
        for _ in range(manager.BURST_SIZE):
            manager._check_rate_limit(ws)

        # Simulate time passing by manipulating the bucket
        manager._rate_limits[ws]["last_update"] -= 1.0  # 1 second ago

        # Should now allow one more message
        result = manager._check_rate_limit(ws)
        assert result is True
