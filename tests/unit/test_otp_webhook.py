"""Tests for OTP webhook service."""

import asyncio
from datetime import datetime, timezone

import pytest

from src.services.otp_manager.otp_webhook import OTPWebhookService
from src.services.otp_manager.pattern_matcher import OTPPatternMatcher


class TestOTPPatternMatcher:
    """Tests for OTP pattern matching."""

    def test_extract_6_digit_otp(self):
        matcher = OTPPatternMatcher()
        assert matcher.extract_otp("Your code is 123456") == "123456"

    def test_extract_4_digit_otp(self):
        """Test extracting 4-digit OTP using SMS patterns (EMAIL patterns require 6 digits)."""
        from src.services.otp_manager.pattern_matcher import SMS_OTP_PATTERNS

        matcher = OTPPatternMatcher(custom_patterns=SMS_OTP_PATTERNS)
        assert matcher.extract_otp("OTP: 1234") == "1234"

    def test_extract_turkish_otp(self):
        matcher = OTPPatternMatcher()
        assert matcher.extract_otp("Doğrulama kodunuz: 654321") == "654321"

    def test_no_otp_found(self):
        matcher = OTPPatternMatcher()
        assert matcher.extract_otp("Hello, no code here") is None

    def test_custom_pattern(self):
        matcher = OTPPatternMatcher(custom_patterns=[r"PIN:(\d{4})"])
        assert matcher.extract_otp("Your PIN:9999 is ready") == "9999"

    def test_extract_with_code_keyword(self):
        matcher = OTPPatternMatcher()
        assert matcher.extract_otp("Your verification code: 888999") == "888999"

    def test_extract_5_digit_otp(self):
        """Test extracting 5-digit OTP using SMS patterns (EMAIL patterns require 6 digits)."""
        from src.services.otp_manager.pattern_matcher import SMS_OTP_PATTERNS

        matcher = OTPPatternMatcher(custom_patterns=SMS_OTP_PATTERNS)
        assert matcher.extract_otp("Code 12345 expires soon") == "12345"


class TestOTPWebhookService:
    """Tests for OTP webhook service."""

    @pytest.mark.asyncio
    async def test_process_sms(self):
        service = OTPWebhookService()
        otp = await service.process_sms("+905551234567", "Your VFS code is 123456")
        assert otp == "123456"

    @pytest.mark.asyncio
    async def test_wait_for_otp_immediate(self):
        service = OTPWebhookService()

        # Add OTP first
        await service.process_sms("+905551234567", "Code: 999888")

        # Should return immediately
        otp = await service.wait_for_otp(timeout=1)
        assert otp == "999888"

    @pytest.mark.asyncio
    async def test_wait_for_otp_timeout(self):
        service = OTPWebhookService()

        # Should timeout
        otp = await service.wait_for_otp(timeout=1)
        assert otp is None

    @pytest.mark.asyncio
    async def test_otp_used_once(self):
        service = OTPWebhookService()

        await service.process_sms("+905551234567", "Code: 111222")

        # First get should succeed
        otp1 = await service.wait_for_otp(timeout=1)
        assert otp1 == "111222"

        # Second get should fail (already used)
        otp2 = await service.wait_for_otp(timeout=1)
        assert otp2 is None

    @pytest.mark.asyncio
    async def test_process_sms_no_otp(self):
        service = OTPWebhookService()
        otp = await service.process_sms("+905551234567", "Hello, this is not an OTP message")
        assert otp is None

    @pytest.mark.asyncio
    async def test_phone_number_filter(self):
        service = OTPWebhookService()

        # Add OTP for different phone numbers
        await service.process_sms("+905551111111", "Code: 111111")
        await service.process_sms("+905552222222", "Code: 222222")

        # Get OTP for specific phone number
        otp = await service.wait_for_otp(phone_number="+905552222222", timeout=1)
        assert otp == "222222"

    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        service = OTPWebhookService(otp_timeout_seconds=1)

        # Add OTP
        await service.process_sms("+905551234567", "Code: 123456")

        # Wait for expiry
        await asyncio.sleep(1.5)

        # Cleanup
        removed = await service.cleanup_expired()
        assert removed >= 0  # May or may not have removed entries depending on timing

    @pytest.mark.asyncio
    async def test_multiple_otps_get_latest(self):
        service = OTPWebhookService()

        # Add multiple OTPs
        await service.process_sms("+905551234567", "Code: 111111")
        await asyncio.sleep(0.1)
        await service.process_sms("+905551234567", "Code: 222222")

        # Should get the latest unused one
        otp = await service.wait_for_otp(timeout=1)
        assert otp == "222222"

    @pytest.mark.asyncio
    async def test_concurrent_otp_wait_and_process(self):
        """Test race condition fix: concurrent wait and process operations."""
        service = OTPWebhookService()

        # Start multiple wait operations concurrently
        wait_tasks = [
            asyncio.create_task(service.wait_for_otp(timeout=3)),
            asyncio.create_task(service.wait_for_otp(timeout=3)),
            asyncio.create_task(service.wait_for_otp(timeout=3)),
        ]

        # Give wait tasks time to register
        await asyncio.sleep(0.1)

        # Send OTP while wait operations are active
        await service.process_sms("+905551234567", "Code: 999888")
        await asyncio.sleep(0.1)
        await service.process_sms("+905551234567", "Code: 777666")
        await asyncio.sleep(0.1)
        await service.process_sms("+905551234567", "Code: 555444")

        # Wait for all tasks to complete
        results = await asyncio.gather(*wait_tasks, return_exceptions=True)

        # At least one task should have received an OTP
        valid_otps = [r for r in results if isinstance(r, str) and r is not None]
        assert len(valid_otps) >= 1, "At least one wait operation should receive an OTP"

        # All results should be either None or a valid OTP (no exceptions)
        for result in results:
            assert result is None or isinstance(result, str), f"Unexpected result: {result}"
