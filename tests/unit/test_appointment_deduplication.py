"""Tests for appointment deduplication service."""

import asyncio
import time

import pytest

from src.services.appointment_deduplication import (
    AppointmentDeduplication,
    InMemoryDeduplicationBackend,
    get_deduplication_service,
)


@pytest.fixture
def in_memory_backend():
    """Fixture for in-memory backend."""
    return InMemoryDeduplicationBackend()


@pytest.mark.asyncio
class TestAppointmentDeduplication:
    """Test cases for AppointmentDeduplication class."""

    async def test_initialization(self, in_memory_backend):
        """Test service initialization."""
        service = AppointmentDeduplication(ttl_seconds=1800, backend=in_memory_backend)
        assert service._ttl_seconds == 1800
        assert isinstance(in_memory_backend._cache, dict)
        assert len(in_memory_backend._cache) == 0

    async def test_no_duplicate_on_first_check(self, in_memory_backend):
        """Test that first booking attempt is not marked as duplicate."""
        service = AppointmentDeduplication(ttl_seconds=3600, backend=in_memory_backend)

        is_dup = await service.is_duplicate(
            user_id=123, centre="Istanbul", category="Tourist", date="2024-03-15"
        )

        assert is_dup is False

    async def test_duplicate_detected_after_marking(self, in_memory_backend):
        """Test that duplicate is detected after marking booking."""
        service = AppointmentDeduplication(ttl_seconds=3600, backend=in_memory_backend)

        # Mark first booking
        await service.mark_booked(
            user_id=123, centre="Istanbul", category="Tourist", date="2024-03-15"
        )

        # Check for duplicate
        is_dup = await service.is_duplicate(
            user_id=123, centre="Istanbul", category="Tourist", date="2024-03-15"
        )

        assert is_dup is True

    async def test_different_user_not_duplicate(self, in_memory_backend):
        """Test that different users don't interfere."""
        service = AppointmentDeduplication(ttl_seconds=3600, backend=in_memory_backend)

        # Mark booking for user 123
        await service.mark_booked(
            user_id=123, centre="Istanbul", category="Tourist", date="2024-03-15"
        )

        # Check for user 456 - should not be duplicate
        is_dup = await service.is_duplicate(
            user_id=456, centre="Istanbul", category="Tourist", date="2024-03-15"
        )

        assert is_dup is False

    async def test_different_centre_not_duplicate(self, in_memory_backend):
        """Test that different centres don't interfere."""
        service = AppointmentDeduplication(ttl_seconds=3600, backend=in_memory_backend)

        # Mark booking for Istanbul
        await service.mark_booked(
            user_id=123, centre="Istanbul", category="Tourist", date="2024-03-15"
        )

        # Check for Ankara - should not be duplicate
        is_dup = await service.is_duplicate(
            user_id=123, centre="Ankara", category="Tourist", date="2024-03-15"
        )

        assert is_dup is False

    async def test_different_date_not_duplicate(self, in_memory_backend):
        """Test that different dates don't interfere."""
        service = AppointmentDeduplication(ttl_seconds=3600, backend=in_memory_backend)

        # Mark booking for 2024-03-15
        await service.mark_booked(
            user_id=123, centre="Istanbul", category="Tourist", date="2024-03-15"
        )

        # Check for different date - should not be duplicate
        is_dup = await service.is_duplicate(
            user_id=123, centre="Istanbul", category="Tourist", date="2024-03-16"
        )

        assert is_dup is False

    async def test_ttl_expiration(self, in_memory_backend):
        """Test that entries expire after TTL."""
        service = AppointmentDeduplication(ttl_seconds=1, backend=in_memory_backend)  # 1 second TTL

        # Mark booking
        await service.mark_booked(
            user_id=123, centre="Istanbul", category="Tourist", date="2024-03-15"
        )

        # Should be duplicate immediately
        is_dup = await service.is_duplicate(
            user_id=123, centre="Istanbul", category="Tourist", date="2024-03-15"
        )
        assert is_dup is True

        # Wait for TTL to expire
        await asyncio.sleep(1.5)

        # Should no longer be duplicate
        is_dup = await service.is_duplicate(
            user_id=123, centre="Istanbul", category="Tourist", date="2024-03-15"
        )
        assert is_dup is False

    async def test_cleanup_expired(self, in_memory_backend):
        """Test cleanup of expired entries."""
        service = AppointmentDeduplication(ttl_seconds=1, backend=in_memory_backend)  # 1 second TTL

        # Mark multiple bookings
        await service.mark_booked(
            user_id=123, centre="Istanbul", category="Tourist", date="2024-03-15"
        )
        await service.mark_booked(
            user_id=456, centre="Ankara", category="Business", date="2024-03-16"
        )

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Cleanup
        removed = await service.cleanup_expired()

        assert removed == 2

    async def test_get_stats(self, in_memory_backend):
        """Test getting cache statistics."""
        service = AppointmentDeduplication(ttl_seconds=3600, backend=in_memory_backend)

        # Mark some bookings
        await service.mark_booked(
            user_id=123, centre="Istanbul", category="Tourist", date="2024-03-15"
        )
        await service.mark_booked(
            user_id=456, centre="Ankara", category="Business", date="2024-03-16"
        )

        stats = await service.get_stats()

        assert stats["total_entries"] == 2
        assert stats["active_entries"] == 2
        assert stats["ttl_seconds"] == 3600

    async def test_clear(self, in_memory_backend):
        """Test clearing all cache entries."""
        service = AppointmentDeduplication(ttl_seconds=3600, backend=in_memory_backend)

        # Mark some bookings
        await service.mark_booked(
            user_id=123, centre="Istanbul", category="Tourist", date="2024-03-15"
        )
        await service.mark_booked(
            user_id=456, centre="Ankara", category="Business", date="2024-03-16"
        )

        # Clear
        await service.clear()

        # Check stats
        stats = await service.get_stats()
        assert stats["total_entries"] == 0

    async def test_concurrent_access(self, in_memory_backend):
        """Test thread-safe concurrent access."""
        service = AppointmentDeduplication(ttl_seconds=3600, backend=in_memory_backend)

        async def mark_and_check(user_id: int):
            await service.mark_booked(
                user_id=user_id, centre="Istanbul", category="Tourist", date="2024-03-15"
            )
            is_dup = await service.is_duplicate(
                user_id=user_id, centre="Istanbul", category="Tourist", date="2024-03-15"
            )
            assert is_dup is True

        # Run multiple concurrent operations
        await asyncio.gather(*[mark_and_check(i) for i in range(10)])

        stats = await service.get_stats()
        assert stats["total_entries"] == 10

    async def test_make_key_uniqueness(self, in_memory_backend):
        """Test that cache keys are unique for different combinations."""
        service = AppointmentDeduplication(ttl_seconds=3600, backend=in_memory_backend)

        key1 = service._make_key(123, "Istanbul", "Tourist", "2024-03-15")
        key2 = service._make_key(456, "Istanbul", "Tourist", "2024-03-15")
        key3 = service._make_key(123, "Ankara", "Tourist", "2024-03-15")
        key4 = service._make_key(123, "Istanbul", "Business", "2024-03-15")
        key5 = service._make_key(123, "Istanbul", "Tourist", "2024-03-16")

        # All keys should be different
        keys = {key1, key2, key3, key4, key5}
        assert len(keys) == 5


@pytest.mark.asyncio
class TestDeduplicationServiceGlobal:
    """Test cases for global deduplication service accessor."""

    async def test_get_deduplication_service_singleton(self):
        """Test that get_deduplication_service returns singleton."""
        # Clear any existing instance
        from src.services import appointment_deduplication

        appointment_deduplication._deduplication_service = None

        service1 = await get_deduplication_service(ttl_seconds=1800)
        service2 = await get_deduplication_service(ttl_seconds=3600)  # Different TTL

        # Should return the same instance (ignoring second TTL)
        assert service1 is service2
        assert service1._ttl_seconds == 1800  # First TTL wins

    async def test_get_deduplication_service_creates_instance(self):
        """Test that service is created if not exists."""
        # Clear any existing instance
        from src.services import appointment_deduplication

        appointment_deduplication._deduplication_service = None

        service = await get_deduplication_service()

        assert service is not None
        assert isinstance(service, AppointmentDeduplication)
        assert service._ttl_seconds == 3600  # Default TTL
