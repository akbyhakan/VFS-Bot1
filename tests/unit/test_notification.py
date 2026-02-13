"""Tests for notification service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.notification import NotificationService


def test_notification_service_initialization():
    """Test notification service initialization."""
    config = {
        "telegram": {"enabled": True, "bot_token": "test", "chat_id": "123"},
        "email": {"enabled": False},
    }

    notifier = NotificationService(config)
    assert notifier.telegram_enabled is True
    assert notifier.email_enabled is False


def test_notification_service_disabled():
    """Test notification service with all channels disabled."""
    config = {"telegram": {"enabled": False}, "email": {"enabled": False}}

    notifier = NotificationService(config)
    assert notifier.telegram_enabled is False
    assert notifier.email_enabled is False


def test_notification_service_empty_config():
    """Test notification service with empty config."""
    config = {}
    notifier = NotificationService(config)
    assert notifier.telegram_enabled is False
    assert notifier.email_enabled is False


@pytest.mark.asyncio
async def test_notification_with_no_channels():
    """Test sending notification with no channels enabled."""
    config = {"telegram": {"enabled": False}, "email": {"enabled": False}}

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
async def test_send_email_missing_credentials():
    """Test email notification with missing credentials."""
    config = {"email": {"enabled": True, "sender": None, "password": None, "receiver": None}}

    notifier = NotificationService(config)
    result = await notifier.send_email("Test Subject", "Test Body")
    assert result is False


@pytest.mark.asyncio
async def test_send_email_exception():
    """Test email notification exception handling with retry."""
    config = {
        "email": {
            "enabled": True,
            "sender": "sender@example.com",
            "password": "password",
            "receiver": "receiver@example.com",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
        }
    }

    notifier = NotificationService(config)

    with patch("src.services.notification.aiosmtplib.SMTP") as MockSMTP:
        # Make SMTP raise exception on all attempts
        mock_smtp_instance = AsyncMock()
        MockSMTP.return_value.__aenter__.return_value = mock_smtp_instance
        mock_smtp_instance.starttls = AsyncMock(side_effect=Exception("SMTP error"))

        result = await notifier.send_email("Test", "Message")
        assert result is False

        # Verify retry happened (1 initial + 2 retries = 3 total attempts)
        assert mock_smtp_instance.starttls.call_count == 3


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
async def test_send_email_retry_then_success():
    """Test email notification succeeds after retry."""
    config = {
        "email": {
            "enabled": True,
            "sender": "sender@example.com",
            "password": "password",
            "receiver": "receiver@example.com",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
        }
    }

    notifier = NotificationService(config)

    with patch("src.services.notification.aiosmtplib.SMTP") as MockSMTP:
        mock_smtp_instance = AsyncMock()
        MockSMTP.return_value.__aenter__.return_value = mock_smtp_instance

        # First call fails, second succeeds
        mock_smtp_instance.starttls = AsyncMock(
            side_effect=[Exception("Transient error"), None]  # Success
        )
        mock_smtp_instance.login = AsyncMock()
        mock_smtp_instance.send_message = AsyncMock()

        result = await notifier.send_email("Test", "Message")
        assert result is True

        # Verify retry happened (2 calls: 1 failure + 1 success)
        assert mock_smtp_instance.starttls.call_count == 2


@pytest.mark.asyncio
async def test_notify_slot_found():
    """Test slot found notification."""
    config = {"telegram": {"enabled": False}, "email": {"enabled": False}}
    notifier = NotificationService(config)

    # Should not raise exception
    await notifier.notify_slot_found("Istanbul", "2024-01-15", "10:00")


@pytest.mark.asyncio
async def test_notify_booking_success():
    """Test booking success notification."""
    config = {"telegram": {"enabled": False}, "email": {"enabled": False}}
    notifier = NotificationService(config)

    # Should not raise exception
    await notifier.notify_booking_success("Istanbul", "2024-01-15", "10:00", "REF123")


@pytest.mark.asyncio
async def test_notify_error():
    """Test error notification."""
    config = {"telegram": {"enabled": False}, "email": {"enabled": False}}
    notifier = NotificationService(config)

    # Should not raise exception
    await notifier.notify_error("ConnectionError", "Failed to connect to VFS website")


@pytest.mark.asyncio
async def test_notify_bot_started():
    """Test bot started notification."""
    config = {"telegram": {"enabled": False}, "email": {"enabled": False}}
    notifier = NotificationService(config)

    # Should not raise exception
    await notifier.notify_bot_started()


@pytest.mark.asyncio
async def test_notify_bot_stopped():
    """Test bot stopped notification."""
    config = {"telegram": {"enabled": False}, "email": {"enabled": False}}
    notifier = NotificationService(config)

    # Should not raise exception
    await notifier.notify_bot_stopped()


@pytest.mark.asyncio
async def test_send_notification_with_telegram_enabled():
    """Test send_notification with Telegram enabled."""
    config = {
        "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"},
        "email": {"enabled": False},
    }

    notifier = NotificationService(config)

    with patch.object(notifier, "send_telegram", new_callable=AsyncMock) as mock_telegram:
        mock_telegram.return_value = True
        await notifier.send_notification("Test", "Message")
        mock_telegram.assert_called_once_with("Test", "Message")


@pytest.mark.asyncio
async def test_send_notification_with_email_enabled():
    """Test send_notification with email enabled."""
    config = {
        "telegram": {"enabled": False},
        "email": {
            "enabled": True,
            "sender": "sender@example.com",
            "password": "password",
            "receiver": "receiver@example.com",
        },
    }

    notifier = NotificationService(config)

    with patch.object(notifier, "send_email", new_callable=AsyncMock) as mock_email:
        mock_email.return_value = True
        await notifier.send_notification("Test", "Message")
        mock_email.assert_called_once_with("Test", "Message")


@pytest.mark.asyncio
async def test_send_notification_with_both_channels():
    """Test send_notification with both channels enabled."""
    config = {
        "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"},
        "email": {
            "enabled": True,
            "sender": "sender@example.com",
            "password": "password",
            "receiver": "receiver@example.com",
        },
    }

    notifier = NotificationService(config)

    with (
        patch.object(notifier, "send_telegram", new_callable=AsyncMock) as mock_telegram,
        patch.object(notifier, "send_email", new_callable=AsyncMock) as mock_email,
    ):
        mock_telegram.return_value = True
        mock_email.return_value = True
        await notifier.send_notification("Test", "Message")
        mock_telegram.assert_called_once()
        mock_email.assert_called_once()


@pytest.mark.asyncio
async def test_send_notification_priority():
    """Test send_notification with priority parameter."""
    config = {"telegram": {"enabled": False}, "email": {"enabled": False}}
    notifier = NotificationService(config)

    # Should not raise exception with different priority levels
    await notifier.send_notification("Test", "Message", priority="low")
    await notifier.send_notification("Test", "Message", priority="normal")
    await notifier.send_notification("Test", "Message", priority="high")


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
    # Should split at the newline
    assert len(result) >= 1
    # First chunk should end near a newline
    assert result[0].endswith("B" * 100) or "\n" in result[0]


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

    with patch("src.services.notification.Bot") as MockBot:
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        MockBot.return_value = mock_bot

        notifier = NotificationService(config)
        result = await notifier.send_telegram("Title", long_message)

        assert result is True
        # Should have been called multiple times for the split message
        assert mock_bot.send_message.call_count > 1
