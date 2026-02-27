"""Tests for path traversal protection in bot routes."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.routes.bot import router
from web.dependencies import verify_jwt_token


def _make_app_with_error_capture(screenshots_dir: str, error_data: dict):
    """Create a FastAPI test app with mocked error_capture state."""
    app = FastAPI()
    app.include_router(router)

    # Override JWT auth for testing
    app.dependency_overrides[verify_jwt_token] = lambda: {"sub": "test_user", "name": "Test"}

    mock_error_capture = MagicMock()
    mock_error_capture.screenshots_dir = screenshots_dir
    mock_error_capture.get_error_by_id = MagicMock(return_value=error_data)
    app.state.error_capture = mock_error_capture

    return app


class TestGetErrorScreenshotPathTraversal:
    """Tests for path traversal protection in get_error_screenshot."""

    def test_valid_screenshot_path_returns_200(self, tmp_path):
        """A legitimate screenshot path inside the screenshots dir returns 200."""
        screenshots_dir = tmp_path / "screenshots"
        screenshots_dir.mkdir()
        screenshot_file = screenshots_dir / "test.png"
        screenshot_file.write_bytes(b"PNG")

        error_data = {"captures": {"full_screenshot": str(screenshot_file)}}
        app = _make_app_with_error_capture(str(screenshots_dir), error_data)

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/bot/errors/err1/screenshot?type=full")

        assert response.status_code == 200

    def test_prefix_bypass_returns_403(self, tmp_path):
        """A path like /app/screenshotsextra/file.png must be rejected (prefix bypass)."""
        screenshots_dir = tmp_path / "screenshots"
        screenshots_dir.mkdir()

        # Create a sibling directory whose name starts with "screenshots"
        bypass_dir = tmp_path / "screenshotsextra"
        bypass_dir.mkdir()
        bypass_file = bypass_dir / "file.png"
        bypass_file.write_bytes(b"PNG")

        error_data = {"captures": {"full_screenshot": str(bypass_file)}}
        app = _make_app_with_error_capture(str(screenshots_dir), error_data)

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/bot/errors/err1/screenshot?type=full")

        assert response.status_code == 403

    def test_classic_path_traversal_returns_403(self, tmp_path):
        """A path like ../../etc/passwd must be rejected."""
        screenshots_dir = tmp_path / "screenshots"
        screenshots_dir.mkdir()

        # Construct a path that resolves outside screenshots_dir
        traversal_path = screenshots_dir / ".." / ".." / "etc" / "passwd"

        error_data = {"captures": {"full_screenshot": str(traversal_path)}}
        app = _make_app_with_error_capture(str(screenshots_dir), error_data)

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/bot/errors/err1/screenshot?type=full")

        assert response.status_code == 403


class TestGetErrorHtmlSnapshotPathTraversal:
    """Tests for path traversal protection in get_error_html_snapshot."""

    def test_valid_html_path_returns_200(self, tmp_path):
        """A legitimate HTML snapshot path inside the screenshots dir returns 200."""
        screenshots_dir = tmp_path / "screenshots"
        screenshots_dir.mkdir()
        html_file = screenshots_dir / "test.html"
        html_file.write_text("<html></html>")

        error_data = {"captures": {"html_snapshot": str(html_file)}}
        app = _make_app_with_error_capture(str(screenshots_dir), error_data)

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/bot/errors/err1/html-snapshot")

        assert response.status_code == 200

    def test_prefix_bypass_returns_403(self, tmp_path):
        """A path like /app/screenshotsextra/file.html must be rejected (prefix bypass)."""
        screenshots_dir = tmp_path / "screenshots"
        screenshots_dir.mkdir()

        bypass_dir = tmp_path / "screenshotsextra"
        bypass_dir.mkdir()
        bypass_file = bypass_dir / "file.html"
        bypass_file.write_text("<html></html>")

        error_data = {"captures": {"html_snapshot": str(bypass_file)}}
        app = _make_app_with_error_capture(str(screenshots_dir), error_data)

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/bot/errors/err1/html-snapshot")

        assert response.status_code == 403

    def test_classic_path_traversal_returns_403(self, tmp_path):
        """A path like ../../etc/passwd must be rejected."""
        screenshots_dir = tmp_path / "screenshots"
        screenshots_dir.mkdir()

        traversal_path = screenshots_dir / ".." / ".." / "etc" / "passwd"

        error_data = {"captures": {"html_snapshot": str(traversal_path)}}
        app = _make_app_with_error_capture(str(screenshots_dir), error_data)

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/bot/errors/err1/html-snapshot")

        assert response.status_code == 403
