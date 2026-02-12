"""Tests for ForensicLogger - country-aware black box logging."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import Page

from src.resilience import ForensicLogger


class TestForensicLoggerInitialization:
    """Tests for ForensicLogger initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        logger = ForensicLogger()

        assert logger.base_dir == Path("logs/errors")
        assert logger.country_code == "default"
        assert logger.max_incidents == 500
        assert logger.max_html_size == 5_000_000

    def test_init_with_custom_country(self):
        """Test initialization with custom country code."""
        logger = ForensicLogger(country_code="FRA")  # Test case normalization

        assert logger.country_code == "fra"
        assert logger.country_dir == Path("logs/errors/fra")

    def test_init_creates_directories(self, tmp_path):
        """Test initialization creates necessary directories."""
        base_dir = tmp_path / "logs"
        logger = ForensicLogger(base_dir=str(base_dir), country_code="nld")

        assert logger.country_dir.exists()
        assert logger.country_dir == base_dir / "nld"


class TestCountryAwareDirectoryStructure:
    """Tests for country-aware directory organization."""

    def test_get_incident_dir_creates_date_subdirectory(self, tmp_path):
        """Test _get_incident_dir creates date-based subdirectory."""
        base_dir = tmp_path / "logs"
        logger = ForensicLogger(base_dir=str(base_dir), country_code="fra")

        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        incident_dir = logger._get_incident_dir(timestamp)

        assert incident_dir == base_dir / "fra" / "2024-01-15"
        assert incident_dir.exists()

    def test_different_countries_separate_directories(self, tmp_path):
        """Test different countries use separate directory structures."""
        base_dir = tmp_path / "logs"

        logger_fra = ForensicLogger(base_dir=str(base_dir), country_code="fra")
        logger_nld = ForensicLogger(base_dir=str(base_dir), country_code="nld")

        assert logger_fra.country_dir == base_dir / "fra"
        assert logger_nld.country_dir == base_dir / "nld"
        assert logger_fra.country_dir != logger_nld.country_dir


class TestCaptureIncident:
    """Tests for capture_incident method."""

    @pytest.mark.asyncio
    async def test_capture_incident_creates_all_files(self, tmp_path):
        """Test capture_incident creates screenshot, DOM, and context files."""
        base_dir = tmp_path / "logs"
        logger = ForensicLogger(base_dir=str(base_dir), country_code="fra")

        # Mock page
        page = MagicMock(spec=Page)
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html>test</html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}
        page.evaluate = AsyncMock(return_value="Mozilla/5.0")
        page.context.cookies = AsyncMock(return_value=[])

        error = ValueError("Test error")
        context = {"step": "login", "action": "click_button"}

        incident = await logger.capture_incident(page, error, context)

        # Check incident record structure
        assert "id" in incident
        assert incident["error_type"] == "ValueError"
        assert incident["error_message"] == "Test error"
        assert incident["country_code"] == "fra"
        assert incident["context"] == context

        # Check files were created
        assert "screenshot" in incident["captures"]
        assert "dom" in incident["captures"]
        assert "context" in incident["captures"]

    @pytest.mark.asyncio
    async def test_capture_incident_masks_cookie_values(self, tmp_path):
        """Test cookie values are masked in context JSON."""
        base_dir = tmp_path / "logs"
        logger = ForensicLogger(base_dir=str(base_dir), country_code="fra")

        page = MagicMock(spec=Page)
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html>test</html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test")
        page.viewport_size = {}
        page.evaluate = AsyncMock(return_value="")
        page.context.cookies = AsyncMock(
            return_value=[
                {"name": "session_id", "value": "secret123", "domain": ".example.com"}
            ]
        )

        error = Exception("test")
        incident = await logger.capture_incident(page, error, {})

        # Read context file
        context_path = Path(incident["captures"]["context"])
        with open(context_path, "r") as f:
            context_data = json.load(f)

        # Check cookie value is masked
        cookies = context_data["page_context"]["cookies"]
        assert len(cookies) == 1
        assert cookies[0]["name"] == "session_id"
        assert cookies[0]["value"] == "[MASKED]"
        assert "secret123" not in json.dumps(context_data)

    @pytest.mark.asyncio
    async def test_capture_incident_masks_storage(self, tmp_path):
        """Test localStorage and sessionStorage values are masked."""
        base_dir = tmp_path / "logs"
        logger = ForensicLogger(base_dir=str(base_dir), country_code="fra")

        page = MagicMock(spec=Page)
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html>test</html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test")
        page.viewport_size = {}
        page.evaluate = AsyncMock(
            side_effect=[
                "Mozilla/5.0",
                ["token", "user_id"],  # localStorage keys
                ["session_data"],  # sessionStorage keys
            ]
        )
        page.context.cookies = AsyncMock(return_value=[])

        error = Exception("test")
        incident = await logger.capture_incident(page, error, {})

        # Read context file
        context_path = Path(incident["captures"]["context"])
        with open(context_path, "r") as f:
            context_data = json.load(f)

        # Check storage values are masked
        local_storage = context_data["page_context"]["localStorage"]
        assert local_storage["token"] == "[MASKED]"
        assert local_storage["user_id"] == "[MASKED]"

        session_storage = context_data["page_context"]["sessionStorage"]
        assert session_storage["session_data"] == "[MASKED]"

    @pytest.mark.asyncio
    async def test_capture_incident_truncates_large_html(self, tmp_path):
        """Test HTML is truncated when exceeds max size."""
        base_dir = tmp_path / "logs"
        logger = ForensicLogger(base_dir=str(base_dir), max_html_size=1000)

        page = MagicMock(spec=Page)
        page.screenshot = AsyncMock()
        large_html = "<html>" + ("x" * 10000) + "</html>"
        page.content = AsyncMock(return_value=large_html)
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test")
        page.viewport_size = {}
        page.evaluate = AsyncMock(return_value="")
        page.context.cookies = AsyncMock(return_value=[])

        error = Exception("test")
        incident = await logger.capture_incident(page, error, {})

        # Read DOM file
        dom_path = Path(incident["captures"]["dom"])
        dom_content = dom_path.read_text()

        assert len(dom_content) <= 1000 + 50  # Max size + truncation marker
        assert "TRUNCATED" in dom_content

    @pytest.mark.asyncio
    async def test_capture_incident_graceful_on_screenshot_failure(self, tmp_path):
        """Test capture continues even if screenshot fails."""
        base_dir = tmp_path / "logs"
        logger = ForensicLogger(base_dir=str(base_dir))

        page = MagicMock(spec=Page)
        page.screenshot = AsyncMock(side_effect=Exception("Screenshot failed"))
        page.content = AsyncMock(return_value="<html>test</html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test")
        page.viewport_size = {}
        page.evaluate = AsyncMock(return_value="")
        page.context.cookies = AsyncMock(return_value=[])

        error = Exception("test")
        incident = await logger.capture_incident(page, error, {})

        # Should still capture other data
        assert "dom" in incident["captures"]
        assert "context" in incident["captures"]


class TestIncidentRetrieval:
    """Tests for incident retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_recent_incidents_returns_newest_first(self, tmp_path):
        """Test get_recent_incidents returns incidents sorted by newest first."""
        base_dir = tmp_path / "logs"
        logger = ForensicLogger(base_dir=str(base_dir), country_code="fra")

        page = MagicMock(spec=Page)
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test")
        page.viewport_size = {}
        page.evaluate = AsyncMock(return_value="")
        page.context.cookies = AsyncMock(return_value=[])

        # Capture multiple incidents
        incident1 = await logger.capture_incident(page, Exception("error1"), {})
        await asyncio.sleep(0.1)
        incident2 = await logger.capture_incident(page, Exception("error2"), {})

        recent = logger.get_recent_incidents(limit=10)

        assert len(recent) == 2
        # Most recent first
        assert recent[0]["error_message"] == "error2"
        assert recent[1]["error_message"] == "error1"

    def test_get_incident_by_id(self, tmp_path):
        """Test get_incident_by_id retrieves specific incident."""
        base_dir = tmp_path / "logs"
        logger = ForensicLogger(base_dir=str(base_dir), country_code="fra")

        # Create mock incident
        incident_id = "20240115_103000_123456"
        incident_dir = logger._get_incident_dir(datetime.now(timezone.utc))
        context_file = incident_dir / f"{incident_id}_context.json"

        test_data = {
            "id": incident_id,
            "error_type": "TestError",
            "error_message": "Test message",
        }
        context_file.write_text(json.dumps(test_data))

        retrieved = logger.get_incident_by_id(incident_id)

        assert retrieved is not None
        assert retrieved["id"] == incident_id
        assert retrieved["error_type"] == "TestError"

    def test_get_incident_by_id_not_found(self, tmp_path):
        """Test get_incident_by_id returns None for non-existent incident."""
        base_dir = tmp_path / "logs"
        logger = ForensicLogger(base_dir=str(base_dir), country_code="fra")

        retrieved = logger.get_incident_by_id("nonexistent_id")

        assert retrieved is None


class TestCleanup:
    """Tests for incident cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_removes_oldest_incidents(self, tmp_path):
        """Test cleanup removes oldest incidents when max exceeded."""
        base_dir = tmp_path / "logs"
        logger = ForensicLogger(base_dir=str(base_dir), max_incidents=2)

        page = MagicMock(spec=Page)
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test")
        page.viewport_size = {}
        page.evaluate = AsyncMock(return_value="")
        page.context.cookies = AsyncMock(return_value=[])

        # Capture 3 incidents (exceeds max of 2)
        import asyncio

        incident1 = await logger.capture_incident(page, Exception("error1"), {})
        await asyncio.sleep(0.1)
        incident2 = await logger.capture_incident(page, Exception("error2"), {})
        await asyncio.sleep(0.1)
        incident3 = await logger.capture_incident(page, Exception("error3"), {})

        recent = logger.get_recent_incidents(limit=10)

        # Should only have 2 most recent
        assert len(recent) == 2
        assert recent[0]["error_message"] == "error3"
        assert recent[1]["error_message"] == "error2"


class TestGetStatus:
    """Tests for get_status method."""

    def test_get_status_returns_metrics(self, tmp_path):
        """Test get_status returns comprehensive metrics."""
        base_dir = tmp_path / "logs"
        logger = ForensicLogger(base_dir=str(base_dir), country_code="fra")

        status = logger.get_status()

        assert status["country_code"] == "fra"
        assert status["total_incidents"] >= 0
        assert status["max_incidents"] == 500
        assert "base_dir" in status
        assert "country_dir" in status
