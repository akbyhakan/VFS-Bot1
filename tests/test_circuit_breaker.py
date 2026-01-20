"""Tests for circuit breaker thread-safety."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from collections import deque

from src.services.bot_service import VFSBot
from src.models.database import Database
from src.services.notification import NotificationService


@pytest.mark.asyncio
async def test_circuit_breaker_thread_safety():
    """Test that circuit breaker error recording is thread-safe."""
    # Create a mock config
    config = {
        "bot": {"check_interval": 30, "headless": True},
        "captcha": {"provider": "manual", "api_key": ""},
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tr",
            "mission": "nld",
            "language": "tr",
        },
    }
    
    # Create mocks
    db = Mock(spec=Database)
    notifier = Mock(spec=NotificationService)
    
    # Create bot instance
    bot = VFSBot(config, db, notifier)
    
    # Verify _error_lock exists
    assert hasattr(bot, "_error_lock")
    assert isinstance(bot._error_lock, asyncio.Lock)
    
    # Test concurrent error recording
    async def record_errors(count: int):
        """Record multiple errors concurrently."""
        for _ in range(count):
            await bot._record_error()
    
    # Run concurrent error recordings
    await asyncio.gather(
        record_errors(5),
        record_errors(5),
        record_errors(5),
    )
    
    # Verify consecutive errors are correct (15 total)
    assert bot.consecutive_errors == 15
    assert len(bot.total_errors) == 15


@pytest.mark.asyncio
async def test_circuit_breaker_async_signature():
    """Test that _record_error is async and returns None."""
    config = {
        "bot": {"check_interval": 30, "headless": True},
        "captcha": {"provider": "manual", "api_key": ""},
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tr",
            "mission": "nld",
            "language": "tr",
        },
    }
    
    db = Mock(spec=Database)
    notifier = Mock(spec=NotificationService)
    bot = VFSBot(config, db, notifier)
    
    # Verify _record_error is a coroutine function
    assert asyncio.iscoroutinefunction(bot._record_error)
    
    # Test that it can be awaited
    result = await bot._record_error()
    assert result is None


@pytest.mark.asyncio
async def test_circuit_breaker_opens_with_concurrent_errors():
    """Test that circuit breaker opens correctly under concurrent load."""
    config = {
        "bot": {"check_interval": 30, "headless": True},
        "captcha": {"provider": "manual", "api_key": ""},
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tr",
            "mission": "nld",
            "language": "tr",
        },
    }
    
    db = Mock(spec=Database)
    notifier = Mock(spec=NotificationService)
    bot = VFSBot(config, db, notifier)
    
    # Record enough errors to trigger circuit breaker
    # Default MAX_CONSECUTIVE_ERRORS is typically 5
    for _ in range(10):
        await bot._record_error()
    
    # Circuit breaker should be open
    assert bot.circuit_breaker_open is True
    assert bot.circuit_breaker_open_time is not None
