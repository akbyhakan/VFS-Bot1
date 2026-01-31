"""Tests for OTP Manager."""

import pytest
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.otp_manager import (
    OTPManager,
    SessionRegistry,
    OTPPatternMatcher,
    EmailProcessor,
    IMAPListener,
    SMSWebhookHandler,
    OTPEntry,
    BotSession,
    IMAPConfig,
    OTPSource,
    SessionState,
    HTMLTextExtractor,
)


class TestOTPPatternMatcher:
    """Tests for OTP pattern matching."""

    def test_extract_6_digit_otp_basic(self):
        """Test basic 6-digit OTP extraction."""
        matcher = OTPPatternMatcher()
        assert matcher.extract_otp("Your code is 123456") == "123456"

    def test_extract_vfs_global_otp(self):
        """Test VFS Global specific pattern."""
        matcher = OTPPatternMatcher()
        text = "VFS Global verification code: 987654"
        assert matcher.extract_otp(text) == "987654"

    def test_extract_turkish_dogrulama_kodu(self):
        """Test Turkish 'doğrulama kodu' pattern."""
        matcher = OTPPatternMatcher()
        assert matcher.extract_otp("Doğrulama kodu: 654321") == "654321"

    def test_extract_turkish_dogrulama(self):
        """Test Turkish 'doğrulama' pattern."""
        matcher = OTPPatternMatcher()
        assert matcher.extract_otp("Doğrulama: 111222") == "111222"

    def test_extract_turkish_tek_kullanimlik_sifre(self):
        """Test Turkish 'tek kullanımlık şifre' pattern."""
        matcher = OTPPatternMatcher()
        assert matcher.extract_otp("Tek kullanımlık şifre: 333444") == "333444"

    def test_extract_otp_code_pattern(self):
        """Test 'OTP:' pattern."""
        matcher = OTPPatternMatcher()
        assert matcher.extract_otp("OTP: 555666") == "555666"

    def test_extract_code_pattern(self):
        """Test 'code:' pattern."""
        matcher = OTPPatternMatcher()
        assert matcher.extract_otp("code: 777888") == "777888"

    def test_extract_verification_code_pattern(self):
        """Test 'verification code:' pattern."""
        matcher = OTPPatternMatcher()
        assert matcher.extract_otp("verification code: 999000") == "999000"

    def test_no_otp_found(self):
        """Test when no OTP is present."""
        matcher = OTPPatternMatcher()
        assert matcher.extract_otp("Hello world") is None

    def test_custom_pattern(self):
        """Test custom regex pattern."""
        custom_patterns = [r"PIN[:\s]+(\d{4})"]
        matcher = OTPPatternMatcher(custom_patterns)
        assert matcher.extract_otp("PIN: 1234") == "1234"


class TestHTMLTextExtractor:
    """Tests for HTML text extraction."""

    def test_extract_plain_text(self):
        """Test extracting text from HTML."""
        html = "<html><body><p>Your code is 123456</p></body></html>"
        extractor = HTMLTextExtractor()
        extractor.feed(html)
        text = extractor.get_text()
        assert "123456" in text

    def test_extract_ignores_script(self):
        """Test that script tags are ignored."""
        html = "<html><body><script>alert('test')</script><p>123456</p></body></html>"
        extractor = HTMLTextExtractor()
        extractor.feed(html)
        text = extractor.get_text()
        assert "alert" not in text
        assert "123456" in text

    def test_extract_ignores_style(self):
        """Test that style tags are ignored."""
        html = "<html><body><style>body { color: red; }</style><p>123456</p></body></html>"
        extractor = HTMLTextExtractor()
        extractor.feed(html)
        text = extractor.get_text()
        assert "color" not in text
        assert "123456" in text


class TestSessionRegistry:
    """Tests for SessionRegistry."""

    def test_register_session_with_email(self):
        """Test registering a session with email."""
        registry = SessionRegistry()
        session_id = registry.register(target_email="test@example.com")

        assert session_id is not None
        session = registry.get_session(session_id)
        assert session is not None
        assert session.target_email == "test@example.com"
        assert session.state == SessionState.ACTIVE

    def test_register_session_with_phone(self):
        """Test registering a session with phone number."""
        registry = SessionRegistry()
        session_id = registry.register(phone_number="+905551234567")

        assert session_id is not None
        session = registry.get_session(session_id)
        assert session is not None
        assert session.phone_number == "+905551234567"

    def test_register_session_with_metadata(self):
        """Test registering a session with metadata."""
        registry = SessionRegistry()
        metadata = {"country": "Netherlands", "purpose": "visa"}
        session_id = registry.register(target_email="test@example.com", metadata=metadata)

        session = registry.get_session(session_id)
        assert session.metadata == metadata

    def test_find_by_email(self):
        """Test finding session by email."""
        registry = SessionRegistry()
        session_id = registry.register(target_email="test@example.com")

        session = registry.find_by_email("test@example.com")
        assert session is not None
        assert session.session_id == session_id

    def test_find_by_email_case_insensitive(self):
        """Test finding session by email (case insensitive)."""
        registry = SessionRegistry()
        session_id = registry.register(target_email="test@example.com")

        session = registry.find_by_email("TEST@EXAMPLE.COM")
        assert session is not None
        assert session.session_id == session_id

    def test_find_by_phone(self):
        """Test finding session by phone number."""
        registry = SessionRegistry()
        session_id = registry.register(phone_number="+905551234567")

        session = registry.find_by_phone("+905551234567")
        assert session is not None
        assert session.session_id == session_id

    def test_notify_otp(self):
        """Test notifying session about OTP."""
        registry = SessionRegistry()
        session_id = registry.register(target_email="test@example.com")

        result = registry.notify_otp(session_id, "123456")
        assert result is True

        session = registry.get_session(session_id)
        assert session.otp_code == "123456"
        assert session.state == SessionState.OTP_RECEIVED
        assert session.otp_event.is_set()

    def test_unregister_session(self):
        """Test unregistering a session."""
        registry = SessionRegistry()
        session_id = registry.register(
            target_email="test@example.com", phone_number="+905551234567"
        )

        result = registry.unregister(session_id)
        assert result is True

        # Verify session is removed
        assert registry.get_session(session_id) is None
        assert registry.find_by_email("test@example.com") is None
        assert registry.find_by_phone("+905551234567") is None

    def test_cleanup_expired_sessions(self):
        """Test cleaning up expired sessions."""
        registry = SessionRegistry(session_timeout_seconds=1)
        session_id = registry.register(target_email="test@example.com")

        # Wait for expiration
        time.sleep(1.5)

        removed = registry.cleanup_expired()
        assert removed == 1
        assert registry.get_session(session_id) is None

    def test_get_all_sessions(self):
        """Test getting all active sessions."""
        registry = SessionRegistry()
        _session_id1 = registry.register(target_email="test1@example.com")
        _session_id2 = registry.register(target_email="test2@example.com")

        sessions = registry.get_all_sessions()
        assert len(sessions) == 2


class TestEmailProcessor:
    """Tests for EmailProcessor."""

    def test_extract_target_email_from_to_header(self):
        """Test extracting target email from To header."""
        processor = EmailProcessor(OTPPatternMatcher())

        # Create mock message
        msg = Mock()
        msg.get.side_effect = lambda h, d="": {
            "To": "test@example.com",
            "Subject": "",
            "Date": "",
        }.get(h, d)
        msg.is_multipart.return_value = False
        msg.get_content_type.return_value = "text/plain"
        msg.get_payload.return_value = b"Your code is 123456"

        target = processor._extract_target_email(msg)
        assert target == "test@example.com"

    def test_extract_target_email_from_delivered_to(self):
        """Test extracting target email from Delivered-To header."""
        processor = EmailProcessor(OTPPatternMatcher())

        msg = Mock()
        msg.get.side_effect = lambda h, d="": {
            "Delivered-To": "bot55@vizecep.com",
            "Subject": "",
            "Date": "",
        }.get(h, d)
        msg.is_multipart.return_value = False
        msg.get_content_type.return_value = "text/plain"
        msg.get_payload.return_value = b"Your code is 123456"

        target = processor._extract_target_email(msg)
        assert target == "bot55@vizecep.com"

    def test_process_email_with_otp(self):
        """Test processing email with OTP."""
        processor = EmailProcessor(OTPPatternMatcher())

        msg = Mock()
        msg.get.side_effect = lambda h, d="": {
            "To": "test@example.com",
            "Subject": "Verification Code",
            "Date": "Wed, 29 Jan 2026 10:00:00 +0000",
        }.get(h, d)
        msg.is_multipart.return_value = False
        msg.get_content_type.return_value = "text/plain"
        msg.get_payload.return_value = b"Your verification code is 123456"

        otp_entry = processor.process_email(msg)

        assert otp_entry is not None
        assert otp_entry.code == "123456"
        assert otp_entry.source == OTPSource.EMAIL
        assert otp_entry.target_identifier == "test@example.com"

    def test_process_email_without_otp(self):
        """Test processing email without OTP."""
        processor = EmailProcessor(OTPPatternMatcher())

        msg = Mock()
        msg.get.side_effect = lambda h, d="": {
            "To": "test@example.com",
            "Subject": "Hello",
            "Date": "",
        }.get(h, d)
        msg.is_multipart.return_value = False
        msg.get_content_type.return_value = "text/plain"
        msg.get_payload.return_value = b"Hello world"

        otp_entry = processor.process_email(msg)
        assert otp_entry is None


class TestSMSWebhookHandler:
    """Tests for SMSWebhookHandler."""

    def test_process_sms_with_valid_otp(self):
        """Test processing SMS with valid OTP."""
        registry = SessionRegistry()
        session_id = registry.register(phone_number="+905551234567")

        handler = SMSWebhookHandler(registry, OTPPatternMatcher())
        otp = handler.process_sms("+905551234567", "Your code is 123456")

        assert otp == "123456"
        session = registry.get_session(session_id)
        assert session.otp_code == "123456"

    def test_process_sms_without_otp(self):
        """Test processing SMS without OTP."""
        registry = SessionRegistry()
        handler = SMSWebhookHandler(registry, OTPPatternMatcher())

        otp = handler.process_sms("+905551234567", "Hello world")
        assert otp is None

    def test_process_sms_no_matching_session(self):
        """Test processing SMS with no matching session."""
        registry = SessionRegistry()
        handler = SMSWebhookHandler(registry, OTPPatternMatcher())

        otp = handler.process_sms("+905551234567", "Your code is 123456")
        assert otp is None  # No session found


class TestOTPManagerIntegration:
    """Integration tests for OTPManager."""

    def test_register_and_unregister_session(self):
        """Test session registration and unregistration."""
        with patch("src.services.otp_manager.IMAPListener"):
            manager = OTPManager(email="test@example.com", app_password="password")

            session_id = manager.register_session(
                target_email="bot@example.com", phone_number="+905551234567", country="Netherlands"
            )

            assert session_id is not None
            manager.unregister_session(session_id)

    def test_manual_otp_input(self):
        """Test manual OTP input."""
        with patch("src.services.otp_manager.IMAPListener"):
            manager = OTPManager(email="test@example.com", app_password="password")

            session_id = manager.register_session(target_email="bot@example.com")
            result = manager.manual_otp_input(session_id, "123456")

            assert result is True

    def test_process_sms_webhook(self):
        """Test SMS webhook processing."""
        with patch("src.services.otp_manager.IMAPListener"):
            manager = OTPManager(email="test@example.com", app_password="password")

            _session_id = manager.register_session(phone_number="+905551234567")
            otp = manager.process_sms_webhook("+905551234567", "Your code is 123456")

            assert otp == "123456"

    def test_health_check(self):
        """Test health check."""
        with patch("src.services.otp_manager.IMAPListener"):
            manager = OTPManager(email="test@example.com", app_password="password")

            health = manager.health_check()

            assert "status" in health
            assert "active_sessions" in health
            assert "otp_timeout_seconds" in health

    def test_start_and_stop(self):
        """Test starting and stopping manager."""
        with patch("src.services.otp_manager.IMAPListener") as mock_listener_class:
            mock_listener = Mock()
            mock_listener_class.return_value = mock_listener

            manager = OTPManager(email="test@example.com", app_password="password")

            manager.start()
            assert manager._running is True
            mock_listener.start.assert_called_once()

            manager.stop()
            assert manager._running is False
            mock_listener.stop.assert_called_once()


class TestConcurrentSessions:
    """Tests for concurrent session handling."""

    def test_multiple_concurrent_sessions(self):
        """Test handling multiple concurrent sessions."""
        registry = SessionRegistry()

        # Register multiple sessions
        sessions = []
        for i in range(10):
            session_id = registry.register(
                target_email=f"bot{i}@example.com", phone_number=f"+9055512345{i:02d}"
            )
            sessions.append(session_id)

        # Verify all sessions exist
        assert len(registry.get_all_sessions()) == 10

        # Notify some sessions
        for i in range(5):
            registry.notify_otp(sessions[i], f"12345{i}")

        # Verify notifications
        for i in range(5):
            session = registry.get_session(sessions[i])
            assert session.otp_code == f"12345{i}"

    def test_thread_safety(self):
        """Test thread safety of session registry."""
        registry = SessionRegistry()
        errors = []

        def register_sessions():
            try:
                for i in range(50):
                    registry.register(target_email=f"bot{i}@example.com")
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=register_sessions)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify no errors
        assert len(errors) == 0

        # Note: Total sessions might be less than 250 due to duplicate emails
        assert len(registry.get_all_sessions()) > 0


class TestIMAPListener:
    """Tests for IMAP listener (mocked)."""

    @patch("src.services.otp_manager.imaplib.IMAP4_SSL")
    def test_imap_connection(self, mock_imap_class):
        """Test IMAP connection establishment."""
        mock_mail = Mock()
        mock_imap_class.return_value = mock_mail
        mock_mail.login.return_value = ("OK", [b"Logged in"])
        mock_mail.select.return_value = ("OK", [b"1"])

        registry = SessionRegistry()
        processor = EmailProcessor(OTPPatternMatcher())

        listener = IMAPListener(
            email="test@example.com",
            app_password="password",
            imap_config=IMAPConfig(),
            email_processor=processor,
            session_registry=registry,
        )

        _mail = listener._connect_imap()

        mock_imap_class.assert_called_once_with("outlook.office365.com", 993)
        mock_mail.login.assert_called_once_with("test@example.com", "password")
        mock_mail.select.assert_called_once_with("INBOX")

    @patch("src.services.otp_manager.imaplib.IMAP4_SSL")
    def test_imap_listener_start_stop(self, mock_imap_class):
        """Test starting and stopping IMAP listener."""
        mock_mail = Mock()
        mock_imap_class.return_value = mock_mail
        mock_mail.login.return_value = ("OK", [b"Logged in"])
        mock_mail.select.return_value = ("OK", [b"1"])
        mock_mail.search.return_value = ("OK", [b""])

        registry = SessionRegistry()
        processor = EmailProcessor(OTPPatternMatcher())

        listener = IMAPListener(
            email="test@example.com",
            app_password="password",
            imap_config=IMAPConfig(),
            email_processor=processor,
            session_registry=registry,
            poll_interval=1,
        )

        listener.start()
        assert listener._running is True

        time.sleep(0.5)

        listener.stop()
        assert listener._running is False


@pytest.mark.unit
class TestOTPManagerUnit:
    """Unit tests for OTPManager components."""

    def test_session_registry_initialization(self):
        """Test SessionRegistry initialization."""
        registry = SessionRegistry(session_timeout_seconds=300)
        assert registry._session_timeout == 300

    def test_otp_pattern_matcher_initialization(self):
        """Test OTPPatternMatcher initialization."""
        matcher = OTPPatternMatcher()
        assert len(matcher._patterns) > 0

    def test_email_processor_initialization(self):
        """Test EmailProcessor initialization."""
        matcher = OTPPatternMatcher()
        processor = EmailProcessor(matcher)
        assert processor._pattern_matcher == matcher
