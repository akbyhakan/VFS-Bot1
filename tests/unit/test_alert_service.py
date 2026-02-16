"""Tests for alert service."""

import pytest

from src.services.notification.alert_service import (
    AlertChannel,
    AlertConfig,
    AlertService,
    AlertSeverity,
    configure_alert_service,
    get_alert_service,
    send_critical_alert,
)


@pytest.mark.asyncio
async def test_alert_service_initialization():
    """Test alert service initializes with config."""
    config = AlertConfig(enabled_channels=[AlertChannel.LOG])
    service = AlertService(config)

    assert service is not None
    assert AlertChannel.LOG in service.enabled_channels


@pytest.mark.asyncio
async def test_alert_service_send_to_log():
    """Test sending alert to log channel."""
    config = AlertConfig(enabled_channels=[AlertChannel.LOG])
    service = AlertService(config)

    result = await service.send_alert("Test alert", AlertSeverity.INFO)

    assert result is True


@pytest.mark.asyncio
async def test_alert_service_send_critical():
    """Test sending critical alert."""
    config = AlertConfig(enabled_channels=[AlertChannel.LOG])
    service = AlertService(config)

    result = await service.send_alert(
        "Critical system failure", AlertSeverity.CRITICAL, metadata={"component": "test"}
    )

    assert result is True


@pytest.mark.asyncio
async def test_alert_service_multiple_severities():
    """Test different severity levels."""
    config = AlertConfig(enabled_channels=[AlertChannel.LOG])
    service = AlertService(config)

    # Test all severities
    for severity in AlertSeverity:
        result = await service.send_alert(f"Test {severity.value} alert", severity)
        assert result is True


@pytest.mark.asyncio
async def test_alert_service_with_metadata():
    """Test alert with metadata."""
    config = AlertConfig(enabled_channels=[AlertChannel.LOG])
    service = AlertService(config)

    metadata = {"user_id": 123, "error_code": "ERR_500", "retry_count": 3}

    result = await service.send_alert("Test alert", AlertSeverity.ERROR, metadata)

    assert result is True


@pytest.mark.asyncio
async def test_get_alert_service():
    """Test getting global alert service instance."""
    service = get_alert_service()

    assert service is not None
    assert isinstance(service, AlertService)

    # Should return same instance
    service2 = get_alert_service()
    assert service is service2


@pytest.mark.asyncio
async def test_configure_alert_service():
    """Test configuring global alert service."""
    config = AlertConfig(
        enabled_channels=[AlertChannel.LOG, AlertChannel.TELEGRAM],
        telegram_bot_token="test_token",
        telegram_chat_id="test_chat_id",
    )

    configure_alert_service(config)
    service = get_alert_service()

    assert AlertChannel.LOG in service.enabled_channels
    assert AlertChannel.TELEGRAM in service.enabled_channels


@pytest.mark.asyncio
async def test_send_critical_alert_convenience():
    """Test convenience function for critical alerts."""
    result = await send_critical_alert("Critical test alert")

    assert result is True


@pytest.mark.asyncio
async def test_alert_service_telegram_not_configured():
    """Test Telegram channel when not configured."""
    config = AlertConfig(enabled_channels=[AlertChannel.LOG, AlertChannel.TELEGRAM])
    service = AlertService(config)

    # Should not fail, just skip Telegram
    result = await service.send_alert("Test alert", AlertSeverity.INFO)

    # Should succeed via LOG channel
    assert result is True


@pytest.mark.asyncio
async def test_alert_service_email_not_configured():
    """Test Email channel when not configured."""
    config = AlertConfig(enabled_channels=[AlertChannel.LOG, AlertChannel.EMAIL])
    service = AlertService(config)

    # Should not fail, just skip Email
    result = await service.send_alert("Test alert", AlertSeverity.INFO)

    # Should succeed via LOG channel
    assert result is True


@pytest.mark.asyncio
async def test_alert_service_webhook_not_configured():
    """Test Webhook channel when not configured."""
    config = AlertConfig(enabled_channels=[AlertChannel.LOG, AlertChannel.WEBHOOK])
    service = AlertService(config)

    # Should not fail, just skip Webhook
    result = await service.send_alert("Test alert", AlertSeverity.INFO)

    # Should succeed via LOG channel
    assert result is True


@pytest.mark.asyncio
async def test_alert_service_all_channels():
    """Test with all channels enabled."""
    config = AlertConfig(
        enabled_channels=[
            AlertChannel.LOG,
            AlertChannel.TELEGRAM,
            AlertChannel.EMAIL,
            AlertChannel.WEBHOOK,
        ]
    )
    service = AlertService(config)

    # Should at least succeed with LOG
    result = await service.send_alert("Test alert", AlertSeverity.WARNING)

    assert result is True
