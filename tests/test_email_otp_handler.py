"""Tests for Email OTP Handler."""

import pytest
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.email_otp_handler import (
    EmailOTPHandler,
    EmailOTPPatternMatcher,
    EmailOTPEntry,
    IMAPConfig,
    HTMLTextExtractor,
)


class TestEmailOTPPatternMatcher:
    """Tests for Email OTP pattern matching."""

    def test_extract_6_digit_otp_basic(self):
        """Test basic 6-digit OTP extraction."""
        matcher = EmailOTPPatternMatcher()
        assert matcher.extract_otp("Your code is 123456") == "123456"

    def test_extract_vfs_global_otp(self):
        """Test VFS Global specific pattern."""
        matcher = EmailOTPPatternMatcher()
        text = "VFS Global verification code: 987654"
        assert matcher.extract_otp(text) == "987654"

    def test_extract_turkish_dogrulama_kodu(self):
        """Test Turkish 'doğrulama kodu' pattern."""
        matcher = EmailOTPPatternMatcher()
        assert matcher.extract_otp("Doğrulama kodu: 654321") == "654321"

    def test_extract_turkish_dogrulama(self):
        """Test Turkish 'doğrulama' pattern."""
        matcher = EmailOTPPatternMatcher()
        assert matcher.extract_otp("Doğrulama: 111222") == "111222"

    def test_extract_turkish_tek_kullanimlik_sifre(self):
        """Test Turkish 'tek kullanımlık şifre' pattern."""
        matcher = EmailOTPPatternMatcher()
        assert matcher.extract_otp("Tek kullanımlık şifre: 333444") == "333444"

    def test_extract_otp_keyword(self):
        """Test OTP keyword pattern."""
        matcher = EmailOTPPatternMatcher()
        assert matcher.extract_otp("Your OTP: 555666") == "555666"

    def test_extract_kod_keyword(self):
        """Test Turkish 'kod' keyword pattern."""
        matcher = EmailOTPPatternMatcher()
        assert matcher.extract_otp("Kod: 777888") == "777888"

    def test_extract_code_keyword(self):
        """Test 'code' keyword pattern."""
        matcher = EmailOTPPatternMatcher()
        assert matcher.extract_otp("verification code: 999000") == "999000"

    def test_extract_authentication_code(self):
        """Test authentication code pattern."""
        matcher = EmailOTPPatternMatcher()
        assert matcher.extract_otp("Your authentication code: 112233") == "112233"

    def test_extract_fallback_6_digit(self):
        """Test fallback 6-digit pattern."""
        matcher = EmailOTPPatternMatcher()
        assert matcher.extract_otp("Please use 445566 to verify") == "445566"

    def test_no_otp_found(self):
        """Test when no OTP is present."""
        matcher = EmailOTPPatternMatcher()
        assert matcher.extract_otp("Hello, no code here") is None

    def test_custom_pattern(self):
        """Test custom regex patterns."""
        matcher = EmailOTPPatternMatcher(custom_patterns=[r"PIN:(\d{6})"])
        assert matcher.extract_otp("Your PIN:998877 is ready") == "998877"

    def test_multiline_text(self):
        """Test OTP extraction from multiline text."""
        matcher = EmailOTPPatternMatcher()
        text = """
        Dear User,

        Your VFS Global verification code is:
        123456

        This code will expire in 5 minutes.
        """
        assert matcher.extract_otp(text) == "123456"

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        matcher = EmailOTPPatternMatcher()
        assert matcher.extract_otp("YOUR OTP: 567890") == "567890"
        assert matcher.extract_otp("your otp: 567890") == "567890"


class TestHTMLTextExtractor:
    """Tests for HTML text extraction."""

    def test_extract_plain_text(self):
        """Test plain text extraction."""
        html = "<p>Your code is 123456</p>"
        extractor = HTMLTextExtractor()
        extractor.feed(html)
        text = extractor.get_text()
        assert "123456" in text

    def test_remove_script_tags(self):
        """Test that script content is removed."""
        html = """
        <html>
        <script>var code = "999999";</script>
        <p>Your code is 123456</p>
        </html>
        """
        extractor = HTMLTextExtractor()
        extractor.feed(html)
        text = extractor.get_text()
        assert "123456" in text
        assert "999999" not in text

    def test_remove_style_tags(self):
        """Test that style content is removed."""
        html = """
        <html>
        <style>.code { font-size: 20px; }</style>
        <p>Your OTP: 654321</p>
        </html>
        """
        extractor = HTMLTextExtractor()
        extractor.feed(html)
        text = extractor.get_text()
        assert "654321" in text
        assert "font-size" not in text

    def test_complex_html(self):
        """Test complex HTML structure."""
        html = """
        <html>
        <head><title>OTP Email</title></head>
        <body>
            <div class="header">VFS Global</div>
            <div class="content">
                <p>Dear applicant,</p>
                <p>Your verification code is: <strong>888999</strong></p>
            </div>
        </body>
        </html>
        """
        extractor = HTMLTextExtractor()
        extractor.feed(html)
        text = extractor.get_text()
        assert "888999" in text
        assert "VFS Global" in text


class TestEmailOTPHandler:
    """Tests for EmailOTPHandler with mocked IMAP."""

    @pytest.fixture
    def mock_imap(self):
        """Create mock IMAP connection."""
        with patch("imaplib.IMAP4_SSL") as mock:
            imap_instance = MagicMock()
            mock.return_value = imap_instance

            # Mock successful login and select
            imap_instance.login.return_value = ("OK", [b"Logged in"])
            imap_instance.select.return_value = ("OK", [b"1"])
            imap_instance.search.return_value = ("OK", [b""])
            imap_instance.close.return_value = ("OK", [b""])
            imap_instance.logout.return_value = ("OK", [b"Logging out"])

            yield imap_instance

    def test_initialization(self):
        """Test handler initialization."""
        handler = EmailOTPHandler(email="test@vizecep.com", app_password="test-password")
        assert handler._email == "test@vizecep.com"
        assert handler._app_password == "test-password"
        assert handler._otp_timeout == 120
        assert handler._poll_interval == 5

    def test_custom_configuration(self):
        """Test handler with custom configuration."""
        config = IMAPConfig(host="custom.host", port=993)
        handler = EmailOTPHandler(
            email="test@vizecep.com",
            app_password="test-password",
            imap_config=config,
            otp_timeout_seconds=60,
            poll_interval_seconds=3,
        )
        assert handler._imap_config.host == "custom.host"
        assert handler._otp_timeout == 60
        assert handler._poll_interval == 3

    def test_decode_header_simple(self):
        """Test simple header decoding."""
        handler = EmailOTPHandler(email="test@vizecep.com", app_password="test-password")
        decoded = handler._decode_header_value("test@example.com")
        assert decoded == "test@example.com"

    def test_extract_target_email_from_to_header(self):
        """Test target email extraction from To header."""
        handler = EmailOTPHandler(email="test@vizecep.com", app_password="test-password")

        msg = MagicMock()
        msg.get.side_effect = lambda h: {
            "To": "bot55@vizecep.com",
            "Delivered-To": None,
            "X-Original-To": None,
        }.get(h)

        target = handler._extract_target_email(msg)
        assert target == "bot55@vizecep.com"

    def test_extract_target_email_from_delivered_to(self):
        """Test target email extraction from Delivered-To header."""
        handler = EmailOTPHandler(email="test@vizecep.com", app_password="test-password")

        msg = MagicMock()
        msg.get.side_effect = lambda h: {
            "To": None,
            "Delivered-To": "vize-ist@vizecep.com",
            "X-Original-To": None,
        }.get(h)

        target = handler._extract_target_email(msg)
        assert target == "vize-ist@vizecep.com"

    def test_extract_target_email_with_name(self):
        """Test target email extraction from formatted header."""
        handler = EmailOTPHandler(email="test@vizecep.com", app_password="test-password")

        msg = MagicMock()
        msg.get.side_effect = lambda h: {
            "To": "Bot User <bot77@vizecep.com>",
            "Delivered-To": None,
            "X-Original-To": None,
        }.get(h)

        target = handler._extract_target_email(msg)
        assert target == "bot77@vizecep.com"

    def test_cache_operations(self):
        """Test OTP caching."""
        handler = EmailOTPHandler(email="test@vizecep.com", app_password="test-password")

        # Add to cache
        entry = EmailOTPEntry(
            code="123456",
            target_email="bot1@vizecep.com",
            raw_subject="OTP Code",
            raw_body="Your code is 123456",
            received_at=datetime.now(timezone.utc),
        )
        handler._otp_cache["bot1@vizecep.com"] = entry

        # Get from cache
        otp = handler.get_cached_otp("bot1@vizecep.com")
        assert otp == "123456"

        # Clear specific cache
        handler.clear_cache("bot1@vizecep.com")
        otp = handler.get_cached_otp("bot1@vizecep.com")
        assert otp is None

    def test_cache_expiry(self):
        """Test that expired OTPs are not returned from cache."""
        handler = EmailOTPHandler(
            email="test@vizecep.com", app_password="test-password", max_email_age_seconds=2
        )

        # Add expired entry
        entry = EmailOTPEntry(
            code="123456",
            target_email="bot1@vizecep.com",
            raw_subject="OTP Code",
            raw_body="Your code is 123456",
            received_at=datetime.now(timezone.utc) - timedelta(seconds=5),
        )
        handler._otp_cache["bot1@vizecep.com"] = entry

        # Should not return expired OTP
        otp = handler.get_cached_otp("bot1@vizecep.com")
        assert otp is None

    def test_cache_used_flag(self):
        """Test that used OTPs are not returned from cache."""
        handler = EmailOTPHandler(email="test@vizecep.com", app_password="test-password")

        # Add used entry
        entry = EmailOTPEntry(
            code="123456",
            target_email="bot1@vizecep.com",
            raw_subject="OTP Code",
            raw_body="Your code is 123456",
            received_at=datetime.now(timezone.utc),
            used=True,
        )
        handler._otp_cache["bot1@vizecep.com"] = entry

        # Should not return used OTP
        otp = handler.get_cached_otp("bot1@vizecep.com")
        assert otp is None

    def test_clear_all_cache(self):
        """Test clearing all cache."""
        handler = EmailOTPHandler(email="test@vizecep.com", app_password="test-password")

        # Add multiple entries
        for i in range(3):
            entry = EmailOTPEntry(
                code=f"12345{i}",
                target_email=f"bot{i}@vizecep.com",
                raw_subject="OTP Code",
                raw_body=f"Your code is 12345{i}",
                received_at=datetime.now(timezone.utc),
            )
            handler._otp_cache[f"bot{i}@vizecep.com"] = entry

        # Clear all
        handler.clear_cache()
        assert len(handler._otp_cache) == 0

    def test_thread_safety(self):
        """Test thread-safe operations."""
        handler = EmailOTPHandler(email="test@vizecep.com", app_password="test-password")

        _results = []

        def add_to_cache(email_suffix):
            for i in range(10):
                entry = EmailOTPEntry(
                    code=f"{email_suffix}{i:04d}",
                    target_email=f"bot{email_suffix}@vizecep.com",
                    raw_subject="OTP Code",
                    raw_body=f"Code {email_suffix}{i:04d}",
                    received_at=datetime.now(timezone.utc),
                )
                handler._otp_cache[f"bot{email_suffix}_{i}@vizecep.com"] = entry
                time.sleep(0.001)

        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=add_to_cache, args=(i,))
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Verify cache integrity
        assert len(handler._otp_cache) == 50  # 5 threads * 10 entries

    def test_wait_for_otp_no_emails(self, mock_imap):
        """Test wait_for_otp when no emails are found."""
        handler = EmailOTPHandler(
            email="test@vizecep.com", app_password="test-password", poll_interval_seconds=1
        )

        # Mock no emails
        mock_imap.search.return_value = ("OK", [b""])

        otp = handler.wait_for_otp("bot1@vizecep.com", timeout=2)
        assert otp is None

    def test_close(self):
        """Test handler cleanup."""
        handler = EmailOTPHandler(email="test@vizecep.com", app_password="test-password")

        # Add some cache
        entry = EmailOTPEntry(
            code="123456",
            target_email="bot1@vizecep.com",
            raw_subject="OTP Code",
            raw_body="Your code is 123456",
            received_at=datetime.now(timezone.utc),
        )
        handler._otp_cache["bot1@vizecep.com"] = entry

        # Close should clear cache
        handler.close()
        assert len(handler._otp_cache) == 0


class TestEmailOTPHandlerSingleton:
    """Tests for global handler singleton."""

    def test_get_handler_first_time(self):
        """Test getting handler for first time requires credentials."""
        with pytest.raises(ValueError, match="Email and app_password required"):
            from src.services.email_otp_handler import get_email_otp_handler

            # Reset global
            import src.services.email_otp_handler as module

            module._email_otp_handler = None
            get_email_otp_handler()

    def test_singleton_pattern(self):
        """Test that singleton returns same instance."""
        from src.services.email_otp_handler import get_email_otp_handler
        import src.services.email_otp_handler as module

        # Reset global
        module._email_otp_handler = None

        # First call with credentials
        handler1 = get_email_otp_handler(email="test@vizecep.com", app_password="test-password")

        # Second call without credentials
        handler2 = get_email_otp_handler()

        # Should be same instance
        assert handler1 is handler2

        # Cleanup
        module._email_otp_handler = None
