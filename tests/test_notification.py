"""Tests for notification service."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.notification import NotificationService


def test_notification_service_initialization():
    """Test notification service initialization."""
    config = {
        'telegram': {'enabled': True, 'bot_token': 'test', 'chat_id': '123'},
        'email': {'enabled': False}
    }
    
    notifier = NotificationService(config)
    assert notifier.telegram_enabled is True
    assert notifier.email_enabled is False


def test_notification_service_disabled():
    """Test notification service with all channels disabled."""
    config = {
        'telegram': {'enabled': False},
        'email': {'enabled': False}
    }
    
    notifier = NotificationService(config)
    assert notifier.telegram_enabled is False
    assert notifier.email_enabled is False


@pytest.mark.asyncio
async def test_notification_with_no_channels():
    """Test sending notification with no channels enabled."""
    config = {
        'telegram': {'enabled': False},
        'email': {'enabled': False}
    }
    
    notifier = NotificationService(config)
    # Should not raise an exception
    await notifier.send_notification("Test", "Test message")
