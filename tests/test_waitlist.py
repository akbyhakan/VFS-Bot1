"""Tests for waitlist functionality."""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.bot.waitlist_handler import WaitlistHandler
from src.services.notification import NotificationService


class MockPage:
    """Mock Playwright page for testing."""

    def __init__(self):
        self.locator_results = {}
        self.content_data = ""
        self.screenshot_called = False
        self.screenshot_path = None

    def locator(self, selector):
        """Mock locator method."""
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.all = AsyncMock(return_value=[])
        mock_locator.wait_for = AsyncMock()
        mock_locator.get_attribute = AsyncMock(return_value="")
        mock_locator.is_checked = AsyncMock(return_value=False)
        mock_locator.click = AsyncMock()

        # Setup nested input locator - locator() is not async
        input_locator = MagicMock()
        input_locator.first = MagicMock()
        input_locator.click = AsyncMock()
        mock_locator.locator = MagicMock(return_value=input_locator)

        # Setup first.wait_for for async waiting
        async_waitable = AsyncMock()
        async_waitable.wait_for = AsyncMock(return_value=mock_locator)
        mock_locator.first.wait_for = AsyncMock(return_value=mock_locator)

        if selector in self.locator_results:
            return self.locator_results[selector]

        return mock_locator

    async def content(self):
        """Mock content method."""
        return self.content_data

    async def text_content(self, selector):
        """Mock text_content method."""
        return self.content_data

    async def screenshot(self, path=None, full_page=False):
        """Mock screenshot method."""
        self.screenshot_called = True
        self.screenshot_path = path


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
        "email": {"enabled": False},
    }
    return NotificationService(config)


@pytest.mark.asyncio
async def test_detect_waitlist_mode_found(waitlist_handler):
    """Test waitlist mode detection when waitlist text is found."""
    page = MockPage()

    # Mock successful waitlist detection
    mock_element = AsyncMock()
    mock_locator = AsyncMock()
    mock_locator.first = AsyncMock()
    mock_locator.first.wait_for = AsyncMock(return_value=mock_element)
    page.locator = MagicMock(return_value=mock_locator)

    result = await waitlist_handler.detect_waitlist_mode(page)
    assert result is True


@pytest.mark.asyncio
async def test_detect_waitlist_mode_not_found(waitlist_handler):
    """Test waitlist mode detection when waitlist text is not found."""
    page = MockPage()

    # Mock failed waitlist detection - all locators throw exception
    mock_locator = AsyncMock()
    mock_locator.first = AsyncMock()
    mock_locator.first.wait_for = AsyncMock(side_effect=Exception("Not found"))
    page.locator = MagicMock(return_value=mock_locator)

    result = await waitlist_handler.detect_waitlist_mode(page)
    assert result is False


@pytest.mark.asyncio
async def test_join_waitlist_success(waitlist_handler):
    """Test successful waitlist checkbox selection."""
    page = MockPage()

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
async def test_join_waitlist_already_checked(waitlist_handler):
    """Test waitlist checkbox when already selected."""
    page = MockPage()

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
async def test_join_waitlist_not_found(waitlist_handler):
    """Test waitlist checkbox when element not found."""
    page = MockPage()

    # Mock checkbox not found
    mock_locator = AsyncMock()
    mock_locator.first = AsyncMock()
    mock_locator.first.wait_for = AsyncMock(side_effect=Exception("Not found"))
    page.locator = MagicMock(return_value=mock_locator)

    result = await waitlist_handler.join_waitlist(page)
    assert result is False


@pytest.mark.asyncio
async def test_accept_review_checkboxes_success(waitlist_handler):
    """Test accepting all review checkboxes successfully."""
    page = MockPage()

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
async def test_click_confirm_button_success(waitlist_handler):
    """Test clicking confirm button successfully."""
    page = MockPage()

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
async def test_click_confirm_button_not_found(waitlist_handler):
    """Test clicking confirm button when not found."""
    page = MockPage()

    # Mock button not found
    mock_locator = AsyncMock()
    mock_locator.first = AsyncMock()
    mock_locator.first.wait_for = AsyncMock(side_effect=Exception("Not found"))
    page.locator = MagicMock(return_value=mock_locator)

    result = await waitlist_handler.click_confirm_button(page)
    assert result is False


@pytest.mark.asyncio
async def test_handle_waitlist_success_with_details(waitlist_handler):
    """Test handling waitlist success screen with detail extraction."""
    page = MockPage()
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
async def test_handle_waitlist_success_not_detected(waitlist_handler):
    """Test handling waitlist success when success screen not detected."""
    page = MockPage()

    # Mock success indicator not found
    mock_locator = AsyncMock()
    mock_locator.first = AsyncMock()
    mock_locator.first.wait_for = AsyncMock(side_effect=Exception("Not found"))
    page.locator = MagicMock(return_value=mock_locator)

    login_email = "test@example.com"
    result = await waitlist_handler.handle_waitlist_success(page, login_email)

    assert result is None


@pytest.mark.asyncio
async def test_extract_waitlist_details(waitlist_handler):
    """Test extracting waitlist details from page."""
    page = MockPage()
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

    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot
        mock_bot.send_message = AsyncMock()

        await notification_service.notify_waitlist_success(details)

        # Verify send_message was called
        assert mock_bot.send_message.called or mock_bot.send_photo.called


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

    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot
        mock_bot.send_photo = AsyncMock()

        await notification_service.notify_waitlist_success(details, str(screenshot_file))

        # Verify send_photo was called
        mock_bot.send_photo.assert_called_once()


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

    with patch("telegram.Bot") as MockBot:
        mock_bot = AsyncMock()
        MockBot.return_value = mock_bot
        mock_bot.send_message = AsyncMock()

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
