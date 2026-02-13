"""Tests for browser pool."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.bot.browser_pool import BrowserPool


@pytest.fixture
def test_config():
    """Test configuration."""
    return {
        "bot": {
            "headless": True,
            "browser_restart_after_pages": 100,
        },
        "anti_detection": {
            "enabled": True,
            "stealth_mode": True,
            "fingerprint_bypass": True,
        },
    }


class TestBrowserPool:
    """Tests for BrowserPool."""

    def test_pool_initialization(self, test_config):
        """Test pool initialization with default values."""
        pool = BrowserPool(test_config)

        assert pool.max_browsers == 5
        assert pool.idle_timeout_minutes == 10
        assert pool.config == test_config
        assert len(pool._browsers) == 0

    def test_pool_custom_params(self, test_config):
        """Test pool initialization with custom parameters."""
        pool = BrowserPool(test_config, max_browsers=10, idle_timeout_minutes=20)

        assert pool.max_browsers == 10
        assert pool.idle_timeout_minutes == 20

    @pytest.mark.asyncio
    async def test_acquire_new_browser(self, test_config):
        """Test acquiring a new browser."""
        pool = BrowserPool(test_config, max_browsers=2)

        with patch.object(pool, "_create_browser", new_callable=AsyncMock) as mock_create:
            mock_browser = MagicMock()
            mock_browser.session_id = "session1"
            mock_create.return_value = mock_browser

            browser = await pool.acquire("session1")

            assert browser == mock_browser
            assert "session1" in pool._browsers
            mock_create.assert_called_once_with("session1")

    @pytest.mark.asyncio
    async def test_acquire_existing_browser(self, test_config):
        """Test acquiring an existing browser."""
        pool = BrowserPool(test_config)

        with patch.object(pool, "_create_browser", new_callable=AsyncMock) as mock_create:
            mock_browser = MagicMock()
            mock_browser.session_id = "session1"
            mock_create.return_value = mock_browser

            # First acquisition
            browser1 = await pool.acquire("session1")

            # Second acquisition (should reuse)
            browser2 = await pool.acquire("session1")

            assert browser1 == browser2
            assert mock_create.call_count == 1

    @pytest.mark.asyncio
    async def test_max_browser_limit(self, test_config):
        """Test that pool respects max browser limit."""
        pool = BrowserPool(test_config, max_browsers=2)

        with patch.object(pool, "_create_browser", new_callable=AsyncMock) as mock_create:
            mock_browsers = []
            for i in range(2):
                mock_browser = MagicMock()
                mock_browser.session_id = f"session{i+1}"
                mock_browsers.append(mock_browser)

            mock_create.side_effect = mock_browsers

            # Acquire 2 browsers (max)
            browser1 = await pool.acquire("session1")
            browser2 = await pool.acquire("session2")

            assert len(pool._browsers) == 2
            
            # Verify stats show no available slots
            stats = pool.get_stats()
            assert stats["available_slots"] == 0

    @pytest.mark.asyncio
    async def test_release_browser_idle(self, test_config):
        """Test releasing browser without closing."""
        pool = BrowserPool(test_config)

        with patch.object(pool, "_create_browser", new_callable=AsyncMock) as mock_create:
            mock_browser = MagicMock()
            mock_browser.session_id = "session1"
            mock_browser.close = AsyncMock()
            mock_create.return_value = mock_browser

            # Acquire and release
            await pool.acquire("session1")
            await pool.release("session1", close_browser=False)

            # Browser should still be in pool
            assert "session1" in pool._browsers
            mock_browser.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_release_browser_close(self, test_config):
        """Test releasing browser with closing."""
        pool = BrowserPool(test_config)

        with patch.object(pool, "_create_browser", new_callable=AsyncMock) as mock_create:
            mock_browser = MagicMock()
            mock_browser.session_id = "session1"
            mock_browser.close = AsyncMock()
            mock_create.return_value = mock_browser

            # Acquire and release
            await pool.acquire("session1")
            await pool.release("session1", close_browser=True)

            # Browser should be removed from pool
            assert "session1" not in pool._browsers
            mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_nonexistent_browser(self, test_config):
        """Test releasing a non-existent browser."""
        pool = BrowserPool(test_config)

        # Should not raise exception
        await pool.release("nonexistent")

    @pytest.mark.asyncio
    async def test_close_all_browsers(self, test_config):
        """Test closing all browsers in pool."""
        pool = BrowserPool(test_config)

        with patch.object(pool, "_create_browser", new_callable=AsyncMock) as mock_create:
            mock_browsers = []
            for i in range(3):
                mock_browser = MagicMock()
                mock_browser.session_id = f"session{i+1}"
                mock_browser.close = AsyncMock()
                mock_browsers.append(mock_browser)

            mock_create.side_effect = mock_browsers

            # Acquire 3 browsers
            await pool.acquire("session1")
            await pool.acquire("session2")
            await pool.acquire("session3")

            # Close all
            await pool.close_all()

            # All browsers should be closed
            assert len(pool._browsers) == 0
            for browser in mock_browsers:
                browser.close.assert_called_once()

    def test_get_stats(self, test_config):
        """Test getting pool statistics."""
        pool = BrowserPool(test_config, max_browsers=5)

        # Mock some browsers
        for i in range(3):
            mock_browser = MagicMock()
            mock_browser.is_idle = i % 2 == 0  # Alternate idle/active
            pool._browsers[f"session{i+1}"] = mock_browser

        stats = pool.get_stats()

        assert stats["total_browsers"] == 3
        assert stats["max_browsers"] == 5
        assert stats["available_slots"] == 2
        assert "sessions" in stats
        assert len(stats["sessions"]) == 3

    @pytest.mark.asyncio
    async def test_create_browser(self, test_config):
        """Test browser creation."""
        pool = BrowserPool(test_config)

        with patch("src.services.bot.browser_pool.BrowserManager") as mock_browser_class:
            mock_browser = MagicMock()
            mock_browser.start = AsyncMock()
            mock_browser_class.return_value = mock_browser

            browser = await pool._create_browser("session1")

            assert browser.session_id == "session1"
            mock_browser.start.assert_called_once()
            mock_browser_class.assert_called_once_with(
                config=test_config,
                header_manager=None,
                proxy_manager=None,
            )

    @pytest.mark.asyncio
    async def test_concurrent_acquire(self, test_config):
        """Test concurrent browser acquisition."""
        pool = BrowserPool(test_config, max_browsers=3)

        with patch.object(pool, "_create_browser", new_callable=AsyncMock) as mock_create:
            # Create unique browsers for each session
            async def create_browser_side_effect(session_id):
                mock_browser = MagicMock()
                mock_browser.session_id = session_id
                await asyncio.sleep(0.01)  # Simulate async work
                return mock_browser

            mock_create.side_effect = create_browser_side_effect

            # Acquire 3 browsers concurrently
            tasks = [
                pool.acquire(f"session{i+1}")
                for i in range(3)
            ]
            browsers = await asyncio.gather(*tasks)

            assert len(browsers) == 3
            assert len(pool._browsers) == 3

    @pytest.mark.asyncio
    async def test_context_manager(self, test_config):
        """Test pool as async context manager."""
        with patch.object(BrowserPool, "_create_browser", new_callable=AsyncMock) as mock_create:
            mock_browser = MagicMock()
            mock_browser.session_id = "session1"
            mock_browser.close = AsyncMock()
            mock_create.return_value = mock_browser

            async with BrowserPool(test_config) as pool:
                await pool.acquire("session1")
                assert len(pool._browsers) == 1

            # Pool should be cleaned up after context exit
            # Note: Can't check pool._browsers directly as it's out of scope
            mock_browser.close.assert_called()

    @pytest.mark.asyncio
    async def test_acquire_error_handling(self, test_config):
        """Test error handling during browser acquisition."""
        pool = BrowserPool(test_config)

        with patch.object(pool, "_create_browser", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("Browser creation failed")

            with pytest.raises(Exception, match="Browser creation failed"):
                await pool.acquire("session1")

            # Session should not be added to pool
            assert "session1" not in pool._browsers

    @pytest.mark.asyncio
    async def test_release_error_handling(self, test_config):
        """Test error handling during browser release."""
        pool = BrowserPool(test_config)

        with patch.object(pool, "_create_browser", new_callable=AsyncMock) as mock_create:
            mock_browser = MagicMock()
            mock_browser.session_id = "session1"
            mock_browser.close = AsyncMock(side_effect=Exception("Close failed"))
            mock_create.return_value = mock_browser

            await pool.acquire("session1")

            # Should not raise exception even if close fails
            await pool.release("session1", close_browser=True)

            # Browser should still be removed from pool
            assert "session1" not in pool._browsers

    def test_idle_browser_detection(self, test_config):
        """Test idle browser detection in stats."""
        pool = BrowserPool(test_config)

        # Create mock browsers with different idle states
        mock_browser1 = MagicMock()
        mock_browser1.is_idle = True
        pool._browsers["session1"] = mock_browser1

        mock_browser2 = MagicMock()
        mock_browser2.is_idle = False
        pool._browsers["session2"] = mock_browser2

        stats = pool.get_stats()

        assert stats["total_browsers"] == 2
        assert stats["idle_browsers"] == 1
        assert stats["active_browsers"] == 1
