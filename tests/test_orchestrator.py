"""Tests for orchestrator module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.bot.orchestrator.reservation_orchestrator import ReservationOrchestrator
from src.services.bot.orchestrator.reservation_worker import ReservationWorker
from src.services.bot.orchestrator.resource_pool import ResourcePool


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

    @pytest.mark.asyncio
    async def test_process_check_no_account(self, mock_pools, mock_config, mock_db, mock_notifier):
        """Test _process_check returns error when no account available."""
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

        # No account set
        worker.current_account = None

        mock_page = MagicMock()
        result = await worker._process_check(mock_page)

        assert result["slot_found"] is False
        assert "error" in result
        assert result["error"] == "No account available"

    @pytest.mark.asyncio
    async def test_process_check_with_account(
        self, mock_pools, mock_config, mock_db, mock_notifier
    ):
        """Test _process_check creates BookingWorkflow and calls process_user."""
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

        # Set current account
        worker.current_account = {"email": "test@example.com", "password": "pass123"}

        mock_page = MagicMock()

        # Mock BookingWorkflow to avoid actual execution
        with patch(
            "src.services.bot.orchestrator.reservation_worker.BookingWorkflow"
        ) as MockWorkflow:
            mock_workflow_instance = AsyncMock()
            MockWorkflow.return_value = mock_workflow_instance

            result = await worker._process_check(mock_page)

            # Verify BookingWorkflow was created
            MockWorkflow.assert_called_once()

            # Verify process_user was called with correct arguments
            mock_workflow_instance.process_user.assert_called_once_with(
                mock_page, worker.current_account
            )

            # Verify result indicates success
            assert result["slot_found"] is True

    @pytest.mark.asyncio
    async def test_process_check_handles_exception(
        self, mock_pools, mock_config, mock_db, mock_notifier
    ):
        """Test _process_check handles exceptions from process_user."""
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

        worker.current_account = {"email": "test@example.com", "password": "pass123"}

        mock_page = MagicMock()

        # Mock BookingWorkflow to raise an exception
        with patch(
            "src.services.bot.orchestrator.reservation_worker.BookingWorkflow"
        ) as MockWorkflow:
            mock_workflow_instance = AsyncMock()
            mock_workflow_instance.process_user.side_effect = Exception("Test error")
            MockWorkflow.return_value = mock_workflow_instance

            result = await worker._process_check(mock_page)

            # Verify result indicates failure
            assert result["slot_found"] is False
            assert "error" in result
            assert "Test error" in result["error"]


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

    @pytest.mark.asyncio
    async def test_start_worker_with_valid_reservation(self, mock_config, mock_db, mock_notifier):
        """Test starting a worker with valid reservation data."""
        orchestrator = ReservationOrchestrator(
            config=mock_config,
            db=mock_db,
            notifier=mock_notifier,
        )

        # Initialize pools
        orchestrator.account_pool = ResourcePool([{"email": "test@test.com"}], name="accounts")
        orchestrator.proxy_pool = ResourcePool([{"server": "http://proxy:8080"}], name="proxies")

        # Valid reservation
        reservation = {"id": 123, "mission_code": "fra"}

        await orchestrator._start_worker(reservation)

        assert "fra" in orchestrator.workers
        assert "fra" in orchestrator.worker_tasks
        assert orchestrator.workers["fra"].reservation_id == 123
        assert orchestrator.workers["fra"].country == "fra"

        # Cleanup
        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_start_worker_missing_country(self, mock_config, mock_db, mock_notifier):
        """Test that worker is not started when country is missing."""
        orchestrator = ReservationOrchestrator(
            config=mock_config,
            db=mock_db,
            notifier=mock_notifier,
        )

        # Initialize pools
        orchestrator.account_pool = ResourcePool([{"email": "test@test.com"}], name="accounts")
        orchestrator.proxy_pool = ResourcePool([{"server": "http://proxy:8080"}], name="proxies")

        # Missing country
        reservation = {"id": 123}

        await orchestrator._start_worker(reservation)

        assert len(orchestrator.workers) == 0

    @pytest.mark.asyncio
    async def test_start_worker_missing_id(self, mock_config, mock_db, mock_notifier):
        """Test that worker is not started when id is missing."""
        orchestrator = ReservationOrchestrator(
            config=mock_config,
            db=mock_db,
            notifier=mock_notifier,
        )

        # Initialize pools
        orchestrator.account_pool = ResourcePool([{"email": "test@test.com"}], name="accounts")
        orchestrator.proxy_pool = ResourcePool([{"server": "http://proxy:8080"}], name="proxies")

        # Missing id
        reservation = {"mission_code": "fra"}

        await orchestrator._start_worker(reservation)

        assert len(orchestrator.workers) == 0

    @pytest.mark.asyncio
    async def test_start_worker_no_account_pool(self, mock_config, mock_db, mock_notifier):
        """Test that worker is not started when account pool is None."""
        orchestrator = ReservationOrchestrator(
            config=mock_config,
            db=mock_db,
            notifier=mock_notifier,
        )

        # Only proxy pool initialized
        orchestrator.proxy_pool = ResourcePool([{"server": "http://proxy:8080"}], name="proxies")

        reservation = {"id": 123, "mission_code": "fra"}

        await orchestrator._start_worker(reservation)

        assert len(orchestrator.workers) == 0

    @pytest.mark.asyncio
    async def test_start_worker_no_proxy_pool(self, mock_config, mock_db, mock_notifier):
        """Test that worker is not started when proxy pool is None."""
        orchestrator = ReservationOrchestrator(
            config=mock_config,
            db=mock_db,
            notifier=mock_notifier,
        )

        # Only account pool initialized
        orchestrator.account_pool = ResourcePool([{"email": "test@test.com"}], name="accounts")

        reservation = {"id": 123, "mission_code": "fra"}

        await orchestrator._start_worker(reservation)

        assert len(orchestrator.workers) == 0

    @pytest.mark.asyncio
    async def test_start_worker_already_exists(self, mock_config, mock_db, mock_notifier):
        """Test that duplicate worker is not started."""
        orchestrator = ReservationOrchestrator(
            config=mock_config,
            db=mock_db,
            notifier=mock_notifier,
        )

        # Initialize pools
        orchestrator.account_pool = ResourcePool([{"email": "test@test.com"}], name="accounts")
        orchestrator.proxy_pool = ResourcePool([{"server": "http://proxy:8080"}], name="proxies")

        reservation = {"id": 123, "mission_code": "fra"}

        # Start first worker
        await orchestrator._start_worker(reservation)
        initial_worker = orchestrator.workers["fra"]

        # Try to start duplicate
        await orchestrator._start_worker(reservation)

        # Should be same worker
        assert orchestrator.workers["fra"] is initial_worker

        # Cleanup
        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_stop_worker(self, mock_config, mock_db, mock_notifier):
        """Test stopping a specific worker."""
        orchestrator = ReservationOrchestrator(
            config=mock_config,
            db=mock_db,
            notifier=mock_notifier,
        )

        # Initialize pools and start worker
        orchestrator.account_pool = ResourcePool([{"email": "test@test.com"}], name="accounts")
        orchestrator.proxy_pool = ResourcePool([{"server": "http://proxy:8080"}], name="proxies")

        reservation = {"id": 123, "mission_code": "fra"}
        await orchestrator._start_worker(reservation)

        assert "fra" in orchestrator.workers

        # Stop the worker
        await orchestrator._stop_worker("fra")

        assert "fra" not in orchestrator.workers
        assert "fra" not in orchestrator.worker_tasks

    @pytest.mark.asyncio
    async def test_get_active_reservations_fallback(self, mock_config, mock_notifier):
        """Test fallback when db method doesn't exist."""
        # DB without get_active_reservations method
        mock_db = AsyncMock()
        # Don't add the get_active_reservations attribute

        orchestrator = ReservationOrchestrator(
            config=mock_config,
            db=mock_db,
            notifier=mock_notifier,
        )

        result = await orchestrator._get_active_reservations()

        assert result == []

    @pytest.mark.asyncio
    async def test_load_proxies_from_db(self, mock_config, mock_notifier):
        """Test loading proxies from database."""
        mock_db = AsyncMock()
        mock_db.get_active_users_with_decrypted_passwords = AsyncMock(return_value=[])
        mock_db.get_active_proxies = AsyncMock(
            return_value=[{"server": "http://proxy1:8080"}, {"server": "http://proxy2:8080"}]
        )

        orchestrator = ReservationOrchestrator(
            config=mock_config,
            db=mock_db,
            notifier=mock_notifier,
        )

        proxies = await orchestrator._load_proxies()

        assert len(proxies) == 2
        assert proxies[0]["server"] == "http://proxy1:8080"
