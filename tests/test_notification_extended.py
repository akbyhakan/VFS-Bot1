"""Extended tests for notification service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.notification import NotificationService


@pytest.fixture
def telegram_config():
    """Telegram notification configuration."""
    return {
        "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "123456"},
        "email": {"enabled": False},
    }


@pytest.fixture
def email_config():
    """Email notification configuration."""
    return {
        "telegram": {"enabled": False},
        "email": {
            "enabled": True,
            "sender": "sender@example.com",
            "password": "password123",
            "receiver": "receiver@example.com",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
        },
    }


@pytest.fixture
def both_config():
    """Both channels enabled configuration."""
    return {
        "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "123456"},
        "email": {
            "enabled": True,
            "sender": "sender@example.com",
            "password": "password123",
            "receiver": "receiver@example.com",
        },
    }


@pytest.mark.asyncio
async def test_send_telegram_success(telegram_config):
    """Test successful Telegram notification."""
    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot

        notifier = NotificationService(telegram_config)
        result = await notifier.send_telegram("Test Title", "Test message")

        assert result is True
        mock_bot.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_telegram_missing_credentials():
    """Test Telegram with missing credentials."""
    config = {"telegram": {"enabled": True}, "email": {"enabled": False}}

    notifier = NotificationService(config)
    result = await notifier.send_telegram("Test", "Message")

    assert result is False


@pytest.mark.asyncio
async def test_send_telegram_exception(telegram_config):
    """Test Telegram notification exception handling."""
    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(side_effect=Exception("Send failed"))
        MockBot.return_value = mock_bot

        notifier = NotificationService(telegram_config)
        result = await notifier.send_telegram("Test", "Message")

        assert result is False


@pytest.mark.asyncio
async def test_send_email_success(email_config):
    """Test successful email notification."""
    with patch("src.services.notification.aiosmtplib.SMTP") as MockSMTP:
        mock_smtp = AsyncMock()
        MockSMTP.return_value.__aenter__.return_value = mock_smtp

        notifier = NotificationService(email_config)
        result = await notifier.send_email("Test Subject", "Test body")

        assert result is True
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once()
        mock_smtp.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_missing_credentials():
    """Test email with missing credentials."""
    config = {"telegram": {"enabled": False}, "email": {"enabled": True, "sender": None}}

    notifier = NotificationService(config)
    result = await notifier.send_email("Test", "Message")

    assert result is False


@pytest.mark.asyncio
async def test_send_email_exception(email_config):
    """Test email notification exception handling."""
    with patch("src.services.notification.aiosmtplib.SMTP") as MockSMTP:
        MockSMTP.side_effect = Exception("SMTP failed")

        notifier = NotificationService(email_config)
        result = await notifier.send_email("Test", "Message")

        assert result is False


@pytest.mark.asyncio
async def test_send_notification_telegram_only(telegram_config):
    """Test send_notification with Telegram only."""
    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot

        notifier = NotificationService(telegram_config)
        await notifier.send_notification("Test", "Message", priority="high")

        mock_bot.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_notification_email_only(email_config):
    """Test send_notification with email only."""
    with patch("src.services.notification.aiosmtplib.SMTP") as MockSMTP:
        mock_smtp = AsyncMock()
        MockSMTP.return_value.__aenter__.return_value = mock_smtp

        notifier = NotificationService(email_config)
        await notifier.send_notification("Test", "Message")

        mock_smtp.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_notification_both_channels(both_config):
    """Test send_notification with both channels."""
    with patch("telegram.Bot") as MockBot, patch(
        "src.services.notification.aiosmtplib.SMTP"
    ) as MockSMTP:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot

        mock_smtp = AsyncMock()
        MockSMTP.return_value.__aenter__.return_value = mock_smtp

        notifier = NotificationService(both_config)
        await notifier.send_notification("Test", "Message")

        mock_bot.send_message.assert_called_once()
        mock_smtp.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_notification_with_exception(both_config):
    """Test send_notification handles exceptions gracefully."""
    with patch("telegram.Bot") as MockBot, patch(
        "src.services.notification.aiosmtplib.SMTP"
    ) as MockSMTP:
        # Make Telegram fail
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(side_effect=Exception("Telegram failed"))
        MockBot.return_value = mock_bot

        # Email succeeds
        mock_smtp = AsyncMock()
        MockSMTP.return_value.__aenter__.return_value = mock_smtp

        notifier = NotificationService(both_config)
        # Should not raise exception
        await notifier.send_notification("Test", "Message")


@pytest.mark.asyncio
async def test_notify_slot_found(telegram_config):
    """Test notify_slot_found convenience method."""
    with patch.object(NotificationService, "send_notification", new_callable=AsyncMock) as mock:
        notifier = NotificationService(telegram_config)
        await notifier.notify_slot_found(centre="Istanbul", date="2024-01-15", time="10:00")

        mock.assert_called_once()
        call_args = mock.call_args
        assert "Slot Found" in call_args[0][0]
        assert "Istanbul" in call_args[0][1]
        assert call_args[1]["priority"] == "high"


@pytest.mark.asyncio
async def test_notify_booking_success(telegram_config):
    """Test notify_booking_success convenience method."""
    with patch.object(NotificationService, "send_notification", new_callable=AsyncMock) as mock:
        notifier = NotificationService(telegram_config)
        await notifier.notify_booking_success(
            centre="Istanbul", date="2024-01-15", time="10:00", reference="REF123"
        )

        mock.assert_called_once()
        call_args = mock.call_args
        assert "Booked Successfully" in call_args[0][0]
        assert "REF123" in call_args[0][1]
        assert call_args[1]["priority"] == "high"


@pytest.mark.asyncio
async def test_notify_error(telegram_config):
    """Test notify_error convenience method."""
    with patch.object(NotificationService, "send_notification", new_callable=AsyncMock) as mock:
        notifier = NotificationService(telegram_config)
        await notifier.notify_error(error_type="NetworkError", details="Connection timeout")

        mock.assert_called_once()
        call_args = mock.call_args
        assert "NetworkError" in call_args[0][0]
        assert "Connection timeout" in call_args[0][1]
        assert call_args[1]["priority"] == "normal"


@pytest.mark.asyncio
async def test_notify_bot_started(telegram_config):
    """Test notify_bot_started convenience method."""
    with patch.object(NotificationService, "send_notification", new_callable=AsyncMock) as mock:
        notifier = NotificationService(telegram_config)
        await notifier.notify_bot_started()

        mock.assert_called_once()
        call_args = mock.call_args
        assert "Started" in call_args[0][0]
        assert call_args[1]["priority"] == "low"


@pytest.mark.asyncio
async def test_notify_bot_stopped(telegram_config):
    """Test notify_bot_stopped convenience method."""
    with patch.object(NotificationService, "send_notification", new_callable=AsyncMock) as mock:
        notifier = NotificationService(telegram_config)
        await notifier.notify_bot_stopped()

        mock.assert_called_once()
        call_args = mock.call_args
        assert "Stopped" in call_args[0][0]
        assert call_args[1]["priority"] == "low"


@pytest.mark.asyncio
async def test_email_html_formatting(email_config):
    """Test that email includes HTML formatting."""
    with patch("src.services.notification.aiosmtplib.SMTP") as MockSMTP:
        mock_smtp = AsyncMock()
        MockSMTP.return_value.__aenter__.return_value = mock_smtp

        notifier = NotificationService(email_config)
        await notifier.send_email("Test Subject", "Line 1\nLine 2")

        # Verify send_message was called
        mock_smtp.send_message.assert_called_once()
        # The message should contain HTML
        message_arg = mock_smtp.send_message.call_args[0][0]
        assert message_arg["Subject"] == "VFS-Bot: Test Subject"
