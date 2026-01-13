"""Tests for TLS handler functionality."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.anti_detection.tls_handler import TLSHandler


class TestTLSHandler:
    """Test TLS handler functionality."""

    def test_init_default(self):
        """Test TLS handler initialization with default impersonation."""
        handler = TLSHandler()
        assert handler.impersonate == "chrome120"
        assert handler.session is None

    def test_init_custom_impersonation(self):
        """Test TLS handler initialization with custom impersonation."""
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
    async def test_create_session_success(self):
        """Test successful session creation."""
        mock_session = AsyncMock()
        with patch("src.utils.anti_detection.tls_handler.AsyncSession") as mock_async_session:
            mock_async_session.return_value = mock_session

            handler = TLSHandler()
            await handler.create_session()

            assert handler.session == mock_session
            mock_async_session.assert_called_once_with(impersonate="chrome120")

    @pytest.mark.asyncio
    async def test_create_session_error(self):
        """Test session creation with error."""
        with patch("src.utils.anti_detection.tls_handler.AsyncSession") as mock_async_session:
            mock_async_session.side_effect = Exception("Connection failed")

            handler = TLSHandler()
            await handler.create_session()

            assert handler.session is None

    @pytest.mark.asyncio
    async def test_close_session_success(self):
        """Test successful session closing."""
        mock_session = AsyncMock()
        handler = TLSHandler()
        handler.session = mock_session

        await handler.close_session()

        mock_session.close.assert_called_once()
        assert handler.session is None

    @pytest.mark.asyncio
    async def test_close_session_error(self):
        """Test session closing with error."""
        mock_session = AsyncMock()
        mock_session.close.side_effect = Exception("Close error")

        handler = TLSHandler()
        handler.session = mock_session

        await handler.close_session()

        assert handler.session is None

    @pytest.mark.asyncio
    async def test_close_session_none(self):
        """Test closing when no session exists."""
        handler = TLSHandler()
        handler.session = None

        await handler.close_session()

        assert handler.session is None

    @pytest.mark.asyncio
    async def test_request_without_session(self):
        """Test request when session is not initialized."""
        handler = TLSHandler()
        handler.session = None

        result = await handler.request("GET", "https://example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_request_success(self):
        """Test successful request."""
        mock_response = MagicMock()
        mock_session = AsyncMock()
        mock_session.request.return_value = mock_response

        handler = TLSHandler()
        handler.session = mock_session

        result = await handler.request("GET", "https://example.com", headers={"test": "header"})

        assert result == mock_response
        mock_session.request.assert_called_once_with(
            "GET", "https://example.com", headers={"test": "header"}
        )

    @pytest.mark.asyncio
    async def test_request_error(self):
        """Test request with error."""
        mock_session = AsyncMock()
        mock_session.request.side_effect = Exception("Request failed")

        handler = TLSHandler()
        handler.session = mock_session

        result = await handler.request("POST", "https://example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_method(self):
        """Test GET request helper method."""
        mock_response = MagicMock()
        mock_session = AsyncMock()
        mock_session.request.return_value = mock_response

        handler = TLSHandler()
        handler.session = mock_session

        result = await handler.get("https://example.com", params={"key": "value"})

        assert result == mock_response
        mock_session.request.assert_called_once_with(
            "GET", "https://example.com", params={"key": "value"}
        )

    @pytest.mark.asyncio
    async def test_post_method(self):
        """Test POST request helper method."""
        mock_response = MagicMock()
        mock_session = AsyncMock()
        mock_session.request.return_value = mock_response

        handler = TLSHandler()
        handler.session = mock_session

        result = await handler.post("https://example.com", json={"data": "test"})

        assert result == mock_response
        mock_session.request.assert_called_once_with(
            "POST", "https://example.com", json={"data": "test"}
        )

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager usage."""
        mock_session = AsyncMock()

        with patch("src.utils.anti_detection.tls_handler.AsyncSession") as mock_async_session:
            mock_async_session.return_value = mock_session

            async with TLSHandler(impersonate="chrome119") as handler:
                assert handler.session == mock_session

            mock_session.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
