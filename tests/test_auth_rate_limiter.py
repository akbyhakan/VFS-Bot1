"""Tests for AuthRateLimiter in auth module."""

import time
from datetime import timezone
from unittest.mock import MagicMock, patch

import pytest

from src.core.auth import AuthRateLimiter, RedisBackend, InMemoryBackend


class TestAuthRateLimiter:
    """Tests for authentication rate limiter."""

    def test_initial_state_not_limited(self):
        """Test that initially no identifier is rate limited."""
        limiter = AuthRateLimiter(max_attempts=5, window_seconds=60)
        assert not limiter.is_rate_limited("user1")
        assert not limiter.is_rate_limited("user2")

    def test_record_attempt_increments_count(self):
        """Test that recording attempts increments the count."""
        limiter = AuthRateLimiter(max_attempts=3, window_seconds=60)

        limiter.record_attempt("user1")
        assert not limiter.is_rate_limited("user1")

        limiter.record_attempt("user1")
        assert not limiter.is_rate_limited("user1")

        limiter.record_attempt("user1")
        assert limiter.is_rate_limited("user1")

    def test_rate_limit_after_max_attempts(self):
        """Test that rate limiting activates after max attempts."""
        limiter = AuthRateLimiter(max_attempts=3, window_seconds=60)

        for _ in range(3):
            limiter.record_attempt("user1")

        assert limiter.is_rate_limited("user1")

    def test_different_identifiers_independent(self):
        """Test that different identifiers are tracked independently."""
        limiter = AuthRateLimiter(max_attempts=2, window_seconds=60)

        limiter.record_attempt("user1")
        limiter.record_attempt("user1")
        limiter.record_attempt("user2")

        assert limiter.is_rate_limited("user1")
        assert not limiter.is_rate_limited("user2")

    def test_window_expiration(self):
        """Test that attempts expire after the time window."""
        limiter = AuthRateLimiter(max_attempts=2, window_seconds=1)

        limiter.record_attempt("user1")
        limiter.record_attempt("user1")

        assert limiter.is_rate_limited("user1")

        # Wait for window to expire
        time.sleep(1.1)

        # Should no longer be rate limited
        assert not limiter.is_rate_limited("user1")

    def test_clear_attempts(self):
        """Test clearing attempts for an identifier."""
        limiter = AuthRateLimiter(max_attempts=2, window_seconds=60)

        limiter.record_attempt("user1")
        limiter.record_attempt("user1")

        assert limiter.is_rate_limited("user1")

        limiter.clear_attempts("user1")

        assert not limiter.is_rate_limited("user1")

    def test_clear_nonexistent_identifier(self):
        """Test clearing attempts for non-existent identifier doesn't error."""
        limiter = AuthRateLimiter(max_attempts=2, window_seconds=60)

        # Should not raise an error
        limiter.clear_attempts("nonexistent")
        assert not limiter.is_rate_limited("nonexistent")

    def test_thread_safety(self):
        """Test that rate limiter is thread-safe."""
        import threading

        limiter = AuthRateLimiter(max_attempts=100, window_seconds=60)

        def record_attempts():
            for _ in range(50):
                limiter.record_attempt("user1")

        threads = [threading.Thread(target=record_attempts) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Both threads recorded 50 attempts each = 100 total
        assert limiter.is_rate_limited("user1")

    def test_custom_configuration(self):
        """Test custom max_attempts and window_seconds."""
        limiter = AuthRateLimiter(max_attempts=10, window_seconds=30)

        assert limiter.max_attempts == 10
        assert limiter.window_seconds == 30

        # Record 9 attempts - should not be limited
        for _ in range(9):
            limiter.record_attempt("user1")
        assert not limiter.is_rate_limited("user1")

        # 10th attempt should trigger limit
        limiter.record_attempt("user1")
        assert limiter.is_rate_limited("user1")

    def test_memory_cleanup_after_expiration(self):
        """Test that empty attempt lists are cleaned up to prevent memory leak."""
        limiter = AuthRateLimiter(max_attempts=3, window_seconds=1)

        # Record attempts for multiple users
        limiter.record_attempt("user1")
        limiter.record_attempt("user2")
        limiter.record_attempt("user3")

        # Check that attempts are recorded (access backend's internal state)
        if hasattr(limiter._backend, '_attempts'):
            assert len(limiter._backend._attempts) == 3

        # Wait for window to expire
        time.sleep(1.1)

        # Check rate limit status which should trigger cleanup
        limiter.is_rate_limited("user1")
        limiter.is_rate_limited("user2")
        limiter.is_rate_limited("user3")

        # After cleanup, empty lists should be removed from memory
        if hasattr(limiter._backend, '_attempts'):
            assert len(limiter._backend._attempts) == 0

    def test_timezone_aware_datetime(self):
        """Test that rate limiter uses timezone-aware datetime."""
        limiter = AuthRateLimiter(max_attempts=3, window_seconds=60)

        # Record an attempt
        limiter.record_attempt("user1")

        # For in-memory backend, check stored timestamp
        if hasattr(limiter._backend, '_attempts'):
            assert len(limiter._backend._attempts["user1"]) == 1
            stored_time = limiter._backend._attempts["user1"][0]
            # Timezone-aware datetime should have tzinfo
            assert stored_time.tzinfo is not None
            assert stored_time.tzinfo == timezone.utc

    def test_is_distributed_false_for_in_memory(self):
        """Test that is_distributed returns False when using InMemoryBackend."""
        limiter = AuthRateLimiter(max_attempts=5, window_seconds=60)
        # Without REDIS_URL, should use InMemoryBackend
        assert limiter.is_distributed is False

    def test_backend_auto_detection_fallback(self):
        """Test that backend gracefully falls back to InMemoryBackend on Redis failure."""
        import os
        from unittest.mock import patch

        # Mock REDIS_URL to an invalid URL
        with patch.dict(os.environ, {"REDIS_URL": "redis://invalid-host:9999/0"}):
            limiter = AuthRateLimiter(max_attempts=5, window_seconds=60)
            # Should fall back to InMemoryBackend without raising
            assert limiter.is_distributed is False
            # Should still work
            assert not limiter.is_rate_limited("test")

    def test_cleanup_stale_entries_through_backend(self):
        """Test that cleanup_stale_entries works correctly through the backend."""
        limiter = AuthRateLimiter(max_attempts=5, window_seconds=1)

        # Record attempts for multiple users
        limiter.record_attempt("user1")
        limiter.record_attempt("user2")
        limiter.record_attempt("user3")

        # Wait for entries to become stale
        time.sleep(1.1)

        # Cleanup should remove all stale entries
        cleaned = limiter.cleanup_stale_entries()
        assert cleaned == 3


class TestCheckAndRecordAttempt:
    """Tests for the new check_and_record_attempt method."""

    def test_check_and_record_attempt_basic(self):
        """Test that check_and_record_attempt returns False until max_attempts, then True."""
        limiter = AuthRateLimiter(max_attempts=3, window_seconds=60)
        
        # First 3 attempts should succeed (return False = not limited)
        assert not limiter.check_and_record_attempt("user1")  # 1st attempt
        assert not limiter.check_and_record_attempt("user1")  # 2nd attempt
        assert not limiter.check_and_record_attempt("user1")  # 3rd attempt
        
        # 4th attempt should be rate limited (return True = limited)
        assert limiter.check_and_record_attempt("user1")
        
        # Further attempts should also be limited
        assert limiter.check_and_record_attempt("user1")

    def test_check_and_record_attempt_does_not_record_when_limited(self):
        """Verify that once limited, additional calls don't add more entries."""
        limiter = AuthRateLimiter(max_attempts=2, window_seconds=60)
        
        # First 2 attempts succeed
        assert not limiter.check_and_record_attempt("user1")
        assert not limiter.check_and_record_attempt("user1")
        
        # Now we're at the limit
        assert limiter.check_and_record_attempt("user1")
        
        # Verify we're still at the limit (no new entries were added)
        # Clear and check that only 2 attempts were recorded
        if hasattr(limiter._backend, '_attempts'):
            # For in-memory backend, we can verify directly
            assert len(limiter._backend._attempts.get("user1", [])) == 2

    def test_check_and_record_attempt_window_expiration(self):
        """Verify attempts expire correctly with check_and_record_attempt."""
        limiter = AuthRateLimiter(max_attempts=2, window_seconds=1)
        
        # Record 2 attempts - should hit the limit
        assert not limiter.check_and_record_attempt("user1")
        assert not limiter.check_and_record_attempt("user1")
        
        # Should be rate limited now
        assert limiter.check_and_record_attempt("user1")
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Should no longer be rate limited
        assert not limiter.check_and_record_attempt("user1")

    def test_check_and_record_attempt_clear_attempts(self):
        """Verify clear_attempts resets the state for check_and_record_attempt."""
        limiter = AuthRateLimiter(max_attempts=2, window_seconds=60)
        
        # Hit the limit
        assert not limiter.check_and_record_attempt("user1")
        assert not limiter.check_and_record_attempt("user1")
        assert limiter.check_and_record_attempt("user1")
        
        # Clear attempts
        limiter.clear_attempts("user1")
        
        # Should be able to make attempts again
        assert not limiter.check_and_record_attempt("user1")

    def test_check_and_record_attempt_thread_safety(self):
        """Multi-threaded test to verify atomicity of check_and_record_attempt."""
        import threading
        
        limiter = AuthRateLimiter(max_attempts=50, window_seconds=60)
        successful_attempts = []
        failed_attempts = []
        lock = threading.Lock()
        
        def make_attempts():
            for _ in range(30):
                is_limited = limiter.check_and_record_attempt("user1")
                with lock:
                    if is_limited:
                        failed_attempts.append(1)
                    else:
                        successful_attempts.append(1)
        
        # Run 2 threads, each trying 30 attempts = 60 total attempts
        threads = [threading.Thread(target=make_attempts) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have exactly 50 successful attempts (max_attempts)
        # and 10 failed attempts (60 - 50)
        assert len(successful_attempts) == 50
        assert len(failed_attempts) == 10

    def test_check_and_record_attempt_different_identifiers(self):
        """Test that different identifiers are tracked independently."""
        limiter = AuthRateLimiter(max_attempts=2, window_seconds=60)
        
        # user1 hits the limit
        assert not limiter.check_and_record_attempt("user1")
        assert not limiter.check_and_record_attempt("user1")
        assert limiter.check_and_record_attempt("user1")
        
        # user2 should still be able to make attempts
        assert not limiter.check_and_record_attempt("user2")
        assert not limiter.check_and_record_attempt("user2")
        assert limiter.check_and_record_attempt("user2")

    def test_backwards_compatibility(self):
        """Ensure existing is_rate_limited and record_attempt still work."""
        limiter = AuthRateLimiter(max_attempts=3, window_seconds=60)
        
        # Old way should still work
        assert not limiter.is_rate_limited("user1")
        limiter.record_attempt("user1")
        limiter.record_attempt("user1")
        limiter.record_attempt("user1")
        assert limiter.is_rate_limited("user1")
        
        # Mix old and new methods
        limiter2 = AuthRateLimiter(max_attempts=2, window_seconds=60)
        limiter2.record_attempt("user2")
        assert not limiter2.check_and_record_attempt("user2")  # Should work
        assert limiter2.check_and_record_attempt("user2")  # Now limited

    def test_redis_backend_check_and_record_attempt_atomicity(self):
        """Test that RedisBackend's check_and_record_attempt is atomic using Lua script."""
        # Create a mock Redis client
        mock_redis = MagicMock()
        
        # Mock the Lua script registration and execution
        mock_script = MagicMock()
        mock_redis.register_script.return_value = mock_script
        
        # Simulate script behavior: first 3 calls return 0 (allowed), then 1 (blocked)
        mock_script.side_effect = [0, 0, 0, 1, 1]
        
        # Create RedisBackend with mocked client
        backend = RedisBackend(mock_redis)
        limiter = AuthRateLimiter(max_attempts=3, window_seconds=60, backend=backend)
        
        # First 3 attempts should succeed
        assert not limiter.check_and_record_attempt("user1")
        assert not limiter.check_and_record_attempt("user1")
        assert not limiter.check_and_record_attempt("user1")
        
        # 4th attempt should be blocked
        assert limiter.check_and_record_attempt("user1")
        
        # Verify the Lua script was called (not separate is_rate_limited + record_attempt)
        assert mock_script.call_count == 4
        
        # Verify each call had the expected structure (keys=[key], args=[max, window, time, uuid])
        for call in mock_script.call_args_list:
            args, kwargs = call
            assert 'keys' in kwargs
            assert 'args' in kwargs
            assert len(kwargs['keys']) == 1
            assert len(kwargs['args']) == 4
            assert kwargs['args'][0] == 3  # max_attempts
            assert kwargs['args'][1] == 60  # window_seconds
