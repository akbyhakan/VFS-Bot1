"""Unit tests for WebSocketChannel notification."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.notification.channels.websocket import WebSocketChannel


class TestWebSocketChannelName:
    """Tests for WebSocketChannel.name property."""

    def test_name_returns_websocket(self):
        """Test that name property returns 'websocket'."""
        channel = WebSocketChannel()
        assert channel.name == "websocket"


class TestWebSocketChannelEnabled:
    """Tests for WebSocketChannel.enabled property."""

    def test_enabled_false_without_manager(self):
        """Test that channel is disabled when no manager is set."""
        channel = WebSocketChannel()
        assert channel.enabled is False

    def test_enabled_true_with_manager(self):
        """Test that channel is enabled when manager is set."""
        mock_manager = MagicMock()
        channel = WebSocketChannel(websocket_manager=mock_manager)
        assert channel.enabled is True

    def test_enabled_false_after_none_manager(self):
        """Test that channel is disabled when manager explicitly set to None."""
        channel = WebSocketChannel(websocket_manager=None)
        assert channel.enabled is False


class TestWebSocketChannelSetManager:
    """Tests for WebSocketChannel.set_manager method."""

    def test_set_manager_enables_channel(self):
        """Test that set_manager enables the channel."""
        channel = WebSocketChannel()
        assert channel.enabled is False

        mock_manager = MagicMock()
        channel.set_manager(mock_manager)
        assert channel.enabled is True

    def test_set_manager_replaces_existing(self):
        """Test that set_manager replaces an existing manager."""
        first_manager = MagicMock()
        second_manager = MagicMock()

        channel = WebSocketChannel(websocket_manager=first_manager)
        channel.set_manager(second_manager)

        assert channel._manager is second_manager

    def test_set_manager_to_none_disables_channel(self):
        """Test that setting manager to None disables the channel."""
        mock_manager = MagicMock()
        channel = WebSocketChannel(websocket_manager=mock_manager)
        assert channel.enabled is True

        channel.set_manager(None)
        assert channel.enabled is False


class TestWebSocketChannelSend:
    """Tests for WebSocketChannel.send method."""

    @pytest.mark.asyncio
    async def test_send_returns_false_without_manager(self):
        """Test that send returns False when no manager is set."""
        channel = WebSocketChannel()
        result = await channel.send("Test Title", "Test Message")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_broadcasts_with_manager(self):
        """Test that send broadcasts message when manager is available."""
        mock_manager = AsyncMock()
        mock_manager.broadcast = AsyncMock()

        channel = WebSocketChannel(websocket_manager=mock_manager)
        result = await channel.send("Alert", "Slot available")

        assert result is True
        mock_manager.broadcast.assert_called_once()

        # Verify the broadcast payload structure
        call_args = mock_manager.broadcast.call_args[0][0]
        assert call_args["type"] == "critical_notification"
        assert call_args["data"]["title"] == "Alert"
        assert call_args["data"]["message"] == "Slot available"
        assert call_args["data"]["priority"] == "high"

    @pytest.mark.asyncio
    async def test_send_returns_false_on_broadcast_exception(self):
        """Test that send returns False when broadcast raises an exception."""
        mock_manager = MagicMock()
        mock_manager.broadcast = AsyncMock(side_effect=RuntimeError("Connection lost"))

        channel = WebSocketChannel(websocket_manager=mock_manager)
        result = await channel.send("Title", "Message")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_returns_false_when_manager_has_no_broadcast(self):
        """Test that send returns False when manager lacks broadcast method."""
        mock_manager = MagicMock(spec=[])  # no attributes

        channel = WebSocketChannel(websocket_manager=mock_manager)
        result = await channel.send("Title", "Message")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_logs_debug_when_no_manager(self):
        """Test that send logs debug message when manager not available."""
        channel = WebSocketChannel()

        with patch("src.services.notification.channels.websocket.logger") as mock_logger:
            result = await channel.send("Title", "Message")

        assert result is False
        mock_logger.debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_notification_has_timestamp(self):
        """Test that the broadcast payload contains a timestamp."""
        mock_manager = AsyncMock()
        mock_manager.broadcast = AsyncMock()

        channel = WebSocketChannel(websocket_manager=mock_manager)
        await channel.send("Title", "Message")

        call_args = mock_manager.broadcast.call_args[0][0]
        assert "timestamp" in call_args["data"]
