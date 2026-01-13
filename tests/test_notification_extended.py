"""Extended tests for notification.py - Target 99% coverage."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.notification import NotificationService


@pytest.fixture
def telegram_config():
    """Telegram notification configuration."""
    return {
        "telegram": {
            "enabled": True,
            "bot_token": "test_token_123",
            "chat_id": "123456789",
        },
        "email": {"enabled": False},
    }


@pytest.fixture
def email_config():
    """Email notification configuration."""
    return {
        "telegram": {"enabled": False},
        "email": {
            "enabled": True,
            "sender": "bot@example.com",
            "password": "testpass",
            "receiver": "user@example.com",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
        },
    }


@pytest.fixture
def both_enabled_config():
    """Configuration with both channels enabled."""
    return {
        "telegram": {
            "enabled": True,
            "bot_token": "test_token_123",
            "chat_id": "123456789",
        },
        "email": {
            "enabled": True,
            "sender": "bot@example.com",
            "password": "testpass",
            "receiver": "user@example.com",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
        },
    }


@pytest.fixture
def disabled_config():
    """Configuration with all channels disabled."""
    return {
        "telegram": {"enabled": False},
        "email": {"enabled": False},
    }


def test_notification_service_init_telegram_only(telegram_config):
    """Test NotificationService initialization with Telegram only."""
    service = NotificationService(telegram_config)
    assert service.telegram_enabled is True
    assert service.email_enabled is False


def test_notification_service_init_email_only(email_config):
    """Test NotificationService initialization with email only."""
    service = NotificationService(email_config)
    assert service.telegram_enabled is False
    assert service.email_enabled is True


def test_notification_service_init_both_enabled(both_enabled_config):
    """Test NotificationService initialization with both channels."""
    service = NotificationService(both_enabled_config)
    assert service.telegram_enabled is True
    assert service.email_enabled is True


def test_notification_service_init_all_disabled(disabled_config):
    """Test NotificationService initialization with all channels disabled."""
    service = NotificationService(disabled_config)
    assert service.telegram_enabled is False
    assert service.email_enabled is False


@pytest.mark.asyncio
async def test_send_notification_no_channels_enabled(disabled_config):
    """Test send_notification with no channels enabled."""
    service = NotificationService(disabled_config)
    # Should complete without error but log warning
    await service.send_notification("Test", "Message")


@pytest.mark.asyncio
async def test_send_notification_telegram_only(telegram_config):
    """Test send_notification with Telegram only."""
    service = NotificationService(telegram_config)
    with patch.object(service, "send_telegram", new_callable=AsyncMock) as mock_telegram:
        mock_telegram.return_value = True
        await service.send_notification("Test Title", "Test Message")
        mock_telegram.assert_called_once_with("Test Title", "Test Message")


@pytest.mark.asyncio
async def test_send_notification_email_only(email_config):
    """Test send_notification with email only."""
    service = NotificationService(email_config)
    with patch.object(service, "send_email", new_callable=AsyncMock) as mock_email:
        mock_email.return_value = True
        await service.send_notification("Test Title", "Test Message")
        mock_email.assert_called_once_with("Test Title", "Test Message")


@pytest.mark.asyncio
async def test_send_notification_both_channels(both_enabled_config):
    """Test send_notification with both channels."""
    service = NotificationService(both_enabled_config)
    with patch.object(service, "send_telegram", new_callable=AsyncMock) as mock_telegram, patch.object(
        service, "send_email", new_callable=AsyncMock
    ) as mock_email:
        mock_telegram.return_value = True
        mock_email.return_value = True
        await service.send_notification("Test Title", "Test Message")
        mock_telegram.assert_called_once()
        mock_email.assert_called_once()


@pytest.mark.asyncio
async def test_send_notification_with_priority(telegram_config):
    """Test send_notification with different priority levels."""
    service = NotificationService(telegram_config)
    with patch.object(service, "send_telegram", new_callable=AsyncMock) as mock_telegram:
        mock_telegram.return_value = True
        await service.send_notification("Test", "Message", priority="high")
        mock_telegram.assert_called_once()


@pytest.mark.asyncio
async def test_send_notification_handles_exception(both_enabled_config):
    """Test send_notification handles exceptions gracefully."""
    service = NotificationService(both_enabled_config)
    with patch.object(service, "send_telegram", new_callable=AsyncMock) as mock_telegram, patch.object(
        service, "send_email", new_callable=AsyncMock
    ) as mock_email:
        # Telegram fails, email succeeds
        mock_telegram.side_effect = Exception("Telegram error")
        mock_email.return_value = True
        # Should not raise exception
        await service.send_notification("Test", "Message")


@pytest.mark.asyncio
async def test_send_telegram_success(telegram_config):
    """Test successful Telegram notification."""
    service = NotificationService(telegram_config)
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    with patch("telegram.Bot", return_value=mock_bot):
        result = await service.send_telegram("Test Title", "Test Message")
        assert result is True
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert call_args[1]["chat_id"] == "123456789"
        assert "Test Title" in call_args[1]["text"]
        assert "Test Message" in call_args[1]["text"]
        assert call_args[1]["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_send_telegram_missing_token(telegram_config):
    """Test Telegram notification with missing token."""
    telegram_config["telegram"]["bot_token"] = None
    service = NotificationService(telegram_config)
    result = await service.send_telegram("Test", "Message")
    assert result is False


@pytest.mark.asyncio
async def test_send_telegram_missing_chat_id(telegram_config):
    """Test Telegram notification with missing chat_id."""
    telegram_config["telegram"]["chat_id"] = None
    service = NotificationService(telegram_config)
    result = await service.send_telegram("Test", "Message")
    assert result is False


@pytest.mark.asyncio
async def test_send_telegram_exception(telegram_config):
    """Test Telegram notification with exception."""
    service = NotificationService(telegram_config)
    with patch("telegram.Bot") as mock_bot_class:
        mock_bot_class.side_effect = Exception("Connection error")
        result = await service.send_telegram("Test", "Message")
        assert result is False


@pytest.mark.asyncio
async def test_send_email_success(email_config):
    """Test successful email notification."""
    service = NotificationService(email_config)
    mock_smtp = AsyncMock()

    with patch("aiosmtplib.SMTP") as mock_smtp_class:
        mock_smtp_class.return_value.__aenter__.return_value = mock_smtp
        result = await service.send_email("Test Subject", "Test Body")
        assert result is True
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("bot@example.com", "testpass")
        mock_smtp.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_missing_sender(email_config):
    """Test email notification with missing sender."""
    email_config["email"]["sender"] = None
    service = NotificationService(email_config)
    result = await service.send_email("Test", "Message")
    assert result is False


@pytest.mark.asyncio
async def test_send_email_missing_password(email_config):
    """Test email notification with missing password."""
    email_config["email"]["password"] = None
    service = NotificationService(email_config)
    result = await service.send_email("Test", "Message")
    assert result is False


@pytest.mark.asyncio
async def test_send_email_missing_receiver(email_config):
    """Test email notification with missing receiver."""
    email_config["email"]["receiver"] = None
    service = NotificationService(email_config)
    result = await service.send_email("Test", "Message")
    assert result is False


@pytest.mark.asyncio
async def test_send_email_custom_smtp(email_config):
    """Test email notification with custom SMTP settings."""
    email_config["email"]["smtp_server"] = "smtp.custom.com"
    email_config["email"]["smtp_port"] = 465
    service = NotificationService(email_config)
    mock_smtp = AsyncMock()

    with patch("aiosmtplib.SMTP") as mock_smtp_class:
        mock_smtp_class.return_value.__aenter__.return_value = mock_smtp
        result = await service.send_email("Test", "Message")
        assert result is True
        # Verify custom SMTP settings were used
        mock_smtp_class.assert_called_with(hostname="smtp.custom.com", port=465)


@pytest.mark.asyncio
async def test_send_email_exception(email_config):
    """Test email notification with exception."""
    service = NotificationService(email_config)
    with patch("aiosmtplib.SMTP") as mock_smtp_class:
        mock_smtp_class.side_effect = Exception("SMTP error")
        result = await service.send_email("Test", "Message")
        assert result is False


@pytest.mark.asyncio
async def test_notify_slot_found(telegram_config):
    """Test notify_slot_found method."""
    service = NotificationService(telegram_config)
    with patch.object(service, "send_notification", new_callable=AsyncMock) as mock_send:
        await service.notify_slot_found("Istanbul", "2024-02-15", "10:00")
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        assert "Slot Found" in call_args[0]
        assert "Istanbul" in call_args[1]
        assert "2024-02-15" in call_args[1]
        assert "10:00" in call_args[1]
        assert mock_send.call_args[1]["priority"] == "high"


@pytest.mark.asyncio
async def test_notify_booking_success(telegram_config):
    """Test notify_booking_success method."""
    service = NotificationService(telegram_config)
    with patch.object(service, "send_notification", new_callable=AsyncMock) as mock_send:
        await service.notify_booking_success("Istanbul", "2024-02-15", "10:00", "REF123")
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        assert "Booked Successfully" in call_args[0]
        assert "Istanbul" in call_args[1]
        assert "2024-02-15" in call_args[1]
        assert "10:00" in call_args[1]
        assert "REF123" in call_args[1]
        assert mock_send.call_args[1]["priority"] == "high"


@pytest.mark.asyncio
async def test_notify_error(telegram_config):
    """Test notify_error method."""
    service = NotificationService(telegram_config)
    with patch.object(service, "send_notification", new_callable=AsyncMock) as mock_send:
        await service.notify_error("NetworkError", "Connection timeout occurred")
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        assert "Error" in call_args[0]
        assert "NetworkError" in call_args[0]
        assert "Connection timeout occurred" in call_args[1]
        assert mock_send.call_args[1]["priority"] == "normal"


@pytest.mark.asyncio
async def test_notify_bot_started(telegram_config):
    """Test notify_bot_started method."""
    service = NotificationService(telegram_config)
    with patch.object(service, "send_notification", new_callable=AsyncMock) as mock_send:
        await service.notify_bot_started()
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        assert "Started" in call_args[0]
        assert mock_send.call_args[1]["priority"] == "low"


@pytest.mark.asyncio
async def test_notify_bot_stopped(telegram_config):
    """Test notify_bot_stopped method."""
    service = NotificationService(telegram_config)
    with patch.object(service, "send_notification", new_callable=AsyncMock) as mock_send:
        await service.notify_bot_stopped()
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        assert "Stopped" in call_args[0]
        assert mock_send.call_args[1]["priority"] == "low"


@pytest.mark.asyncio
async def test_email_html_formatting(email_config):
    """Test that email body is properly formatted as HTML."""
    service = NotificationService(email_config)
    mock_smtp = AsyncMock()

    with patch("aiosmtplib.SMTP") as mock_smtp_class:
        mock_smtp_class.return_value.__aenter__.return_value = mock_smtp
        await service.send_email("Test", "Line1\nLine2\nLine3")

        # Verify send_message was called
        assert mock_smtp.send_message.called
        # The message should contain HTML with <br> tags
        message_arg = mock_smtp.send_message.call_args[0][0]
        message_str = message_arg.as_string()
        assert "<br>" in message_str or "text/html" in message_str
