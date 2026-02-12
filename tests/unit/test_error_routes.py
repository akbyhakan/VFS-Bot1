"""Tests for error routes."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.utils.error_capture import ErrorCapture
from web.app import app


@pytest.fixture
def test_screenshots_dir(tmp_path):
    """Create a temporary directory for test screenshots."""
    test_dir = tmp_path / "test_errors"
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir
    # Cleanup
    if test_dir.exists():
        shutil.rmtree(test_dir)


@pytest.fixture
def error_capture(test_screenshots_dir):
    """Create an ErrorCapture instance for testing."""
    return ErrorCapture(screenshots_dir=str(test_screenshots_dir))


@pytest.fixture
def client(error_capture):
    """Create test client with error_capture configured."""
    # Set error_capture on app state
    app.state.error_capture = error_capture
    client = TestClient(app)
    yield client
    # Cleanup
    if hasattr(app.state, "error_capture"):
        delattr(app.state, "error_capture")


@pytest.fixture
def sample_error(error_capture, test_screenshots_dir):
    """Create a sample error with HTML snapshot."""
    error_id = "20240101_120000_000000"
    
    # Create HTML snapshot file
    html_path = test_screenshots_dir / f"{error_id}.html"
    html_path.write_text("<html><body>Test Error Page</body></html>", encoding="utf-8")
    
    # Create screenshot file
    screenshot_path = test_screenshots_dir / f"{error_id}_full.png"
    screenshot_path.write_bytes(b"fake_png_data")
    
    # Create error record
    error_record = {
        "id": error_id,
        "timestamp": "2024-01-01T12:00:00.000000+00:00",
        "error_type": "TestError",
        "error_message": "Test error message",
        "context": {"step": "test_step"},
        "captures": {
            "html_snapshot": str(html_path),
            "full_screenshot": str(screenshot_path),
        },
    }
    
    # Add to error_capture's in-memory list
    error_capture.errors.append(error_record)
    
    return error_record


class TestErrorHTMLSnapshotEndpoint:
    """Tests for GET /api/errors/{error_id}/html-snapshot endpoint."""

    def test_get_html_snapshot_success(self, client, sample_error):
        """Test successful HTML snapshot retrieval."""
        response = client.get(f"/api/errors/{sample_error['id']}/html-snapshot")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert "error_20240101_120000_000000.html" in response.headers.get("content-disposition", "")
        assert b"Test Error Page" in response.content

    def test_get_html_snapshot_error_not_found(self, client):
        """Test 404 when error doesn't exist."""
        response = client.get("/api/errors/nonexistent_error_id/html-snapshot")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "HTML snapshot not found"

    def test_get_html_snapshot_no_html_in_error(self, client, error_capture):
        """Test 404 when error exists but has no HTML snapshot."""
        error_id = "20240101_130000_000000"
        error_record = {
            "id": error_id,
            "timestamp": "2024-01-01T13:00:00.000000+00:00",
            "error_type": "TestError",
            "error_message": "Test error without HTML",
            "context": {"step": "test_step"},
            "captures": {},  # No html_snapshot
        }
        error_capture.errors.append(error_record)
        
        response = client.get(f"/api/errors/{error_id}/html-snapshot")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "HTML snapshot not found"

    def test_get_html_snapshot_path_traversal_blocked(
        self, client, sample_error, test_screenshots_dir, tmp_path
    ):
        """Test that path traversal attempts are blocked with 403."""
        # Create a file outside the expected directory
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir(exist_ok=True)
        malicious_file = outside_dir / "malicious.html"
        malicious_file.write_text("<html><body>Malicious content</body></html>", encoding="utf-8")
        
        # Modify the error record to point to file outside screenshots_dir
        error_id = "20240101_140000_000000"
        error_record = {
            "id": error_id,
            "timestamp": "2024-01-01T14:00:00.000000+00:00",
            "error_type": "TestError",
            "error_message": "Test error with path traversal",
            "context": {"step": "test_step"},
            "captures": {
                "html_snapshot": str(malicious_file),  # Outside screenshots_dir
            },
        }
        client.app.state.error_capture.errors.append(error_record)
        
        response = client.get(f"/api/errors/{error_id}/html-snapshot")
        
        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied"

    def test_get_html_snapshot_file_not_exists(self, client, error_capture, test_screenshots_dir):
        """Test 500 when HTML file path is in record but file doesn't exist."""
        error_id = "20240101_150000_000000"
        non_existent_path = test_screenshots_dir / "nonexistent.html"
        
        error_record = {
            "id": error_id,
            "timestamp": "2024-01-01T15:00:00.000000+00:00",
            "error_type": "TestError",
            "error_message": "Test error with missing file",
            "context": {"step": "test_step"},
            "captures": {
                "html_snapshot": str(non_existent_path),
            },
        }
        error_capture.errors.append(error_record)
        
        response = client.get(f"/api/errors/{error_id}/html-snapshot")
        
        # Should return 404 when file doesn't exist
        assert response.status_code == 404
        assert response.json()["detail"] == "HTML snapshot not found"

    def test_get_html_snapshot_no_error_capture(self, test_screenshots_dir):
        """Test 404 when error_capture is not configured in app state."""
        # Create client without error_capture
        test_client = TestClient(app)
        
        response = test_client.get("/api/errors/some_error_id/html-snapshot")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "HTML snapshot not found"
