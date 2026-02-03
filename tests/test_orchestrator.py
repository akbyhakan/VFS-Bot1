"""Tests for orchestrator module."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.bot.orchestrator.resource_pool import ResourcePool
from src.services.bot.orchestrator.reservation_worker import ReservationWorker
from src.services.bot.orchestrator.reservation_orchestrator import ReservationOrchestrator


class TestResourcePool:
    """Tests for ResourcePool class."""

    @pytest.mark.asyncio
    async def test_get_next_single_country(self):
        """Test getting next resource for single country."""
        pool = ResourcePool(["A", "B", "C"], name="test")

        assert await pool.get_next("fra") == "A"
        assert await pool.get_next("fra") == "B"
        assert await pool.get_next("fra") == "C"
        assert await pool.get_next("fra") == "A"  # Wraps around

    @pytest.mark.asyncio
    async def test_get_next_multiple_countries(self):
        """Test round-robin for multiple countries."""
        pool = ResourcePool(["A", "B", "C", "D"], name="test")

        # Each country starts at different offset
        assert await pool.get_next("fra") == "A"
        assert await pool.get_next("nld") == "B"
        assert await pool.get_next("bel") == "C"

        # Next round
        assert await pool.get_next("fra") == "B"
        assert await pool.get_next("nld") == "C"
        assert await pool.get_next("bel") == "D"

    @pytest.mark.asyncio
    async def test_get_next_empty_pool(self):
        """Test that empty pool raises ValueError."""
        pool = ResourcePool([], name="empty")

        with pytest.raises(ValueError, match="empty"):
            await pool.get_next("fra")

    @pytest.mark.asyncio
    async def test_get_current(self):
        """Test getting current resource without advancing."""
        pool = ResourcePool(["A", "B"], name="test")

        await pool.get_next("fra")  # Now at index 1
        current = await pool.get_current("fra")
        assert current == "B"

        # Should not advance
        current2 = await pool.get_current("fra")
        assert current2 == "B"

    @pytest.mark.asyncio
    async def test_get_current_unknown_country(self):
        """Test getting current for unknown country returns None."""
        pool = ResourcePool(["A"], name="test")

        result = await pool.get_current("unknown")
        assert result is None

    def test_add_resource(self):
        """Test adding resource to pool."""
        pool = ResourcePool(["A"], name="test")
        pool.add_resource("B")

        assert len(pool) == 2
        assert "B" in pool.get_all()

    def test_remove_resource(self):
        """Test removing resource from pool."""
        pool = ResourcePool(["A", "B"], name="test")

        result = pool.remove_resource("A")
        assert result is True
        assert len(pool) == 1
        assert "A" not in pool.get_all()

    def test_remove_nonexistent_resource(self):
        """Test removing nonexistent resource returns False."""
        pool = ResourcePool(["A"], name="test")

        result = pool.remove_resource("B")
        assert result is False

    def test_update_resources(self):
        """Test updating all resources."""
        pool = ResourcePool(["A", "B"], name="test")
        pool.update_resources(["X", "Y", "Z"])

        assert len(pool) == 3
        assert pool.get_all() == ["X", "Y", "Z"]

    def test_get_stats(self):
        """Test getting pool statistics."""
        pool = ResourcePool(["A", "B"], name="test_pool")

        stats = pool.get_stats()
        assert stats["name"] == "test_pool"
        assert stats["total_resources"] == 2
        assert stats["active_countries"] == []

    @pytest.mark.asyncio
    async def test_get_stats_with_countries(self):
        """Test stats after country access."""
        pool = ResourcePool(["A", "B"], name="test")

        await pool.get_next("fra")
        await pool.get_next("nld")

        stats = pool.get_stats()
        assert "fra" in stats["active_countries"]
        assert "nld" in stats["active_countries"]


class TestReservationWorker:
    """Tests for ReservationWorker class."""

    @pytest.fixture
    def mock_pools(self):
        """Create mock resource pools."""
        account_pool = ResourcePool(
            [{"email": "test@example.com", "password": "pass123"}], name="accounts"
        )
        proxy_pool = ResourcePool([{"server": "http://proxy1:8080"}], name="proxies")
        return account_pool, proxy_pool

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        return {
            "bot": {"check_interval": 1, "headless": True},
            "anti_detection": {"enabled": False},
        }

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        return AsyncMock()

    @pytest.fixture
    def mock_notifier(self):
        """Create mock notifier."""
        return AsyncMock()

    def test_init(self, mock_pools, mock_config, mock_db, mock_notifier):
        """Test worker initialization."""
        account_pool, proxy_pool = mock_pools

        worker = ReservationWorker(
            reservation_id=1,
            country="fra",
            config=mock_config,
            account_pool=account_pool,
            proxy_pool=proxy_pool,
            db=mock_db,
            notifier=mock_notifier,
        )

        assert worker.reservation_id == 1
        assert worker.country == "fra"
        assert worker.running is False
        assert worker.check_count == 0

    def test_mask_email(self, mock_pools, mock_config, mock_db, mock_notifier):
        """Test email masking."""
        account_pool, proxy_pool = mock_pools

        worker = ReservationWorker(
            reservation_id=1,
            country="fra",
            config=mock_config,
            account_pool=account_pool,
            proxy_pool=proxy_pool,
            db=mock_db,
            notifier=mock_notifier,
        )

        assert worker._mask_email("test@example.com") == "tes***@example.com"
        assert worker._mask_email("ab@x.com") == "***"
        assert worker._mask_email("invalid") == "***"

    def test_get_stats(self, mock_pools, mock_config, mock_db, mock_notifier):
        """Test getting worker stats."""
        account_pool, proxy_pool = mock_pools

        worker = ReservationWorker(
            reservation_id=1,
            country="fra",
            config=mock_config,
            account_pool=account_pool,
            proxy_pool=proxy_pool,
            db=mock_db,
            notifier=mock_notifier,
        )

        stats = worker.get_stats()
        assert stats["reservation_id"] == 1
        assert stats["country"] == "fra"
        assert stats["running"] is False
        assert stats["check_count"] == 0

    @pytest.mark.asyncio
    async def test_stop(self, mock_pools, mock_config, mock_db, mock_notifier):
        """Test stopping worker."""
        account_pool, proxy_pool = mock_pools

        worker = ReservationWorker(
            reservation_id=1,
            country="fra",
            config=mock_config,
            account_pool=account_pool,
            proxy_pool=proxy_pool,
            db=mock_db,
            notifier=mock_notifier,
        )

        worker.running = True
        await worker.stop()

        assert worker.running is False

    @pytest.mark.asyncio
    async def test_cleanup(self, mock_pools, mock_config, mock_db, mock_notifier):
        """Test cleanup without browser."""
        account_pool, proxy_pool = mock_pools

        worker = ReservationWorker(
            reservation_id=1,
            country="fra",
            config=mock_config,
            account_pool=account_pool,
            proxy_pool=proxy_pool,
            db=mock_db,
            notifier=mock_notifier,
        )

        # Should not raise even without browser
        await worker.cleanup()
        assert worker.browser_manager is None


class TestReservationOrchestrator:
    """Tests for ReservationOrchestrator class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        return {
            "bot": {"check_interval": 1},
            "proxy": {"enabled": False},
        }

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = AsyncMock()
        db.get_active_users_with_decrypted_passwords = AsyncMock(
            return_value=[{"email": "test@example.com", "password": "pass"}]
        )
        db.get_active_proxies = AsyncMock(return_value=[])
        db.get_active_reservations = AsyncMock(return_value=[])
        return db

    @pytest.fixture
    def mock_notifier(self):
        """Create mock notifier."""
        return AsyncMock()

    def test_init(self, mock_config, mock_db, mock_notifier):
        """Test orchestrator initialization."""
        orchestrator = ReservationOrchestrator(
            config=mock_config,
            db=mock_db,
            notifier=mock_notifier,
        )

        assert orchestrator.running is False
        assert orchestrator.account_pool is None
        assert orchestrator.proxy_pool is None
        assert len(orchestrator.workers) == 0

    @pytest.mark.asyncio
    async def test_stop(self, mock_config, mock_db, mock_notifier):
        """Test stopping orchestrator."""
        orchestrator = ReservationOrchestrator(
            config=mock_config,
            db=mock_db,
            notifier=mock_notifier,
        )

        orchestrator.running = True
        await orchestrator.stop()

        assert orchestrator.running is False

    def test_get_stats(self, mock_config, mock_db, mock_notifier):
        """Test getting orchestrator stats."""
        orchestrator = ReservationOrchestrator(
            config=mock_config,
            db=mock_db,
            notifier=mock_notifier,
        )

        stats = orchestrator.get_stats()
        assert stats["running"] is False
        assert stats["active_workers"] == 0
        assert stats["account_pool"] is None
