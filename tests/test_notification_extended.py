"""Extended tests for src/services/notification.py - aiming for 99% coverage."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.notification import NotificationService


@pytest.mark.asyncio
class TestSendTelegram:
    """Tests for send_telegram method."""

    async def test_send_telegram_success(self):
        """Test successful telegram notification."""
        config = {
            "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "123456"}
        }
        service = NotificationService(config)

        with patch("src.services.notification.Bot") as mock_bot_class:
            mock_bot = AsyncMock()
            mock_bot.send_message = AsyncMock()
            mock_bot_class.return_value = mock_bot

            result = await service.send_telegram("Test Title", "Test message")

            assert result is True
            mock_bot.send_message.assert_called_once()

    async def test_send_telegram_missing_credentials(self):
        """Test telegram notification with missing credentials."""
        config = {"telegram": {"enabled": True}}
        service = NotificationService(config)

        result = await service.send_telegram("Test Title", "Test message")

        assert result is False

    async def test_send_telegram_exception(self):
        """Test telegram notification with exception."""
        config = {
            "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "123456"}
        }
        service = NotificationService(config)

        with patch("src.services.notification.Bot") as mock_bot_class:
            mock_bot_class.side_effect = Exception("Telegram error")

            result = await service.send_telegram("Test Title", "Test message")

            assert result is False


@pytest.mark.asyncio
class TestSendEmail:
    """Tests for send_email method."""

    async def test_send_email_success(self):
        """Test successful email notification."""
        config = {
            "email": {
                "enabled": True,
                "sender": "sender@example.com",
                "password": "password",
                "receiver": "receiver@example.com",
                "smtp_server": "smtp.example.com",
                "smtp_port": 587,
            }
        }
        service = NotificationService(config)

        with patch("src.services.notification.aiosmtplib.SMTP") as mock_smtp:
            mock_smtp_instance = AsyncMock()
            mock_smtp_instance.__aenter__ = AsyncMock(return_value=mock_smtp_instance)
            mock_smtp_instance.__aexit__ = AsyncMock()
            mock_smtp_instance.starttls = AsyncMock()
            mock_smtp_instance.login = AsyncMock()
            mock_smtp_instance.send_message = AsyncMock()
            mock_smtp.return_value = mock_smtp_instance

            result = await service.send_email("Test Subject", "Test body")

            assert result is True
            mock_smtp_instance.starttls.assert_called_once()
            mock_smtp_instance.login.assert_called_once()
            mock_smtp_instance.send_message.assert_called_once()

    async def test_send_email_missing_credentials(self):
        """Test email notification with missing credentials."""
        config = {"email": {"enabled": True}}
        service = NotificationService(config)

        result = await service.send_email("Test Subject", "Test body")

        assert result is False

    async def test_send_email_exception(self):
        """Test email notification with exception."""
        config = {
            "email": {
                "enabled": True,
                "sender": "sender@example.com",
                "password": "password",
                "receiver": "receiver@example.com",
            }
        }
        service = NotificationService(config)

        with patch("src.services.notification.aiosmtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = Exception("SMTP error")

            result = await service.send_email("Test Subject", "Test body")

            assert result is False


@pytest.mark.asyncio
class TestSendNotification:
    """Tests for send_notification method."""

    async def test_send_notification_telegram_only(self):
        """Test notification with telegram only."""
        config = {
            "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "123456"},
            "email": {"enabled": False},
        }
        service = NotificationService(config)

        with patch.object(service, "send_telegram", return_value=True) as mock_telegram:
            await service.send_notification("Title", "Message")

            mock_telegram.assert_called_once_with("Title", "Message")

    async def test_send_notification_email_only(self):
        """Test notification with email only."""
        config = {
            "telegram": {"enabled": False},
            "email": {
                "enabled": True,
                "sender": "sender@example.com",
                "password": "password",
                "receiver": "receiver@example.com",
            },
        }
        service = NotificationService(config)

        with patch.object(service, "send_email", return_value=True) as mock_email:
            await service.send_notification("Title", "Message")

            mock_email.assert_called_once_with("Title", "Message")

    async def test_send_notification_both_channels(self):
        """Test notification with both channels enabled."""
        config = {
            "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "123456"},
            "email": {
                "enabled": True,
                "sender": "sender@example.com",
                "password": "password",
                "receiver": "receiver@example.com",
            },
        }
        service = NotificationService(config)

        with patch.object(service, "send_telegram", return_value=True) as mock_telegram:
            with patch.object(service, "send_email", return_value=True) as mock_email:
                await service.send_notification("Title", "Message")

                mock_telegram.assert_called_once()
                mock_email.assert_called_once()

    async def test_send_notification_no_channels(self):
        """Test notification with no channels enabled."""
        config = {"telegram": {"enabled": False}, "email": {"enabled": False}}
        service = NotificationService(config)

        # Should not raise exception, just log warning
        await service.send_notification("Title", "Message")

    async def test_send_notification_with_exception(self):
        """Test notification when one channel raises exception."""
        config = {
            "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "123456"},
            "email": {"enabled": False},
        }
        service = NotificationService(config)

        with patch.object(
            service, "send_telegram", side_effect=Exception("Telegram failed")
        ) as mock_telegram:
            # Should not raise exception, gather handles it
            await service.send_notification("Title", "Message")

            mock_telegram.assert_called_once()


@pytest.mark.asyncio
class TestNotifySlotFound:
    """Tests for notify_slot_found method."""

    async def test_notify_slot_found(self):
        """Test slot found notification."""
        config = {"telegram": {"enabled": False}, "email": {"enabled": False}}
        service = NotificationService(config)

        with patch.object(service, "send_notification") as mock_send:
            await service.notify_slot_found(
                centre="Istanbul", date="2024-01-15", time="10:00 AM"
            )

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "Appointment Slot Found" in call_args[0][0]
            assert "Istanbul" in call_args[0][1]


@pytest.mark.asyncio
class TestNotifyBookingSuccess:
    """Tests for notify_booking_success method."""

    async def test_notify_booking_success(self):
        """Test booking success notification."""
        config = {"telegram": {"enabled": False}, "email": {"enabled": False}}
        service = NotificationService(config)

        with patch.object(service, "send_notification") as mock_send:
            await service.notify_booking_success(
                centre="Istanbul", date="2024-01-15", time="10:00 AM", reference="REF123"
            )

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "Appointment Booked Successfully" in call_args[0][0]
            assert "REF123" in call_args[0][1]


@pytest.mark.asyncio
class TestNotifyError:
    """Tests for notify_error method."""

    async def test_notify_error(self):
        """Test error notification."""
        config = {"telegram": {"enabled": False}, "email": {"enabled": False}}
        service = NotificationService(config)

        with patch.object(service, "send_notification") as mock_send:
            await service.notify_error(error_type="LoginError", details="Failed to login")

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "Error: LoginError" in call_args[0][0]
            assert "Failed to login" in call_args[0][1]


@pytest.mark.asyncio
class TestNotifyBotStarted:
    """Tests for notify_bot_started method."""

    async def test_notify_bot_started(self):
        """Test bot started notification."""
        config = {"telegram": {"enabled": False}, "email": {"enabled": False}}
        service = NotificationService(config)

        with patch.object(service, "send_notification") as mock_send:
            await service.notify_bot_started()

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "VFS-Bot Started" in call_args[0][0]


@pytest.mark.asyncio
class TestNotifyBotStopped:
    """Tests for notify_bot_stopped method."""

    async def test_notify_bot_stopped(self):
        """Test bot stopped notification."""
        config = {"telegram": {"enabled": False}, "email": {"enabled": False}}
        service = NotificationService(config)

        with patch.object(service, "send_notification") as mock_send:
            await service.notify_bot_stopped()

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "VFS-Bot Stopped" in call_args[0][0]
