"""Tests for notification service."""

import pytest
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

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

    notifier = NotificationService(config)

    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot
        mock_bot.send_message = AsyncMock()

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
    """Test Telegram notification exception handling."""
    config = {"telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"}}

    notifier = NotificationService(config)

    with patch("telegram.Bot") as MockBot:
        MockBot.side_effect = Exception("Telegram error")
        result = await notifier.send_telegram("Test", "Message")
        assert result is False


@pytest.mark.asyncio
async def test_send_email_missing_credentials():
    """Test email notification with missing credentials."""
    config = {"email": {"enabled": True, "sender": None, "password": None, "receiver": None}}

    notifier = NotificationService(config)
    result = await notifier.send_email("Test Subject", "Test Body")
    assert result is False


@pytest.mark.asyncio
async def test_send_email_exception():
    """Test email notification exception handling."""
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
        MockSMTP.side_effect = Exception("SMTP error")
        result = await notifier.send_email("Test", "Message")
        assert result is False


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

    with patch.object(
        notifier, "send_telegram", new_callable=AsyncMock
    ) as mock_telegram, patch.object(notifier, "send_email", new_callable=AsyncMock) as mock_email:
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
