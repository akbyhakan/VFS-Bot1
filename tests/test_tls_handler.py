"""Tests for TLS handler."""

import pytest
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.anti_detection.tls_handler import TLSHandler


class TestTLSHandler:
    """Test TLS handler functionality."""

    def test_init_default(self):
        """Test TLSHandler initialization with defaults."""
        handler = TLSHandler()

        assert handler.impersonate == "chrome120"
        assert handler.session is None

    def test_init_custom_impersonate(self):
        """Test TLSHandler initialization with custom browser."""
        handler = TLSHandler(impersonate="chrome119")

        assert handler.impersonate == "chrome119"
        assert handler.session is None

    @pytest.mark.asyncio
    async def test_create_session_without_curl_cffi(self):
        """Test session creation when curl-cffi is not available."""
        with patch("src.utils.anti_detection.tls_handler.AsyncSession", None):
            handler = TLSHandler()
            await handler.create_session()

            assert handler.session is None

    @pytest.mark.asyncio
    async def test_create_session_with_curl_cffi(self):
        """Test session creation when curl-cffi is available."""
        mock_session_class = MagicMock()
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        with patch("src.utils.anti_detection.tls_handler.AsyncSession", mock_session_class):
            handler = TLSHandler(impersonate="chrome120")
            await handler.create_session()

            mock_session_class.assert_called_once_with(impersonate="chrome120")
            assert handler.session == mock_session

    @pytest.mark.asyncio
    async def test_create_session_exception(self):
        """Test session creation handles exceptions."""
        mock_session_class = MagicMock()
        mock_session_class.side_effect = Exception("Connection error")

        with patch("src.utils.anti_detection.tls_handler.AsyncSession", mock_session_class):
            handler = TLSHandler()
            await handler.create_session()

            assert handler.session is None

    @pytest.mark.asyncio
    async def test_close_session_with_session(self):
        """Test closing session when session exists."""
        handler = TLSHandler()
        mock_session = AsyncMock()
        handler.session = mock_session

        await handler.close_session()

        mock_session.close.assert_awaited_once()
        assert handler.session is None

    @pytest.mark.asyncio
    async def test_close_session_exception(self):
        """Test closing session handles exceptions."""
        handler = TLSHandler()
        mock_session = AsyncMock()
        mock_session.close.side_effect = Exception("Close error")
        handler.session = mock_session

        await handler.close_session()

        mock_session.close.assert_awaited_once()
        assert handler.session is None

    @pytest.mark.asyncio
    async def test_close_session_no_session(self):
        """Test closing session when no session exists."""
        handler = TLSHandler()
        handler.session = None

        # Should not raise exception
        await handler.close_session()

        assert handler.session is None

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test TLS handler as async context manager."""
        mock_session_class = MagicMock()
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session

        with patch("src.utils.anti_detection.tls_handler.AsyncSession", mock_session_class):
            async with TLSHandler() as handler:
                assert handler.session == mock_session

            mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_request_no_session(self):
        """Test request without initialized session."""
        handler = TLSHandler()
        handler.session = None

        result = await handler.request("GET", "https://example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_request_success(self):
        """Test successful request."""
        handler = TLSHandler()
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_session.request.return_value = mock_response
        handler.session = mock_session

        result = await handler.request("GET", "https://example.com", timeout=30)

        assert result == mock_response
        mock_session.request.assert_awaited_once_with("GET", "https://example.com", timeout=30)

    @pytest.mark.asyncio
    async def test_request_exception(self):
        """Test request handles exceptions."""
        handler = TLSHandler()
        mock_session = AsyncMock()
        mock_session.request.side_effect = Exception("Request failed")
        handler.session = mock_session

        result = await handler.request("POST", "https://example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_method(self):
        """Test GET method wrapper."""
        handler = TLSHandler()
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_session.request.return_value = mock_response
        handler.session = mock_session

        result = await handler.get("https://example.com", headers={"User-Agent": "test"})

        assert result == mock_response
        mock_session.request.assert_awaited_once_with(
            "GET", "https://example.com", headers={"User-Agent": "test"}
        )

    @pytest.mark.asyncio
    async def test_post_method(self):
        """Test POST method wrapper."""
        handler = TLSHandler()
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_session.request.return_value = mock_response
        handler.session = mock_session

        result = await handler.post("https://example.com", data={"key": "value"})

        assert result == mock_response
        mock_session.request.assert_awaited_once_with(
            "POST", "https://example.com", data={"key": "value"}
        )

    @pytest.mark.asyncio
    async def test_get_no_session(self):
        """Test GET method without session."""
        handler = TLSHandler()
        handler.session = None

        result = await handler.get("https://example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_post_no_session(self):
        """Test POST method without session."""
        handler = TLSHandler()
        handler.session = None

        result = await handler.post("https://example.com")

        assert result is None
