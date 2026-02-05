"""Tests for ResourcePool round-robin rotation."""

import asyncio

import pytest

from src.services.bot.orchestrator.resource_pool import ResourcePool


@pytest.mark.asyncio
async def test_round_robin_rotation():
    """Test round-robin rotation for different countries."""
    resources = ["R1", "R2", "R3", "R4"]
    pool = ResourcePool(resources, name="test")

    # First round
    assert await pool.get_next("fra") == "R1"  # fra starts at 0
    assert await pool.get_next("nld") == "R2"  # nld starts at 1
    assert await pool.get_next("bel") == "R3"  # bel starts at 2

    # Second round
    assert await pool.get_next("fra") == "R2"  # fra advances to 1
    assert await pool.get_next("nld") == "R3"  # nld advances to 2
    assert await pool.get_next("bel") == "R4"  # bel advances to 3

    # Third round
    assert await pool.get_next("fra") == "R3"
    assert await pool.get_next("nld") == "R4"
    assert await pool.get_next("bel") == "R1"  # wraps around


@pytest.mark.asyncio
async def test_independent_country_indices():
    """Test that each country has independent index."""
    resources = ["A", "B", "C"]
    pool = ResourcePool(resources, name="test")

    # Get multiple from same country
    results_fra = [await pool.get_next("fra") for _ in range(6)]
    assert results_fra == ["A", "B", "C", "A", "B", "C"]

    # nld should start fresh from its offset
    results_nld = [await pool.get_next("nld") for _ in range(3)]
    assert results_nld == ["B", "C", "A"]


@pytest.mark.asyncio
async def test_empty_pool_raises():
    """Test that empty pool raises ValueError."""
    pool = ResourcePool([], name="empty")

    with pytest.raises(ValueError, match="ResourcePool\\[empty\\] is empty"):
        await pool.get_next("fra")


@pytest.mark.asyncio
async def test_update_resources():
    """Test updating pool resources."""
    pool = ResourcePool(["A", "B"], name="test")

    await pool.get_next("fra")  # Get A
    await pool.get_next("fra")  # Get B

    pool.update_resources(["X", "Y", "Z"])

    # Indices should be reset
    assert await pool.get_next("fra") == "X"


@pytest.mark.asyncio
async def test_get_current():
    """Test getting current resource without advancing."""
    resources = ["A", "B", "C"]
    pool = ResourcePool(resources, name="test")

    # Initially no current for country
    assert await pool.get_current("fra") is None

    # After first get_next, current should be next one
    await pool.get_next("fra")  # Gets A, advances to B
    current = await pool.get_current("fra")
    assert current == "B"

    # Current should not change
    assert await pool.get_current("fra") == "B"


@pytest.mark.asyncio
async def test_add_resource():
    """Test adding resources to pool."""
    pool = ResourcePool(["A", "B"], name="test")

    assert len(pool) == 2

    pool.add_resource("C")
    assert len(pool) == 3
    assert "C" in pool.get_all()


@pytest.mark.asyncio
async def test_remove_resource():
    """Test removing resources from pool."""
    pool = ResourcePool(["A", "B", "C"], name="test")

    assert pool.remove_resource("B") is True
    assert len(pool) == 2
    assert "B" not in pool.get_all()

    # Removing non-existent resource
    assert pool.remove_resource("D") is False


@pytest.mark.asyncio
async def test_get_stats():
    """Test getting pool statistics."""
    pool = ResourcePool(["A", "B", "C"], name="test_pool")

    await pool.get_next("fra")
    await pool.get_next("nld")

    stats = pool.get_stats()

    assert stats["name"] == "test_pool"
    assert stats["total_resources"] == 3
    assert set(stats["active_countries"]) == {"fra", "nld"}
    assert "fra" in stats["country_indices"]
    assert "nld" in stats["country_indices"]


@pytest.mark.asyncio
async def test_concurrent_access():
    """Test that pool is thread-safe with concurrent access."""
    resources = ["A", "B", "C", "D"]
    pool = ResourcePool(resources, name="concurrent")

    async def get_resources(country: str, count: int):
        results = []
        for _ in range(count):
            results.append(await pool.get_next(country))
        return results

    # Run concurrent access from multiple countries
    results = await asyncio.gather(
        get_resources("fra", 4),
        get_resources("nld", 4),
        get_resources("bel", 4),
    )

    # Each country should get all resources in order
    assert results[0] == ["A", "B", "C", "D"]  # fra starts at 0
    assert results[1] == ["B", "C", "D", "A"]  # nld starts at 1
    assert results[2] == ["C", "D", "A", "B"]  # bel starts at 2


@pytest.mark.asyncio
async def test_dict_resources():
    """Test pool with dictionary resources (like accounts/proxies)."""
    accounts = [
        {"email": "user1@test.com", "password": "pass1"},
        {"email": "user2@test.com", "password": "pass2"},
        {"email": "user3@test.com", "password": "pass3"},
    ]

    pool = ResourcePool(accounts, name="accounts")

    # First round
    acc1 = await pool.get_next("fra")
    assert acc1["email"] == "user1@test.com"

    acc2 = await pool.get_next("fra")
    assert acc2["email"] == "user2@test.com"

    acc3 = await pool.get_next("fra")
    assert acc3["email"] == "user3@test.com"

    # Wrap around
    acc4 = await pool.get_next("fra")
    assert acc4["email"] == "user1@test.com"
