"""Integration tests for Redis-based rate limiting with Lua script atomicity."""

import asyncio
import logging
import os
import time

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.integration
class TestRedisRateLimiting:
    """Integration tests for Redis rate limiting functionality."""

    @pytest.fixture(autouse=True)
    def check_redis(self, redis_available):
        """Skip tests if Redis is not available."""
        if not redis_available:
            pytest.skip("Redis is not available for testing")

    @pytest.mark.asyncio
    async def test_atomic_rate_limiting(self, redis_available):
        """
        Test atomic rate limiting: 5 attempts OK → 6th attempt blocked.
        
        This validates:
        - Lua script atomically checks and records attempts
        - Rate limit threshold is enforced correctly
        - No race conditions in check-and-record operation
        """
        from src.core.auth import AuthRateLimiter
        
        # Get Redis URL from environment
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL not set")
        
        # Create rate limiter with Redis backend
        import redis
        redis_client = redis.from_url(redis_url, decode_responses=True)
        
        try:
            limiter = AuthRateLimiter(redis_client)
            
            # Use a unique identifier for this test
            test_identifier = f"test_atomic_{int(time.time())}"
            
            # Clear any previous attempts
            limiter.clear_attempts(test_identifier)
            
            # Configure: 5 max attempts, 60 second window
            max_attempts = 5
            window_seconds = 60
            
            # Step 1: First 5 attempts should succeed
            for i in range(max_attempts):
                is_limited = limiter.check_and_record_attempt(
                    identifier=test_identifier,
                    max_attempts=max_attempts,
                    window_seconds=window_seconds
                )
                assert is_limited is False, f"Attempt {i+1} should not be rate limited"
            
            # Step 2: 6th attempt should be blocked
            is_limited_6th = limiter.check_and_record_attempt(
                identifier=test_identifier,
                max_attempts=max_attempts,
                window_seconds=window_seconds
            )
            assert is_limited_6th is True, "6th attempt should be rate limited"
            
            # Step 3: 7th attempt should also be blocked
            is_limited_7th = limiter.check_and_record_attempt(
                identifier=test_identifier,
                max_attempts=max_attempts,
                window_seconds=window_seconds
            )
            assert is_limited_7th is True, "7th attempt should be rate limited"
            
            # Cleanup
            limiter.clear_attempts(test_identifier)
            
        finally:
            redis_client.close()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_rate_limit_window_expiry(self, redis_available):
        """
        Test rate limit window expiry: limits reset after window expires.
        
        This validates:
        - Rate limit window expiration works
        - Attempts are cleared after window
        - New attempts are allowed after expiry
        """
        from src.core.auth import AuthRateLimiter
        
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL not set")
        
        import redis
        redis_client = redis.from_url(redis_url, decode_responses=True)
        
        try:
            limiter = AuthRateLimiter(redis_client)
            
            test_identifier = f"test_expiry_{int(time.time())}"
            limiter.clear_attempts(test_identifier)
            
            # Use a short window for testing (5 seconds)
            max_attempts = 3
            window_seconds = 5
            
            # Step 1: Use up all attempts
            for i in range(max_attempts):
                is_limited = limiter.check_and_record_attempt(
                    identifier=test_identifier,
                    max_attempts=max_attempts,
                    window_seconds=window_seconds
                )
                assert is_limited is False, f"Initial attempt {i+1} should succeed"
            
            # Step 2: 4th attempt should be blocked
            is_limited_4th = limiter.check_and_record_attempt(
                identifier=test_identifier,
                max_attempts=max_attempts,
                window_seconds=window_seconds
            )
            assert is_limited_4th is True, "4th attempt should be blocked"
            
            # Step 3: Wait for window to expire
            logger.info(f"Waiting {window_seconds + 1} seconds for rate limit window to expire...")
            await asyncio.sleep(window_seconds + 1)
            
            # Step 4: After expiry, attempts should be allowed again
            is_limited_after = limiter.check_and_record_attempt(
                identifier=test_identifier,
                max_attempts=max_attempts,
                window_seconds=window_seconds
            )
            assert is_limited_after is False, "Attempt after window expiry should succeed"
            
            # Cleanup
            limiter.clear_attempts(test_identifier)
            
        finally:
            redis_client.close()

    @pytest.mark.asyncio
    async def test_independent_identifiers(self, redis_available):
        """
        Test independent rate limits for different identifiers.
        
        This validates:
        - Different users have separate rate limits
        - One user hitting limit doesn't affect others
        - Identifiers are properly isolated
        """
        from src.core.auth import AuthRateLimiter
        
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL not set")
        
        import redis
        redis_client = redis.from_url(redis_url, decode_responses=True)
        
        try:
            limiter = AuthRateLimiter(redis_client)
            
            timestamp = int(time.time())
            user1 = f"test_user1_{timestamp}"
            user2 = f"test_user2_{timestamp}"
            
            # Clear both users
            limiter.clear_attempts(user1)
            limiter.clear_attempts(user2)
            
            max_attempts = 3
            window_seconds = 60
            
            # Step 1: User 1 uses all attempts
            for i in range(max_attempts):
                is_limited = limiter.check_and_record_attempt(
                    identifier=user1,
                    max_attempts=max_attempts,
                    window_seconds=window_seconds
                )
                assert is_limited is False, f"User1 attempt {i+1} should succeed"
            
            # Step 2: User 1 is now rate limited
            is_limited_user1 = limiter.check_and_record_attempt(
                identifier=user1,
                max_attempts=max_attempts,
                window_seconds=window_seconds
            )
            assert is_limited_user1 is True, "User1 should be rate limited"
            
            # Step 3: User 2 should still have full quota
            for i in range(max_attempts):
                is_limited = limiter.check_and_record_attempt(
                    identifier=user2,
                    max_attempts=max_attempts,
                    window_seconds=window_seconds
                )
                assert is_limited is False, f"User2 attempt {i+1} should succeed (independent limit)"
            
            # Step 4: Now User 2 should also be limited
            is_limited_user2 = limiter.check_and_record_attempt(
                identifier=user2,
                max_attempts=max_attempts,
                window_seconds=window_seconds
            )
            assert is_limited_user2 is True, "User2 should now be rate limited"
            
            # Cleanup
            limiter.clear_attempts(user1)
            limiter.clear_attempts(user2)
            
        finally:
            redis_client.close()

    @pytest.mark.asyncio
    async def test_concurrent_attempts_no_race_condition(self, redis_available):
        """
        Test concurrent attempts to verify Lua script prevents race conditions.
        
        This validates:
        - Multiple concurrent attempts are handled atomically
        - No race conditions in check-and-record
        - Total attempts never exceed limit
        """
        from src.core.auth import AuthRateLimiter
        
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL not set")
        
        import redis
        redis_client = redis.from_url(redis_url, decode_responses=True)
        
        try:
            limiter = AuthRateLimiter(redis_client)
            
            test_identifier = f"test_concurrent_{int(time.time())}"
            limiter.clear_attempts(test_identifier)
            
            max_attempts = 5
            window_seconds = 60
            
            async def make_attempt():
                """Make a single rate limit check attempt."""
                # Note: AuthRateLimiter is sync, but we can still test concurrency
                return limiter.check_and_record_attempt(
                    identifier=test_identifier,
                    max_attempts=max_attempts,
                    window_seconds=window_seconds
                )
            
            # Create 10 concurrent tasks
            tasks = [asyncio.create_task(asyncio.to_thread(make_attempt)) for _ in range(10)]
            results = await asyncio.gather(*tasks)
            
            # Count how many were allowed vs blocked
            allowed_count = sum(1 for r in results if r is False)
            blocked_count = sum(1 for r in results if r is True)
            
            # Exactly max_attempts should be allowed, rest blocked
            assert allowed_count == max_attempts, f"Expected {max_attempts} allowed, got {allowed_count}"
            assert blocked_count == 10 - max_attempts, f"Expected {10 - max_attempts} blocked, got {blocked_count}"
            
            # Cleanup
            limiter.clear_attempts(test_identifier)
            
        finally:
            redis_client.close()
