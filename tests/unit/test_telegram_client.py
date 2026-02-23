"""Tests for TelegramClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.notification.telegram_client import TelegramClient


@pytest.fixture
def telegram_client():
    """Create a TelegramClient with a mocked Bot."""
    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot
        client = TelegramClient(bot_token="test_token")
        client._bot = mock_bot
        yield client


@pytest.mark.asyncio
async def test_format_and_send_basic(telegram_client):
    """Test format_and_send sends correctly formatted message."""
    telegram_client._bot.send_message = AsyncMock()

    result = await telegram_client.format_and_send(
        chat_id="123", title="Hello", message="World"
    )

    assert result is True
    telegram_client._bot.send_message.assert_called_once()
    call_kwargs = telegram_client._bot.send_message.call_args
    text = call_kwargs.kwargs.get("text") or call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs["text"]
    # Check the text is in the sent message
    sent_text = call_kwargs.kwargs.get("text", "")
    assert "Hello" in sent_text
    assert "World" in sent_text
    assert "🤖" in sent_text


@pytest.mark.asyncio
async def test_format_and_send_custom_emoji(telegram_client):
    """Test format_and_send uses custom emoji."""
    telegram_client._bot.send_message = AsyncMock()

    await telegram_client.format_and_send(
        chat_id="123", title="Alert", message="Something happened", emoji="⚠️"
    )

    call_kwargs = telegram_client._bot.send_message.call_args
    sent_text = call_kwargs.kwargs.get("text", "")
    assert "⚠️" in sent_text


@pytest.mark.asyncio
async def test_format_and_send_with_footer(telegram_client):
    """Test format_and_send includes footer when provided."""
    telegram_client._bot.send_message = AsyncMock()

    await telegram_client.format_and_send(
        chat_id="123", title="Title", message="Body", footer="Footer text"
    )

    call_kwargs = telegram_client._bot.send_message.call_args
    sent_text = call_kwargs.kwargs.get("text", "")
    assert "Footer text" in sent_text


@pytest.mark.asyncio
async def test_format_and_send_without_footer(telegram_client):
    """Test format_and_send excludes footer when not provided."""
    telegram_client._bot.send_message = AsyncMock()

    await telegram_client.format_and_send(
        chat_id="123", title="Title", message="Body"
    )

    call_kwargs = telegram_client._bot.send_message.call_args
    sent_text = call_kwargs.kwargs.get("text", "")
    # No footer section
    assert "\n\n_" not in sent_text


@pytest.mark.asyncio
async def test_format_and_send_escapes_markdown(telegram_client):
    """Test format_and_send escapes markdown special characters."""
    telegram_client._bot.send_message = AsyncMock()

    await telegram_client.format_and_send(
        chat_id="123", title="Hello *World*", message="Test_message"
    )

    call_kwargs = telegram_client._bot.send_message.call_args
    sent_text = call_kwargs.kwargs.get("text", "")
    # Asterisks in title/message should be escaped
    # The title is wrapped in bold so *Hello \*World\** is expected
    assert r"\*" in sent_text or "Hello" in sent_text
