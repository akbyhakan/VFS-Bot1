"""Tests for TLS handler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.utils.anti_detection.tls_handler import TLSHandler


@pytest.fixture
def mock_async_session():
    """Mock curl_cffi AsyncSession."""
    session = AsyncMock()
    session.close = AsyncMock()
    session.request = AsyncMock(return_value=MagicMock(status_code=200))
    return session


@pytest.mark.asyncio
async def test_tls_handler_initialization_default():
    """Test TLS handler initialization with default impersonation."""
    handler = TLSHandler()
    assert handler.impersonate == "chrome136"
    assert handler.session is None


@pytest.mark.asyncio
async def test_tls_handler_initialization_custom():
    """Test TLS handler initialization with custom impersonation."""
    handler = TLSHandler(impersonate="chrome119")
    assert handler.impersonate == "chrome119"
    assert handler.session is None


@pytest.mark.asyncio
async def test_create_session_with_curl_cffi(mock_async_session):
    """Test session creation with curl-cffi available."""
    with patch(
        "src.utils.anti_detection.tls_handler.AsyncSession", return_value=mock_async_session
    ):
        handler = TLSHandler(impersonate="chrome136")
        await handler.create_session()
        assert handler.session == mock_async_session


@pytest.mark.asyncio
async def test_create_session_error_handling(mock_async_session):
    """Test session creation error handling."""
    with patch(
        "src.utils.anti_detection.tls_handler.AsyncSession",
        side_effect=Exception("Session creation failed"),
    ):
        handler = TLSHandler()
        await handler.create_session()
        assert handler.session is None


@pytest.mark.asyncio
async def test_close_session_when_none():
    """Test closing session when no session exists."""
    handler = TLSHandler()
    await handler.close_session()
    assert handler.session is None


@pytest.mark.asyncio
async def test_close_session_success(mock_async_session):
    """Test successful session closure."""
    handler = TLSHandler()
    handler.session = mock_async_session
    await handler.close_session()
    mock_async_session.close.assert_called_once()
    assert handler.session is None


@pytest.mark.asyncio
async def test_close_session_error_handling(mock_async_session):
    """Test session closure error handling."""
    mock_async_session.close = AsyncMock(side_effect=Exception("Close failed"))
    handler = TLSHandler()
    handler.session = mock_async_session
    await handler.close_session()
    assert handler.session is None


@pytest.mark.asyncio
async def test_context_manager_entry(mock_async_session):
    """Test async context manager entry."""
    with patch(
        "src.utils.anti_detection.tls_handler.AsyncSession", return_value=mock_async_session
    ):
        async with TLSHandler() as handler:
            assert handler.session == mock_async_session


@pytest.mark.asyncio
async def test_context_manager_exit(mock_async_session):
    """Test async context manager exit."""
    with patch(
        "src.utils.anti_detection.tls_handler.AsyncSession", return_value=mock_async_session
    ):
        async with TLSHandler() as handler:
            pass
        assert handler.session is None


@pytest.mark.asyncio
async def test_request_without_session():
    """Test request without initialized session."""
    handler = TLSHandler()
    result = await handler.request("GET", "https://example.com")
    assert result is None


@pytest.mark.asyncio
async def test_request_success(mock_async_session):
    """Test successful request."""
    handler = TLSHandler()
    handler.session = mock_async_session
    response = await handler.request("GET", "https://example.com")
    assert response is not None
    mock_async_session.request.assert_called_once_with("GET", "https://example.com")


@pytest.mark.asyncio
async def test_request_with_kwargs(mock_async_session):
    """Test request with additional parameters."""
    handler = TLSHandler()
    handler.session = mock_async_session
    await handler.request(
        "POST", "https://example.com", data={"key": "value"}, headers={"User-Agent": "test"}
    )
    mock_async_session.request.assert_called_once_with(
        "POST", "https://example.com", data={"key": "value"}, headers={"User-Agent": "test"}
    )


@pytest.mark.asyncio
async def test_request_error_handling(mock_async_session):
    """Test request error handling."""
    mock_async_session.request = AsyncMock(side_effect=Exception("Request failed"))
    handler = TLSHandler()
    handler.session = mock_async_session
    result = await handler.request("GET", "https://example.com")
    assert result is None


@pytest.mark.asyncio
async def test_get_method(mock_async_session):
    """Test GET method wrapper."""
    handler = TLSHandler()
    handler.session = mock_async_session
    await handler.get("https://example.com", params={"q": "test"})
    mock_async_session.request.assert_called_once_with(
        "GET", "https://example.com", params={"q": "test"}
    )


@pytest.mark.asyncio
async def test_post_method(mock_async_session):
    """Test POST method wrapper."""
    handler = TLSHandler()
    handler.session = mock_async_session
    await handler.post("https://example.com", data={"key": "value"})
    mock_async_session.request.assert_called_once_with(
        "POST", "https://example.com", data={"key": "value"}
    )


@pytest.mark.asyncio
async def test_get_without_session():
    """Test GET method without session."""
    handler = TLSHandler()
    result = await handler.get("https://example.com")
    assert result is None


@pytest.mark.asyncio
async def test_post_without_session():
    """Test POST method without session."""
    handler = TLSHandler()
    result = await handler.post("https://example.com")
    assert result is None
