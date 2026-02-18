"""Load tests for concurrent operations."""

import asyncio
import os
import time
from pathlib import Path

import pytest

from src.constants import Database as DbConstants
from src.core.rate_limiting import RateLimiter, reset_rate_limiter
from src.models.database import Database
from src.repositories import UserRepository


class TestConcurrentLoad:
    """Load tests for system under heavy load."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_slot_checks(self):
        """Test 50 concurrent slot checks."""
        check_count = 50
        results = []

        async def simulate_slot_check(check_id: int) -> dict:
            """Simulate a slot check operation."""
            await asyncio.sleep(0.1)  # Simulate network delay
            return {
                "check_id": check_id,
                "timestamp": time.time(),
                "slots_found": check_id % 3 == 0,  # Every 3rd check finds a slot
            }

        # Start all checks concurrently
        start_time = time.time()
        tasks = [simulate_slot_check(i) for i in range(check_count)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        # Verify all checks completed
        assert len(results) == check_count

        # Check execution time (should be close to 0.1s, not 5s if sequential)
        execution_time = end_time - start_time
        assert execution_time < 1.0, f"Should complete in under 1s, took {execution_time:.2f}s"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_rate_limiter_under_load(self):
        """Test rate limiter behavior under heavy load."""
        # Reset rate limiter for clean test
        reset_rate_limiter()

        # Create rate limiter with small limits for testing
        limiter = RateLimiter(max_requests=10, time_window=1)

        request_count = 25
        start_time = time.time()
        completed = []

        async def make_request(req_id: int) -> dict:
            """Make a rate-limited request."""
            await limiter.acquire()
            completed.append({"id": req_id, "timestamp": time.time()})
            return {"id": req_id}

        # Make 25 requests (10 req/s limit means ~3 seconds total)
        tasks = [make_request(i) for i in range(request_count)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        # Verify all requests completed
        assert len(results) == request_count
        assert len(completed) == request_count

        # Verify rate limiting worked (should take at least 2 seconds)
        execution_time = end_time - start_time
        assert execution_time >= 2.0, f"Should be rate-limited, took {execution_time:.2f}s"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_database_concurrent_writes(self):
        """Test database under concurrent write load."""
        database_url = os.getenv("TEST_DATABASE_URL", DbConstants.TEST_URL)
        db = Database(database_url=database_url, pool_size=10)
        await db.connect()

        try:
            write_count = 50
            start_time = time.time()

            user_repo = UserRepository(db)

            async def write_user(user_id: int) -> int:
                """Write a user to database."""
                return await user_repo.create(
                    {
                        "email": f"load{user_id}@test.com",
                        "password": f"password{user_id}",
                        "center_name": "Istanbul",
                        "visa_category": "Schengen",
                        "visa_subcategory": "Tourism",
                    }
                )

            # Perform concurrent writes
            tasks = [write_user(i) for i in range(write_count)]
            user_ids = await asyncio.gather(*tasks)
            end_time = time.time()

            # Verify all writes succeeded
            assert len(user_ids) == write_count
            assert len(set(user_ids)) == write_count  # All unique IDs

            # Check execution time
            execution_time = end_time - start_time
            print(f"Concurrent writes: {write_count} in {execution_time:.2f}s")

        finally:
            await db.close()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_database_concurrent_reads(self):
        """Test database under concurrent read load."""
        database_url = os.getenv("TEST_DATABASE_URL", DbConstants.TEST_URL)
        db = Database(database_url=database_url, pool_size=10)
        await db.connect()

        try:
            # Create some test data
            user_repo = UserRepository(db)
            for i in range(10):
                await user_repo.create(
                    {
                        "email": f"read{i}@test.com",
                        "password": f"password{i}",
                        "center_name": "Istanbul",
                        "visa_category": "Schengen",
                        "visa_subcategory": "Tourism",
                    }
                )

            # Perform many concurrent reads
            read_count = 100
            start_time = time.time()

            user_repo = UserRepository(db)

            async def read_users() -> list:
                """Read all users."""
                return await user_repo.get_all_active()

            tasks = [read_users() for _ in range(read_count)]
            results = await asyncio.gather(*tasks)
            end_time = time.time()

            # Verify all reads succeeded
            assert len(results) == read_count
            for result in results:
                assert len(result) == 10  # All 10 users

            execution_time = end_time - start_time
            print(f"Concurrent reads: {read_count} in {execution_time:.2f}s")

        finally:
            await db.close()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_mixed_read_write_load(self):
        """Test database with mixed read and write operations."""
        database_url = os.getenv("TEST_DATABASE_URL", DbConstants.TEST_URL)
        db = Database(database_url=database_url, pool_size=10)
        await db.connect()

        try:
            # Create initial data
            user_repo = UserRepository(db)
            for i in range(5):
                await user_repo.create(
                    {
                        "email": f"initial{i}@test.com",
                        "password": f"password{i}",
                        "center_name": "Istanbul",
                        "visa_category": "Schengen",
                        "visa_subcategory": "Tourism",
                    }
                )

            write_count = 25
            read_count = 75

            user_repo = UserRepository(db)

            async def write_user(user_id: int) -> int:
                """Write operation."""
                return await user_repo.create(
                    {
                        "email": f"mixed{user_id}@test.com",
                        "password": f"password{user_id}",
                        "center_name": "Istanbul",
                        "visa_category": "Schengen",
                        "visa_subcategory": "Tourism",
                    }
                )

            async def read_users() -> list:
                """Read operation."""
                return await user_repo.get_all_active()

            # Mix writes and reads
            tasks = []
            tasks.extend([write_user(i) for i in range(write_count)])
            tasks.extend([read_users() for _ in range(read_count)])

            # Shuffle tasks to mix reads and writes
            import random

            random.shuffle(tasks)

            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()

            # Count successes and failures
            successes = [r for r in results if not isinstance(r, Exception)]
            failures = [r for r in results if isinstance(r, Exception)]

            # All operations should succeed
            assert len(failures) == 0, f"No failures expected, got {len(failures)}"
            assert len(successes) == write_count + read_count

            execution_time = end_time - start_time
            print(f"Mixed operations: {len(successes)} in {execution_time:.2f}s")

        finally:
            await db.close()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_connection_pool_stress(self):
        """Stress test connection pool with sustained load."""
        database_url = os.getenv("TEST_DATABASE_URL", DbConstants.TEST_URL)
        db = Database(database_url=database_url, pool_size=5)  # Small pool for stress testing
        await db.connect()

        try:
            operation_count = 100

            async def perform_operation(op_id: int) -> bool:
                """Perform a database operation."""
                async with db.get_connection(timeout=10.0) as conn:
                    result = await conn.fetchval("SELECT 1")
                return True

            start_time = time.time()
            tasks = [perform_operation(i) for i in range(operation_count)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()

            # All should succeed even with small pool
            successes = [r for r in results if r is True]
            failures = [r for r in results if isinstance(r, Exception)]

            assert (
                len(successes) == operation_count
            ), f"Expected {operation_count}, got {len(successes)}"
            assert len(failures) == 0, f"No failures expected, got {failures}"

            execution_time = end_time - start_time
            ops_per_second = operation_count / execution_time
            print(
                f"Pool stress: {operation_count} ops in {execution_time:.2f}s "
                f"({ops_per_second:.1f} ops/s)"
            )

        finally:
            await db.close()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_sustained_load_over_time(self):
        """Test sustained load over a longer period."""
        database_url = os.getenv("TEST_DATABASE_URL", DbConstants.TEST_URL)
        db = Database(database_url=database_url, pool_size=10)
        await db.connect()

        try:
            duration_seconds = 5
            operations_per_second = 10
            total_operations = duration_seconds * operations_per_second

            async def continuous_operations():
                """Perform operations continuously."""
                user_repo = UserRepository(db)
                for i in range(operations_per_second):
                    await user_repo.create(
                        {
                            "email": f"sustained{time.time()}@test.com",
                            "password": "password",
                            "center_name": "Istanbul",
                            "visa_category": "Schengen",
                            "visa_subcategory": "Tourism",
                        }
                    )
                    await asyncio.sleep(1.0 / operations_per_second)

            start_time = time.time()
            tasks = [continuous_operations() for _ in range(duration_seconds)]
            await asyncio.gather(*tasks)
            end_time = time.time()

            # Verify execution time
            # Since tasks run in parallel, execution time should be ~1 second
            # (operations_per_second iterations * (1.0/operations_per_second) sleep)
            execution_time = end_time - start_time
            # Tasks run in parallel, so time should be around 1 second, not 5
            assert execution_time >= 0.5  # At least 0.5 seconds
            assert execution_time <= 2  # But not more than 2 seconds

            # Verify data was created
            user_repo = UserRepository(db)
            users = await user_repo.get_all_active()
            assert len(users) >= total_operations * 0.9  # Allow 10% variance

        finally:
            await db.close()
