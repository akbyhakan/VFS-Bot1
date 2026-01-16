"""Tests for security improvements."""

import pytest
import asyncio
import time
from src.utils.decorators import log_errors, retry_async, timed_async
from src.utils.audit_logger import AuditLogger, AuditAction
from src.utils.webhook_utils import verify_webhook_signature, generate_webhook_signature
from src.utils.security.adaptive_rate_limiter import AdaptiveRateLimiter


class TestAdaptiveRateLimiter:
    @pytest.mark.asyncio
    async def test_initial_delay(self):
        """Test that limiter starts with base delay."""
        limiter = AdaptiveRateLimiter(base_delay=1.0)
        assert limiter.current_delay == 1.0
    
    @pytest.mark.asyncio
    async def test_backoff_on_failure(self):
        """Test exponential backoff on failures."""
        limiter = AdaptiveRateLimiter(base_delay=1.0, backoff_factor=2.0)
        limiter.on_failure()
        assert limiter.current_delay == 2.0
        limiter.on_failure()
        assert limiter.current_delay == 4.0
    
    @pytest.mark.asyncio
    async def test_recovery_on_success(self):
        """Test gradual recovery on success."""
        limiter = AdaptiveRateLimiter(base_delay=1.0)
        limiter._current_delay = 10.0
        limiter.on_success()
        assert limiter.current_delay < 10.0
    
    @pytest.mark.asyncio
    async def test_max_delay_limit(self):
        """Test that delay doesn't exceed max_delay."""
        limiter = AdaptiveRateLimiter(base_delay=1.0, max_delay=5.0, backoff_factor=2.0)
        for _ in range(10):
            limiter.on_failure()
        assert limiter.current_delay <= 5.0
    
    @pytest.mark.asyncio
    async def test_reset(self):
        """Test reset functionality."""
        limiter = AdaptiveRateLimiter(base_delay=1.0)
        limiter.on_failure()
        limiter.on_failure()
        limiter.reset()
        assert limiter.current_delay == 1.0
        assert limiter._consecutive_failures == 0
    
    @pytest.mark.asyncio
    async def test_is_backed_off(self):
        """Test backed off detection."""
        limiter = AdaptiveRateLimiter(base_delay=1.0)
        assert not limiter.is_backed_off
        limiter._current_delay = 2.0
        assert limiter.is_backed_off


class TestWebhookSignature:
    def test_generate_and_verify(self):
        """Test signature generation and verification."""
        payload = '{"test": "data"}'
        secret = "test-secret-key"
        
        signature = generate_webhook_signature(payload, secret)
        assert verify_webhook_signature(
            payload.encode(),
            signature,
            secret
        )
    
    def test_invalid_signature(self):
        """Test rejection of invalid signature."""
        payload = '{"test": "data"}'
        secret = "test-secret-key"
        wrong_secret = "wrong-secret"
        
        signature = generate_webhook_signature(payload, secret)
        assert not verify_webhook_signature(
            payload.encode(),
            signature,
            wrong_secret
        )
    
    def test_modified_payload(self):
        """Test rejection of modified payload."""
        payload = '{"test": "data"}'
        modified_payload = '{"test": "modified"}'
        secret = "test-secret-key"
        
        signature = generate_webhook_signature(payload, secret)
        assert not verify_webhook_signature(
            modified_payload.encode(),
            signature,
            secret
        )
    
    def test_invalid_signature_format(self):
        """Test rejection of invalid signature format."""
        payload = '{"test": "data"}'
        secret = "test-secret-key"
        
        assert not verify_webhook_signature(
            payload.encode(),
            "invalid-format",
            secret
        )
    
    def test_expired_timestamp(self):
        """Test rejection of old timestamps."""
        payload = '{"test": "data"}'
        secret = "test-secret-key"
        
        # Create signature with old timestamp using utility function
        from src.utils.webhook_utils import generate_webhook_signature
        
        # Temporarily mock time to create old signature
        old_time = time.time() - 400  # 400 seconds old
        original_time = time.time
        time.time = lambda: old_time
        
        try:
            old_signature = generate_webhook_signature(payload, secret)
        finally:
            time.time = original_time
        
        assert not verify_webhook_signature(
            payload.encode(),
            old_signature,
            secret,
            timestamp_tolerance=300  # 5 minutes
        )


class TestAuditLogger:
    @pytest.mark.asyncio
    async def test_sanitize_sensitive_data(self):
        """Test that sensitive data is sanitized."""
        logger = AuditLogger()
        
        data = {
            "username": "test",
            "password": "secret123",
            "api_key": "abc123def456"
        }
        
        sanitized = logger._sanitize(data)
        
        assert sanitized["username"] == "test"
        assert "***" in sanitized["password"]
        assert "***" in sanitized["api_key"]
    
    @pytest.mark.asyncio
    async def test_sanitize_nested_data(self):
        """Test sanitization of nested dictionaries."""
        logger = AuditLogger()
        
        data = {
            "user": {
                "username": "test",
                "password": "secret123"
            }
        }
        
        sanitized = logger._sanitize(data)
        
        assert sanitized["user"]["username"] == "test"
        assert "***" in sanitized["user"]["password"]
    
    @pytest.mark.asyncio
    async def test_sanitize_short_sensitive_data(self):
        """Test sanitization of short sensitive values."""
        logger = AuditLogger()
        
        data = {
            "cvv": "123"
        }
        
        sanitized = logger._sanitize(data)
        assert sanitized["cvv"] == "***REDACTED***"
    
    @pytest.mark.asyncio
    async def test_buffer_limit(self):
        """Test that buffer respects size limit."""
        logger = AuditLogger()
        logger._buffer_size = 5
        
        # Add more entries than buffer size
        for i in range(10):
            await logger.log(
                AuditAction.LOGIN_SUCCESS,
                user_id=i,
                username=f"user{i}"
            )
        
        assert len(logger._buffer) <= 5


class TestDecorators:
    @pytest.mark.asyncio
    async def test_retry_decorator_success(self):
        """Test retry decorator with eventual success."""
        call_count = 0
        
        @retry_async(max_retries=3, delay=0.01, exceptions=(ValueError,))
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = await flaky_func()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_decorator_failure(self):
        """Test retry decorator with permanent failure."""
        call_count = 0
        
        @retry_async(max_retries=2, delay=0.01, exceptions=(ValueError,))
        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent error")
        
        with pytest.raises(ValueError):
            await failing_func()
        
        assert call_count == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_log_errors_decorator_reraise(self):
        """Test log_errors decorator with reraise."""
        @log_errors(reraise=True)
        async def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await failing_func()
    
    @pytest.mark.asyncio
    async def test_log_errors_decorator_default_return(self):
        """Test log_errors decorator with default return."""
        @log_errors(reraise=False, default_return="default")
        async def failing_func():
            raise ValueError("Test error")
        
        result = await failing_func()
        assert result == "default"
    
    @pytest.mark.asyncio
    async def test_timed_async_decorator(self):
        """Test timed_async decorator."""
        @timed_async
        async def slow_func():
            await asyncio.sleep(0.01)
            return "done"
        
        result = await slow_func()
        assert result == "done"
    
    @pytest.mark.asyncio
    async def test_timed_async_decorator_with_error(self):
        """Test timed_async decorator with error."""
        @timed_async
        async def failing_func():
            await asyncio.sleep(0.01)
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await failing_func()
    
    @pytest.mark.asyncio
    async def test_retry_with_specific_exceptions(self):
        """Test retry decorator with specific exception types."""
        call_count = 0
        
        @retry_async(max_retries=2, delay=0.01, exceptions=(ValueError,))
        async def func_with_value_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"
        
        result = await func_with_value_error()
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_ignores_other_exceptions(self):
        """Test that retry decorator doesn't catch non-specified exceptions."""
        call_count = 0
        
        @retry_async(max_retries=3, delay=0.01, exceptions=(ValueError,))
        async def func_with_runtime_error():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Different error")
        
        with pytest.raises(RuntimeError):
            await func_with_runtime_error()
        
        # Should fail immediately without retries
        assert call_count == 1
