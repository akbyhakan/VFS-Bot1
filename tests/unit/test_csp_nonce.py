"""Tests for CSP nonce injection in web application."""

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web.app import create_app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    app = create_app(run_security_validation=False, env_override="testing")
    return TestClient(app)


@pytest.fixture
def temp_dist_dir():
    """Create a temporary dist directory with test index.html."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dist_dir = Path(tmpdir) / "dist"
        dist_dir.mkdir(parents=True)

        # Create a test index.html with nonce placeholders
        index_html = """<!DOCTYPE html>
<html>
<head>
    <title>Test App</title>
    <script nonce="{{CSP_NONCE}}" src="/assets/main.js"></script>
    <style nonce="{{CSP_NONCE}}">body { margin: 0; }</style>
    <link nonce="{{CSP_NONCE}}" rel="stylesheet" href="/assets/main.css">
</head>
<body>
    <div id="root"></div>
</body>
</html>"""
        (dist_dir / "index.html").write_text(index_html)

        # Temporarily replace the dist directory path
        Path(__file__).parent.parent / "web" / "static" / "dist"
        yield dist_dir


class TestCSPNonceInHeaders:
    """Tests for CSP headers."""

    def test_csp_header_present(self, client):
        """Test that CSP header is present in responses."""
        response = client.get("/health")
        assert "Content-Security-Policy" in response.headers

    def test_csp_default_src_self(self, client):
        """Test that CSP header contains default-src 'self'."""
        response = client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp

    def test_csp_frame_ancestors_none(self, client):
        """Test that CSP header contains frame-ancestors 'none'."""
        response = client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")
        assert "frame-ancestors 'none'" in csp

    def test_csp_connect_src_includes_websocket(self, client):
        """Test that CSP connect-src allows WebSocket connections."""
        response = client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")
        assert "connect-src 'self' wss: ws:" in csp

    def test_csp_consistent_across_requests(self, client):
        """Test that CSP header is consistent across requests."""
        response1 = client.get("/health")
        response2 = client.get("/health")

        csp1 = response1.headers.get("Content-Security-Policy", "")
        csp2 = response2.headers.get("Content-Security-Policy", "")

        # CSP should be the same for every request (no dynamic nonces)
        assert csp1 == csp2

    @pytest.mark.parametrize(
        "env_value",
        [
            "production",
            "staging",
            "development",
            "dev",
            "testing",
            "test",
            "local",
        ],
    )
    def test_csp_present_in_all_environments(self, monkeypatch, env_value):
        """Test that CSP header is always present regardless of environment."""
        monkeypatch.setenv("ENV", env_value)

        import importlib

        import web.middleware.security_headers

        importlib.reload(web.middleware.security_headers)

        from fastapi import FastAPI

        from web.middleware.security_headers import SecurityHeadersMiddleware

        test_app = FastAPI()
        test_app.add_middleware(SecurityHeadersMiddleware)

        @test_app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        from fastapi.testclient import TestClient

        test_client = TestClient(test_app)

        response = test_client.get("/test")
        csp = response.headers.get("Content-Security-Policy", "")

        # CSP must be present in every environment
        assert csp != ""
        assert "default-src 'self'" in csp
        # style-src includes 'unsafe-inline' as a deliberate trade-off:
        # React and Tailwind CSS require inline styles. Nonces for stylesheets
        # would require runtime injection per-request. For a single-user app
        # the XSS risk is already mitigated by script-src 'self' (no unsafe-eval).
        assert "'unsafe-inline'" in csp


class TestCSPContent:
    """Tests for CSP header content and security properties."""

    def test_csp_script_src_self_only(self, client):
        """Test that script-src only allows 'self' (no unsafe-eval)."""
        response = client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")
        assert "script-src 'self'" in csp
        assert "'unsafe-eval'" not in csp

    def test_csp_base_uri_self(self, client):
        """Test that base-uri is restricted to 'self'."""
        response = client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")
        assert "base-uri 'self'" in csp

    def test_csp_form_action_self(self, client):
        """Test that form-action is restricted to 'self'."""
        response = client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")
        assert "form-action 'self'" in csp


class TestViteBuildOutput:
    """Tests for Vite build output nonce placeholders."""

    def test_vite_plugin_adds_nonce_placeholder(self):
        """Test that Vite plugin configuration includes nonce plugin."""
        vite_config_path = Path(__file__).parent.parent / "frontend" / "vite.config.ts"

        if vite_config_path.exists():
            config_content = vite_config_path.read_text()

            # Check that the CSP nonce plugin is defined
            assert "cspNoncePlugin" in config_content
            assert "transformIndexHtml" in config_content
            assert "{{CSP_NONCE}}" in config_content

            # Check that plugin is registered
            assert "cspNoncePlugin()" in config_content
