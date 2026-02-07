"""Tests for BotController singleton."""

import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.bot_controller import BotController


@pytest.fixture
def reset_controller():
    """Reset the BotController singleton between tests."""
    BotController.reset_instance()
    yield
    BotController.reset_instance()


@pytest.fixture
def mock_bot():
    """Create a mock VFSBot instance."""
    bot = MagicMock()
    bot.running = False
    return bot


@pytest.fixture
def mock_shutdown_event():
    """Create a mock shutdown event."""
    return asyncio.Event()


class TestBotControllerSingleton:
    """Tests for BotController singleton pattern."""
    
    def test_singleton_pattern(self, reset_controller):
        """Test that BotController implements singleton pattern."""
        controller1 = BotController()
        controller2 = BotController()
        
        assert controller1 is controller2
    
    def test_singleton_thread_safe(self, reset_controller):
        """Test that singleton is thread-safe."""
        instances = []
        
        def create_instance():
            instances.append(BotController())
        
        threads = [threading.Thread(target=create_instance) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # All instances should be the same object
        assert len(set(id(inst) for inst in instances)) == 1
    
    def test_reset_instance(self, reset_controller):
        """Test that reset_instance clears the singleton."""
        controller1 = BotController()
        BotController.reset_instance()
        controller2 = BotController()
        
        assert controller1 is not controller2


class TestBotControllerRegistration:
    """Tests for bot registration."""
    
    def test_register_bot(self, reset_controller, mock_bot, mock_shutdown_event):
        """Test registering a bot instance."""
        controller = BotController()
        controller.register_bot(mock_bot, shutdown_event=mock_shutdown_event)
        
        assert controller.get_bot() is mock_bot
    
    def test_get_bot_when_not_registered(self, reset_controller):
        """Test get_bot returns None when no bot is registered."""
        controller = BotController()
        assert controller.get_bot() is None
    
    def test_is_running_when_not_registered(self, reset_controller):
        """Test is_running returns False when no bot is registered."""
        controller = BotController()
        assert controller.is_running() is False
    
    def test_is_running_when_bot_running(self, reset_controller, mock_bot):
        """Test is_running returns True when bot is running."""
        controller = BotController()
        mock_bot.running = True
        controller.register_bot(mock_bot)
        
        assert controller.is_running() is True
    
    def test_is_running_when_bot_stopped(self, reset_controller, mock_bot):
        """Test is_running returns False when bot is stopped."""
        controller = BotController()
        mock_bot.running = False
        controller.register_bot(mock_bot)
        
        assert controller.is_running() is False


class TestBotControllerStatus:
    """Tests for status reporting."""
    
    def test_get_status_not_registered(self, reset_controller):
        """Test get_status when bot is not registered."""
        controller = BotController()
        status = controller.get_status()
        
        assert status['registered'] is False
        assert status['running'] is False
        assert status['status'] == 'not_initialized'
    
    def test_get_status_registered_stopped(self, reset_controller, mock_bot):
        """Test get_status when bot is registered but stopped."""
        controller = BotController()
        mock_bot.running = False
        controller.register_bot(mock_bot)
        
        status = controller.get_status()
        assert status['registered'] is True
        assert status['running'] is False
        assert status['status'] == 'stopped'
    
    def test_get_status_registered_running(self, reset_controller, mock_bot):
        """Test get_status when bot is registered and running."""
        controller = BotController()
        mock_bot.running = True
        controller.register_bot(mock_bot)
        
        status = controller.get_status()
        assert status['registered'] is True
        assert status['running'] is True
        assert status['status'] == 'running'


class TestBotControllerStart:
    """Tests for starting the bot."""
    
    @pytest.mark.asyncio
    async def test_start_bot_not_registered(self, reset_controller):
        """Test starting bot when not registered."""
        controller = BotController()
        result = await controller.start_bot()
        
        assert result['status'] == 'error'
        assert 'not initialized' in result['message'].lower()
    
    @pytest.mark.asyncio
    async def test_start_bot_already_running(self, reset_controller, mock_bot):
        """Test starting bot when already running."""
        controller = BotController()
        mock_bot.running = True
        controller.register_bot(mock_bot)
        
        result = await controller.start_bot()
        
        assert result['status'] == 'error'
        assert 'already running' in result['message'].lower()
    
    @pytest.mark.asyncio
    @patch('src.core.bot_controller.BotController._sync_state_to_dict', new_callable=AsyncMock)
    async def test_start_bot_success(self, mock_sync, reset_controller, mock_bot):
        """Test successfully starting the bot."""
        controller = BotController()
        mock_bot.running = False
        controller.register_bot(mock_bot)
        
        result = await controller.start_bot()
        
        assert result['status'] == 'success'
        assert mock_bot.running is True
        mock_sync.assert_called_once_with(running=True, status='running')
    
    @pytest.mark.asyncio
    @patch('src.core.bot_controller.BotController._sync_state_to_dict', new_callable=AsyncMock)
    async def test_start_bot_exception(self, mock_sync, reset_controller):
        """Test handling exception when starting bot."""
        controller = BotController()
        
        # Create a mock bot that will raise when setting running to True
        mock_bot = MagicMock()
        
        def raise_on_true(value):
            if value:
                raise RuntimeError("Test error")
        
        type(mock_bot).running = property(
            fget=lambda self: False,
            fset=lambda self, value: raise_on_true(value)
        )
        
        controller.register_bot(mock_bot)
        
        result = await controller.start_bot()
        
        assert result['status'] == 'error'
        assert 'failed to start' in result['message'].lower()


class TestBotControllerStop:
    """Tests for stopping the bot."""
    
    @pytest.mark.asyncio
    async def test_stop_bot_not_registered(self, reset_controller):
        """Test stopping bot when not registered."""
        controller = BotController()
        result = await controller.stop_bot()
        
        assert result['status'] == 'error'
        assert 'not initialized' in result['message'].lower()
    
    @pytest.mark.asyncio
    async def test_stop_bot_not_running(self, reset_controller, mock_bot):
        """Test stopping bot when not running."""
        controller = BotController()
        mock_bot.running = False
        controller.register_bot(mock_bot)
        
        result = await controller.stop_bot()
        
        assert result['status'] == 'error'
        assert 'not running' in result['message'].lower()
    
    @pytest.mark.asyncio
    @patch('src.core.bot_controller.BotController._sync_state_to_dict', new_callable=AsyncMock)
    async def test_stop_bot_success(self, mock_sync, reset_controller, mock_bot, mock_shutdown_event):
        """Test successfully stopping the bot."""
        controller = BotController()
        mock_bot.running = True
        controller.register_bot(mock_bot, shutdown_event=mock_shutdown_event)
        
        result = await controller.stop_bot()
        
        assert result['status'] == 'success'
        assert mock_bot.running is False
        assert mock_shutdown_event.is_set()
        mock_sync.assert_called_once_with(running=False, status='stopped')
    
    @pytest.mark.asyncio
    @patch('src.core.bot_controller.BotController._sync_state_to_dict', new_callable=AsyncMock)
    async def test_stop_bot_without_shutdown_event(self, mock_sync, reset_controller, mock_bot):
        """Test stopping bot when shutdown_event is not set."""
        controller = BotController()
        mock_bot.running = True
        controller.register_bot(mock_bot, shutdown_event=None)
        
        result = await controller.stop_bot()
        
        assert result['status'] == 'success'
        assert mock_bot.running is False


class TestBotControllerRestart:
    """Tests for restarting the bot."""
    
    @pytest.mark.asyncio
    async def test_restart_bot_not_registered(self, reset_controller):
        """Test restarting bot when not registered."""
        controller = BotController()
        result = await controller.restart_bot()
        
        assert result['status'] == 'error'
        assert 'not initialized' in result['message'].lower()
    
    @pytest.mark.asyncio
    @patch('src.core.bot_controller.BotController._sync_state_to_dict', new_callable=AsyncMock)
    async def test_restart_bot_success(self, mock_sync, reset_controller, mock_bot, mock_shutdown_event):
        """Test successfully restarting the bot."""
        controller = BotController()
        mock_bot.running = True
        controller.register_bot(mock_bot, shutdown_event=mock_shutdown_event)
        
        result = await controller.restart_bot()
        
        assert result['status'] == 'success'
        assert 'restarted successfully' in result['message'].lower()
        # Should sync state multiple times (restarting, stopped, running)
        assert mock_sync.call_count >= 2
    
    @pytest.mark.asyncio
    @patch('src.core.bot_controller.BotController._sync_state_to_dict', new_callable=AsyncMock)
    async def test_restart_bot_when_stopped(self, mock_sync, reset_controller, mock_bot):
        """Test restarting bot when it's already stopped."""
        controller = BotController()
        mock_bot.running = False
        controller.register_bot(mock_bot)
        
        result = await controller.restart_bot()
        
        # Should succeed even if bot was not running
        assert result['status'] == 'success'


class TestBotControllerThreadSafety:
    """Tests for thread safety of BotController operations."""
    
    @pytest.mark.asyncio
    async def test_concurrent_status_checks(self, reset_controller, mock_bot):
        """Test concurrent status checks are thread-safe."""
        controller = BotController()
        controller.register_bot(mock_bot)
        
        async def check_status():
            for _ in range(100):
                controller.get_status()
                controller.is_running()
                await asyncio.sleep(0.001)
        
        # Run multiple concurrent status checks
        await asyncio.gather(*[check_status() for _ in range(10)])
        
        # Should complete without errors
        assert True
    
    def test_concurrent_registration(self, reset_controller):
        """Test concurrent bot registration is thread-safe."""
        controller = BotController()
        mock_bots = [MagicMock() for _ in range(10)]
        
        def register_bot(bot):
            controller.register_bot(bot)
        
        threads = [threading.Thread(target=register_bot, args=(bot,)) for bot in mock_bots]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # Should have one of the bots registered
        assert controller.get_bot() in mock_bots


class TestBotControllerStateSynchronization:
    """Tests for state synchronization with bot_state dict."""
    
    @pytest.mark.asyncio
    @patch('web.dependencies.bot_state', {'running': False, 'status': 'stopped'})
    @patch('web.dependencies.broadcast_message', new_callable=AsyncMock)
    async def test_sync_state_to_dict(self, mock_broadcast, reset_controller):
        """Test state synchronization to bot_state dict."""
        from web.dependencies import bot_state
        
        controller = BotController()
        await controller._sync_state_to_dict(running=True, status='running')
        
        # Check that bot_state was updated
        assert bot_state['running'] is True
        assert bot_state['status'] == 'running'
        
        # Check that broadcast was called
        mock_broadcast.assert_called_once()
        call_args = mock_broadcast.call_args[0][0]
        assert call_args['type'] == 'status'
        assert call_args['data']['running'] is True
        assert call_args['data']['status'] == 'running'
