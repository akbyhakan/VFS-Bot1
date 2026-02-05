"""Tests for AuthRateLimiter in auth module."""

import time
from datetime import timezone

import pytest

from src.core.auth import AuthRateLimiter


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

        # Check that attempts are recorded
        assert len(limiter._attempts) == 3

        # Wait for window to expire
        time.sleep(1.1)

        # Check rate limit status which should trigger cleanup
        limiter.is_rate_limited("user1")
        limiter.is_rate_limited("user2")
        limiter.is_rate_limited("user3")

        # After cleanup, empty lists should be removed from memory
        assert len(limiter._attempts) == 0

    def test_timezone_aware_datetime(self):
        """Test that rate limiter uses timezone-aware datetime."""
        limiter = AuthRateLimiter(max_attempts=3, window_seconds=60)

        # Record an attempt
        limiter.record_attempt("user1")

        # Check that the stored timestamp is timezone-aware
        assert len(limiter._attempts["user1"]) == 1
        stored_time = limiter._attempts["user1"][0]
        # Timezone-aware datetime should have tzinfo
        assert stored_time.tzinfo is not None
        assert stored_time.tzinfo == timezone.utc
