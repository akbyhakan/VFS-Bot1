"""Tests for notification service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.notification.notification import (
    NotificationConfig,
    NotificationService,
    TelegramConfig,
)


def test_notification_service_initialization():
    """Test notification service initialization."""
    config = {
        "telegram": {"enabled": True, "bot_token": "test", "chat_id": "123"},
    }

    notifier = NotificationService(config)
    assert notifier.telegram_enabled is True


def test_telegram_config_repr_masks_bot_token():
    """Test that TelegramConfig.__repr__ masks bot_token."""
    config = TelegramConfig(enabled=True, bot_token="secret_bot_token_123", chat_id="123456")
    repr_str = repr(config)
    assert "secret_bot_token_123" not in repr_str
    assert "***" in repr_str
    assert "123456" in repr_str


def test_notification_config_repr_masks_nested_secrets():
    """Test that NotificationConfig.__repr__ masks nested secrets."""
    config = NotificationConfig(
        telegram=TelegramConfig(enabled=True, bot_token="secret_token", chat_id="123"),
    )
    repr_str = repr(config)
    assert "secret_token" not in repr_str
    assert "***" in repr_str


def test_notification_service_disabled():
    """Test notification service with all channels disabled."""
    config = {"telegram": {"enabled": False}}

    notifier = NotificationService(config)
    assert notifier.telegram_enabled is False


def test_notification_service_empty_config():
    """Test notification service with empty config."""
    config = {}
    notifier = NotificationService(config)
    assert notifier.telegram_enabled is False


@pytest.mark.asyncio
async def test_notification_with_no_channels():
    """Test sending notification with no channels enabled."""
    config = {"telegram": {"enabled": False}}

    notifier = NotificationService(config)
    # Should not raise an exception
    await notifier.send_notification("Test", "Test message")


@pytest.mark.asyncio
async def test_send_telegram_success():
    """Test successful Telegram notification."""
    config = {"telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"}}

    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot
        mock_bot.send_message = AsyncMock()

        # Create notifier after patching Bot
        notifier = NotificationService(config)

        result = await notifier.send_telegram("Test Title", "Test Message")

        assert result is True
        mock_bot.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_telegram_missing_credentials():
    """Test Telegram notification with missing credentials."""
    config = {"telegram": {"enabled": True, "bot_token": None, "chat_id": None}}

    notifier = NotificationService(config)
    result = await notifier.send_telegram("Test", "Message")
    assert result is False


@pytest.mark.asyncio
async def test_send_telegram_exception():
    """Test Telegram notification exception handling with retry."""
    config = {"telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"}}

    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot
        mock_bot.send_message = AsyncMock(side_effect=Exception("Telegram error"))

        # Create notifier after patching Bot
        notifier = NotificationService(config)

        result = await notifier.send_telegram("Test", "Message")
        assert result is False

        # Verify retry happened (1 initial + 2 retries = 3 total attempts)
        assert mock_bot.send_message.call_count == 3


@pytest.mark.asyncio
async def test_send_telegram_retry_then_success():
    """Test Telegram notification succeeds after retry."""
    config = {"telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"}}

    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot

        # First call fails, second call succeeds
        mock_bot.send_message = AsyncMock(
            side_effect=[Exception("Transient error"), None]  # Success
        )

        # Create notifier after patching Bot
        notifier = NotificationService(config)

        result = await notifier.send_telegram("Test", "Message")
        assert result is True

        # Verify retry happened (2 calls: 1 failure + 1 success)
        assert mock_bot.send_message.call_count == 2


@pytest.mark.asyncio
async def test_notify_slot_found():
    """Test slot found notification."""
    config = {"telegram": {"enabled": False}}
    notifier = NotificationService(config)

    # Should not raise exception
    await notifier.notify_slot_found("Istanbul", "2024-01-15", "10:00")


@pytest.mark.asyncio
async def test_notify_booking_success():
    """Test booking success notification."""
    config = {"telegram": {"enabled": False}}
    notifier = NotificationService(config)

    # Should not raise exception
    await notifier.notify_booking_success("Istanbul", "2024-01-15", "10:00", "REF123")


@pytest.mark.asyncio
async def test_notify_error():
    """Test error notification."""
    config = {"telegram": {"enabled": False}}
    notifier = NotificationService(config)

    # Should not raise exception
    await notifier.notify_error("ConnectionError", "Failed to connect to VFS website")


@pytest.mark.asyncio
async def test_notify_bot_started():
    """Test bot started notification."""
    config = {"telegram": {"enabled": False}}
    notifier = NotificationService(config)

    # Should not raise exception
    await notifier.notify_bot_started()


@pytest.mark.asyncio
async def test_notify_bot_stopped():
    """Test bot stopped notification."""
    config = {"telegram": {"enabled": False}}
    notifier = NotificationService(config)

    # Should not raise exception
    await notifier.notify_bot_stopped()


@pytest.mark.asyncio
async def test_send_notification_with_telegram_enabled():
    """Test send_notification with Telegram enabled."""
    config = {
        "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"},
    }

    notifier = NotificationService(config)

    with patch.object(notifier, "send_telegram", new_callable=AsyncMock) as mock_telegram:
        mock_telegram.return_value = True
        await notifier.send_notification("Test", "Message")
        mock_telegram.assert_called_once_with("Test", "Message")


@pytest.mark.asyncio
async def test_send_notification_priority():
    """Test send_notification with priority parameter."""
    config = {"telegram": {"enabled": False}}
    notifier = NotificationService(config)

    # Should not raise exception with different priority levels
    result_low = await notifier.send_notification("Test", "Message", priority="low")
    result_normal = await notifier.send_notification("Test", "Message", priority="normal")
    result_high = await notifier.send_notification("Test", "Message", priority="high")

    # All should return False since no channels are enabled
    assert result_low is False
    assert result_normal is False
    assert result_high is False


@pytest.mark.asyncio
async def test_send_notification_returns_bool():
    """Test send_notification returns bool indicating success."""
    config = {
        "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"},
        "email": {"enabled": False},
    }

    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot
        mock_bot.send_message = AsyncMock()

        notifier = NotificationService(config)

        # Should return True when Telegram succeeds
        result = await notifier.send_notification("Test", "Message")
        assert result is True


@pytest.mark.asyncio
async def test_send_notification_all_channels_fail():
    """Test send_notification returns False when all channels fail."""
    config = {
        "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"},
    }

    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot
        mock_bot.send_message = AsyncMock(side_effect=Exception("Telegram error"))

        notifier = NotificationService(config)

        # Should return False when all channels fail
        result = await notifier.send_notification("Test", "Message")
        assert result is False


@pytest.mark.asyncio
async def test_send_notification_high_priority_websocket_fallback():
    """Test high-priority notification with WebSocket as parallel channel when Telegram fails."""
    config = {
        "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"},
        "email": {"enabled": False},
    }

    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot
        # Make all attempts fail
        mock_bot.send_message = AsyncMock(side_effect=Exception("Telegram error"))

        notifier = NotificationService(config)

        # Mock WebSocket manager
        mock_ws_manager = AsyncMock()
        mock_ws_manager.broadcast = AsyncMock()
        notifier.set_websocket_manager(mock_ws_manager)

        # Send high-priority notification
        result = await notifier.send_notification("Test", "Critical Alert", priority="high")

        # WebSocket should have been called as a parallel channel (not fallback)
        mock_ws_manager.broadcast.assert_called_once()

        # Should return True if WebSocket succeeded
        assert result is True


@pytest.mark.asyncio
async def test_send_notification_high_priority_no_websocket():
    """Test high-priority notification without WebSocket manager."""
    config = {
        "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"}
    }

    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot
        mock_bot.send_message = AsyncMock(side_effect=Exception("Telegram error"))

        notifier = NotificationService(config)

        # Send high-priority notification without WebSocket manager
        result = await notifier.send_notification("Test", "Critical Alert", priority="high")

        # Should return False when all channels fail and no WebSocket
        assert result is False

        # Failed high-priority count should increment
        stats = notifier.get_notification_stats()
        assert stats["failed_high_priority_notifications"] == 1


@pytest.mark.asyncio
async def test_send_notification_websocket_parallel_channel():
    """Test that WebSocket receives notifications for all priority levels."""
    config = {"telegram": {"enabled": False}}

    notifier = NotificationService(config)

    # Mock WebSocket manager
    mock_ws_manager = AsyncMock()
    mock_ws_manager.broadcast = AsyncMock()
    notifier.set_websocket_manager(mock_ws_manager)

    # Test low priority
    result_low = await notifier.send_notification("Test", "Low Priority", priority="low")
    assert result_low is True
    assert mock_ws_manager.broadcast.call_count == 1

    # Test normal priority
    result_normal = await notifier.send_notification("Test", "Normal Priority", priority="normal")
    assert result_normal is True
    assert mock_ws_manager.broadcast.call_count == 2

    # Test high priority
    result_high = await notifier.send_notification("Test", "High Priority", priority="high")
    assert result_high is True
    assert mock_ws_manager.broadcast.call_count == 3


@pytest.mark.asyncio
async def test_send_notification_websocket_and_telegram_both_called():
    """Test that both WebSocket and Telegram are called in parallel."""
    config = {
        "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"}
    }

    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot
        mock_bot.send_message = AsyncMock()

        notifier = NotificationService(config)

        # Mock WebSocket manager
        mock_ws_manager = AsyncMock()
        mock_ws_manager.broadcast = AsyncMock()
        notifier.set_websocket_manager(mock_ws_manager)

        # Send notification
        result = await notifier.send_notification("Test", "Message", priority="normal")

        # Both channels should be called
        assert result is True
        mock_bot.send_message.assert_called_once()
        mock_ws_manager.broadcast.assert_called_once()


@pytest.mark.asyncio
async def test_send_notification_websocket_success_telegram_fail():
    """Test that notification succeeds if WebSocket succeeds even when Telegram fails."""
    config = {
        "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"}
    }

    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot
        # Make Telegram fail
        mock_bot.send_message = AsyncMock(side_effect=Exception("Telegram error"))

        notifier = NotificationService(config)

        # Mock WebSocket manager (succeeds)
        mock_ws_manager = AsyncMock()
        mock_ws_manager.broadcast = AsyncMock()
        notifier.set_websocket_manager(mock_ws_manager)

        # Send notification
        result = await notifier.send_notification("Test", "Message", priority="normal")

        # Should return True because WebSocket succeeded
        assert result is True
        mock_ws_manager.broadcast.assert_called_once()


@pytest.mark.asyncio
async def test_get_notification_stats():
    """Test get_notification_stats method."""
    config = {
        "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"},
    }

    notifier = NotificationService(config)

    stats = notifier.get_notification_stats()

    assert stats["telegram_enabled"] is True
    assert stats["websocket_available"] is False
    assert stats["failed_high_priority_notifications"] == 0

    # Set WebSocket manager
    mock_ws_manager = AsyncMock()
    notifier.set_websocket_manager(mock_ws_manager)

    stats = notifier.get_notification_stats()
    assert stats["websocket_available"] is True


def test_split_message_short_text():
    """Test _split_message with short text that doesn't need splitting."""
    text = "This is a short message"
    result = NotificationService._split_message(text, 4096)
    assert len(result) == 1
    assert result[0] == text


def test_split_message_long_text():
    """Test _split_message with long text that needs splitting."""
    # Create a message longer than 4096 characters
    text = "A" * 5000
    result = NotificationService._split_message(text, 4096)
    assert len(result) == 2
    assert len(result[0]) <= 4096
    assert len(result[1]) <= 4096
    # Verify all text is preserved
    assert "".join(result) == text


def test_split_message_splits_at_newline():
    """Test _split_message prefers splitting at newline."""
    # Create a message with newlines that exceeds the limit
    text = "A" * 100 + "\n" + "B" * 100 + "\n" + "C" * 4000
    result = NotificationService._split_message(text, 4096)
    # Should split into at least 2 chunks
    assert len(result) >= 2
    # First chunk should be exactly what fits before the second newline
    expected_first_chunk = "A" * 100 + "\n" + "B" * 100
    assert result[0] == expected_first_chunk
    # Second chunk should start with the C's
    assert result[1].startswith("C")


def test_split_message_splits_at_space():
    """Test _split_message falls back to splitting at space."""
    # Create a message with spaces but no newlines
    text = "Word " * 1000  # Creates a long message with spaces
    result = NotificationService._split_message(text, 100)
    # Should split into multiple chunks
    assert len(result) > 1
    # Each chunk should be <= 100 characters
    for chunk in result:
        assert len(chunk) <= 100


@pytest.mark.asyncio
async def test_send_telegram_long_message_splits():
    """Test send_telegram splits long messages into multiple sends."""
    config = {
        "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"}
    }

    # Create a very long message (more than 4096 characters)
    long_message = "A" * 5000

    with patch("src.services.notification.notification.Bot") as MockBot:
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        MockBot.return_value = mock_bot

        notifier = NotificationService(config)
        result = await notifier.send_telegram("Title", long_message)

        assert result is True
        # Should have been called multiple times for the split message
        assert mock_bot.send_message.call_count > 1
