"""Tests for waitlist functionality."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.services.bot.waitlist_handler import WaitlistHandler
from src.services.notification.notification import NotificationService


@pytest.fixture
def waitlist_page(mock_page):
    """Mock page with waitlist-specific tracking attributes."""
    mock_page.content_data = ""
    mock_page.screenshot_called = False
    mock_page.screenshot_path = None

    async def _content():
        return mock_page.content_data

    async def _text_content(selector):
        return mock_page.content_data

    async def _screenshot(path=None, full_page=False):
        mock_page.screenshot_called = True
        mock_page.screenshot_path = path

    mock_page.content = _content
    mock_page.text_content = _text_content
    mock_page.screenshot = _screenshot

    return mock_page


@pytest.fixture
def waitlist_handler():
    """Create WaitlistHandler instance for testing."""
    config = {
        "vfs": {"base_url": "https://test.com", "country": "tr", "mission": "test"},
        "bot": {"check_interval": 30},
    }
    return WaitlistHandler(config)


@pytest.fixture
def notification_service():
    """Create NotificationService instance for testing."""
    config = {
        "telegram": {"enabled": True, "bot_token": "test_token", "chat_id": "test_chat_id"},
    }
    return NotificationService(config)


@pytest.mark.asyncio
async def test_detect_waitlist_mode_found(waitlist_handler, waitlist_page):
    """Test waitlist mode detection when waitlist text is found."""
    page = waitlist_page

    # Mock successful waitlist detection
    mock_element = AsyncMock()
    mock_locator = AsyncMock()
    mock_locator.first = AsyncMock()
    mock_locator.first.wait_for = AsyncMock(return_value=mock_element)
    page.locator = MagicMock(return_value=mock_locator)

    result = await waitlist_handler.detect_waitlist_mode(page)
    assert result is True


@pytest.mark.asyncio
async def test_detect_waitlist_mode_not_found(waitlist_handler, waitlist_page):
    """Test waitlist mode detection when waitlist text is not found."""
    page = waitlist_page

    # Mock failed waitlist detection - all locators throw exception
    mock_locator = AsyncMock()
    mock_locator.first = AsyncMock()
    mock_locator.first.wait_for = AsyncMock(side_effect=Exception("Not found"))
    page.locator = MagicMock(return_value=mock_locator)

    result = await waitlist_handler.detect_waitlist_mode(page)
    assert result is False


@pytest.mark.asyncio
async def test_join_waitlist_success(waitlist_handler, waitlist_page):
    """Test successful waitlist checkbox selection."""
    page = waitlist_page

    # Mock input element
    mock_input = AsyncMock()
    mock_input.click = AsyncMock()

    # Mock locator (this is what 'checkbox' will be after wait_for)
    mock_locator_first = AsyncMock()
    mock_locator_first.wait_for = AsyncMock()  # wait_for doesn't return anything
    mock_locator_first.get_attribute = AsyncMock(return_value="")

    # Mock the input locator
    mock_input_locator = AsyncMock()
    mock_input_locator.first = mock_input
    mock_locator_first.locator = MagicMock(return_value=mock_input_locator)

    mock_locator = AsyncMock()
    mock_locator.first = mock_locator_first
    page.locator = MagicMock(return_value=mock_locator)

    result = await waitlist_handler.join_waitlist(page)
    assert result is True


@pytest.mark.asyncio
async def test_join_waitlist_already_checked(waitlist_handler, waitlist_page):
    """Test waitlist checkbox when already selected."""
    page = waitlist_page

    # Mock already checked checkbox (this is the locator after wait_for)
    mock_locator_first = AsyncMock()
    mock_locator_first.wait_for = AsyncMock()
    mock_locator_first.get_attribute = AsyncMock(return_value="mat-mdc-checkbox-checked")

    mock_locator = AsyncMock()
    mock_locator.first = mock_locator_first
    page.locator = MagicMock(return_value=mock_locator)

    result = await waitlist_handler.join_waitlist(page)
    assert result is True


@pytest.mark.asyncio
async def test_join_waitlist_not_found(waitlist_handler, waitlist_page):
    """Test waitlist checkbox when element not found."""
    page = waitlist_page

    # Mock checkbox not found
    mock_locator = AsyncMock()
    mock_locator.first = AsyncMock()
    mock_locator.first.wait_for = AsyncMock(side_effect=Exception("Not found"))
    page.locator = MagicMock(return_value=mock_locator)

    result = await waitlist_handler.join_waitlist(page)
    assert result is False


@pytest.mark.asyncio
async def test_accept_review_checkboxes_success(waitlist_handler, waitlist_page):
    """Test accepting all review checkboxes successfully."""
    page = waitlist_page

    # Mock all checkboxes as unchecked and clickable
    mock_checkbox = AsyncMock()
    mock_checkbox.is_checked = AsyncMock(return_value=False)
    mock_checkbox.click = AsyncMock()

    mock_locator = AsyncMock()
    mock_locator.first = AsyncMock()
    mock_locator.first.wait_for = AsyncMock(return_value=mock_checkbox)
    page.locator = MagicMock(return_value=mock_locator)

    result = await waitlist_handler.accept_review_checkboxes(page)
    assert result is True


@pytest.mark.asyncio
async def test_click_confirm_button_success(waitlist_handler, waitlist_page):
    """Test clicking confirm button successfully."""
    page = waitlist_page

    # Mock confirm button
    mock_button = AsyncMock()
    mock_button.click = AsyncMock()

    mock_locator = AsyncMock()
    mock_locator.first = AsyncMock()
    mock_locator.first.wait_for = AsyncMock(return_value=mock_button)
    page.locator = MagicMock(return_value=mock_locator)

    result = await waitlist_handler.click_confirm_button(page)
    assert result is True


@pytest.mark.asyncio
async def test_click_confirm_button_not_found(waitlist_handler, waitlist_page):
    """Test clicking confirm button when not found."""
    page = waitlist_page

    # Mock button not found
    mock_locator = AsyncMock()
    mock_locator.first = AsyncMock()
    mock_locator.first.wait_for = AsyncMock(side_effect=Exception("Not found"))
    page.locator = MagicMock(return_value=mock_locator)

    result = await waitlist_handler.click_confirm_button(page)
    assert result is False


@pytest.mark.asyncio
async def test_handle_waitlist_success_with_details(waitlist_handler, waitlist_page):
    """Test handling waitlist success screen with detail extraction."""
    page = waitlist_page
    page.content_data = """
    <html>
        <body>
            <h1>Bekleme Listesinde</h1>
            <p>Referans Numarası: ABC123456</p>
            <p>Ülke: Türkiye</p>
            <p>Merkez: Istanbul</p>
            <p>Kategori: Turist Vizesi</p>
            <p>Toplam: 100 EUR</p>
        </body>
    </html>
    """

    # Mock success indicator found
    mock_element = AsyncMock()
    mock_locator = AsyncMock()
    mock_locator.first = AsyncMock()
    mock_locator.first.wait_for = AsyncMock(return_value=mock_element)
    page.locator = MagicMock(return_value=mock_locator)

    login_email = "test@example.com"
    result = await waitlist_handler.handle_waitlist_success(page, login_email)

    assert result is not None
    assert result["login_email"] == login_email
    assert "screenshot_path" in result
    assert "timestamp" in result
    assert page.screenshot_called is True


@pytest.mark.asyncio
async def test_handle_waitlist_success_not_detected(waitlist_handler, waitlist_page):
    """Test handling waitlist success when success screen not detected."""
    page = waitlist_page

    # Mock success indicator not found
    mock_locator = AsyncMock()
    mock_locator.first = AsyncMock()
    mock_locator.first.wait_for = AsyncMock(side_effect=Exception("Not found"))
    page.locator = MagicMock(return_value=mock_locator)

    login_email = "test@example.com"
    result = await waitlist_handler.handle_waitlist_success(page, login_email)

    assert result is None


@pytest.mark.asyncio
async def test_extract_waitlist_details(waitlist_handler, waitlist_page):
    """Test extracting waitlist details from page."""
    page = waitlist_page
    page.content_data = """
    <html>
        <body>
            <h1>İşlem Özeti</h1>
            <p>Referans: REF-123456</p>
            <p>Ülke: Türkiye</p>
            <p>Merkez: Ankara</p>
            <p>Kategori: Çalışma Vizesi</p>
            <p>Alt Kategori: 1 Yıl</p>
            <p>Toplam Ücret: 150.00 EUR</p>
        </body>
    </html>
    """

    # Mock name elements
    mock_name_element = AsyncMock()
    mock_name_element.text_content = AsyncMock(return_value="John Doe")
    mock_locator_with_all = MagicMock()
    mock_locator_with_all.all = AsyncMock(return_value=[mock_name_element])
    page.locator = MagicMock(return_value=mock_locator_with_all)

    details = await waitlist_handler.extract_waitlist_details(page)

    assert "reference_number" in details
    assert "people" in details
    assert "country" in details
    assert "centre" in details
    assert "category" in details
    assert "subcategory" in details
    assert "total_amount" in details


@pytest.mark.asyncio
async def test_notify_waitlist_success(notification_service):
    """Test waitlist success notification."""
    details = {
        "login_email": "test@example.com",
        "reference_number": "REF123456",
        "people": ["John Doe", "Jane Doe"],
        "country": "Türkiye",
        "centre": "Istanbul",
        "category": "Turist Vizesi",
        "subcategory": "90 Gün",
        "total_amount": "200 EUR",
    }

    # Mock the telegram channel's send method
    mock_channel = AsyncMock()
    mock_channel.send = AsyncMock(return_value=True)
    notification_service._telegram_channel = mock_channel
    notification_service.telegram_enabled = True

    await notification_service.notify_waitlist_success(details)

    # Verify send was called
    # (notify_waitlist_success calls send_notification which calls _telegram_channel.send)
    assert mock_channel.send.called


@pytest.mark.asyncio
async def test_notify_waitlist_success_with_screenshot(notification_service, tmp_path):
    """Test waitlist success notification with screenshot."""
    # Create a temporary screenshot file
    screenshot_file = tmp_path / "test_screenshot.png"
    screenshot_file.write_bytes(b"fake image data")

    details = {
        "login_email": "test@example.com",
        "reference_number": "REF123456",
        "people": ["John Doe"],
        "country": "Türkiye",
        "centre": "Istanbul",
        "category": "Turist Vizesi",
        "subcategory": "90 Gün",
        "total_amount": "100 EUR",
    }

    # Mock the telegram channel and its client
    mock_client = AsyncMock()
    mock_client.send_photo = AsyncMock(return_value=True)
    mock_client.TELEGRAM_CAPTION_LIMIT = 1024

    mock_channel = MagicMock()
    mock_channel._get_or_create_client = MagicMock(return_value=mock_client)
    mock_channel._config = MagicMock()
    mock_channel._config.chat_id = "test_chat_id"

    notification_service._telegram_channel = mock_channel
    notification_service.telegram_enabled = True

    await notification_service.notify_waitlist_success(details, str(screenshot_file))

    # Verify send_photo was called
    mock_client.send_photo.assert_called_once()


@pytest.mark.asyncio
async def test_notify_waitlist_success_no_people(notification_service):
    """Test waitlist success notification with no people list."""
    details = {
        "login_email": "test@example.com",
        "reference_number": "REF123456",
        "people": [],
        "country": "Türkiye",
        "centre": "Istanbul",
        "category": "Turist Vizesi",
        "subcategory": "90 Gün",
        "total_amount": "100 EUR",
    }

    # Mock the cached bot instance directly
    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock()
    notification_service._telegram_bot = mock_bot

    await notification_service.notify_waitlist_success(details)

    # Should not raise exception
    assert True


def test_waitlist_handler_initialization():
    """Test WaitlistHandler initialization."""
    config = {
        "vfs": {"base_url": "https://test.com", "country": "tr", "mission": "test"},
    }
    handler = WaitlistHandler(config)

    assert handler.config == config
    assert handler.screenshots_dir.exists()


def test_waitlist_handler_screenshots_dir_created():
    """Test that screenshots directory is created."""
    config = {
        "vfs": {"base_url": "https://test.com", "country": "tr", "mission": "test"},
    }
    handler = WaitlistHandler(config)

    assert handler.screenshots_dir.is_dir()
