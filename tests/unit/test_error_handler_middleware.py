"""Tests for middleware/error_handler module."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request, status
from fastapi.responses import JSONResponse

from src.core.exceptions import (
    AuthenticationError,
    DatabaseError,
    RateLimitError,
    ValidationError,
    VFSBotError,
)
from web.middleware.error_handler import ErrorHandlerMiddleware


class TestErrorHandlerMiddleware:
    """Tests for ErrorHandlerMiddleware."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        return ErrorHandlerMiddleware(app=MagicMock())

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock(spec=Request)
        request.url.path = "/test"
        request.client.host = "127.0.0.1"
        return request

    @pytest.mark.asyncio
    async def test_dispatch_success(self, middleware, mock_request):
        """Test dispatch with successful call_next."""
        expected_response = MagicMock()
        call_next = AsyncMock(return_value=expected_response)

        response = await middleware.dispatch(mock_request, call_next)
        assert response == expected_response

    @pytest.mark.asyncio
    async def test_handle_vfsbot_error(self, middleware, mock_request):
        """Test handling VFSBotError."""
        error = VFSBotError(message="Test error", recoverable=True)
        call_next = AsyncMock(side_effect=error)

        response = await middleware.dispatch(mock_request, call_next)
        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_handle_validation_error(self, middleware, mock_request):
        """Test handling ValidationError."""
        error = ValidationError(message="Invalid input", field="username")
        call_next = AsyncMock(side_effect=error)

        response = await middleware.dispatch(mock_request, call_next)
        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_handle_authentication_error(self, middleware, mock_request):
        """Test handling AuthenticationError."""
        error = AuthenticationError(message="Unauthorized")
        call_next = AsyncMock(side_effect=error)

        response = await middleware.dispatch(mock_request, call_next)
        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_handle_database_error(self, middleware, mock_request):
        """Test handling DatabaseError."""
        error = DatabaseError(message="Connection failed")
        call_next = AsyncMock(side_effect=error)

        response = await middleware.dispatch(mock_request, call_next)
        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_handle_rate_limit_error(self, middleware, mock_request):
        """Test handling RateLimitError."""
        error = RateLimitError(message="Too many requests", retry_after=60)
        call_next = AsyncMock(side_effect=error)

        response = await middleware.dispatch(mock_request, call_next)
        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @pytest.mark.asyncio
    async def test_handle_unexpected_error(self, middleware, mock_request):
        """Test handling unexpected exceptions."""
        error = RuntimeError("Unexpected error")
        call_next = AsyncMock(side_effect=error)

        response = await middleware.dispatch(mock_request, call_next)
        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_handle_vfsbot_error_non_recoverable(self, middleware, mock_request):
        """Test handling non-recoverable VFSBotError."""
        error = VFSBotError(message="Fatal error", recoverable=False)
        response = middleware._handle_vfsbot_error(error, mock_request)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_handle_rate_limit_error_with_wait_time(self, middleware, mock_request):
        """Test RateLimitError includes Retry-After header."""
        error = RateLimitError(message="Rate limited", retry_after=120)
        response = middleware._handle_rate_limit_error(error, mock_request)
        assert "Retry-After" in response.headers
        assert response.headers["Retry-After"] == "120"

    def test_handle_rate_limit_error_no_wait_time(self, middleware, mock_request):
        """Test RateLimitError without retry_after."""
        error = RateLimitError(message="Rate limited")
        response = middleware._handle_rate_limit_error(error, mock_request)
        # Should not have Retry-After header
        assert "Retry-After" not in response.headers

    def test_handle_validation_error_includes_field(self, middleware, mock_request):
        """Test ValidationError response includes field."""
        error = ValidationError(message="Invalid email", field="email")
        response = middleware._handle_validation_error(error, mock_request)
        # Check response body contains field
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestRFC7807Compliance:
    """Tests for RFC 7807 compliance in error handler middleware."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        return ErrorHandlerMiddleware(app=MagicMock())

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock(spec=Request)
        request.url.path = "/test/endpoint"
        request.client.host = "127.0.0.1"
        return request

    def test_validation_error_rfc7807_format(self, middleware, mock_request):
        """Test validation error returns RFC 7807 format."""
        error = ValidationError("Invalid input", field="username")
        response = middleware._handle_validation_error(error, mock_request)

        assert response.media_type == "application/problem+json"
        # Parse response body
        import json

        body = json.loads(response.body)

        assert body["type"] == "urn:vfsbot:error:validation"
        assert body["title"] == "Validation Error"
        assert body["status"] == 400
        assert body["detail"] == "Validation error for field 'username': Invalid input"
        assert body["instance"] == "/test/endpoint"
        assert body["field"] == "username"

    def test_rate_limit_error_rfc7807_format(self, middleware, mock_request):
        """Test rate limit error returns RFC 7807 format."""
        error = RateLimitError("Too many requests", retry_after=60)
        response = middleware._handle_rate_limit_error(error, mock_request)

        assert response.media_type == "application/problem+json"
        import json

        body = json.loads(response.body)

        assert body["type"] == "urn:vfsbot:error:rate-limit"
        assert body["title"] == "Rate Limit Error"
        assert body["status"] == 429
        assert body["instance"] == "/test/endpoint"
        assert body["retry_after"] == 60
        assert body["recoverable"] is True

    def test_auth_error_rfc7807_format(self, middleware, mock_request):
        """Test authentication error returns RFC 7807 format."""
        error = AuthenticationError("Invalid credentials")
        response = middleware._handle_auth_error(error, mock_request)

        assert response.media_type == "application/problem+json"
        import json

        body = json.loads(response.body)

        assert body["type"] == "urn:vfsbot:error:authentication"
        assert body["title"] == "Authentication Error"
        assert body["status"] == 401
        assert body["detail"] == "Invalid credentials"
        assert body["instance"] == "/test/endpoint"

    def test_database_error_rfc7807_format(self, middleware, mock_request):
        """Test database error returns RFC 7807 format."""
        error = DatabaseError("Connection failed", recoverable=True)
        response = middleware._handle_database_error(error, mock_request)

        assert response.media_type == "application/problem+json"
        import json

        body = json.loads(response.body)

        assert body["type"] == "urn:vfsbot:error:database"
        assert body["title"] == "Database Error"
        assert body["status"] == 500
        assert body["detail"] == "Connection failed"
        assert body["instance"] == "/test/endpoint"
        assert body["recoverable"] is True

    def test_unexpected_error_rfc7807_format(self, middleware, mock_request):
        """Test unexpected error returns RFC 7807 format without leaking details."""
        error = RuntimeError("Internal implementation detail")
        response = middleware._handle_unexpected_error(error, mock_request)

        assert response.media_type == "application/problem+json"
        import json

        body = json.loads(response.body)

        assert body["type"] == "urn:vfsbot:error:internal-server"
        assert body["title"] == "Internal Server Error"
        assert body["status"] == 500
        # Should not leak internal details
        assert "Internal implementation detail" not in body["detail"]
        assert body["detail"] == "An unexpected error occurred. Please try again later."
        assert body["instance"] == "/test/endpoint"

    def test_vfsbot_error_rfc7807_format(self, middleware, mock_request):
        """Test generic VFSBot error returns RFC 7807 format."""
        error = VFSBotError("Generic error", recoverable=True)
        response = middleware._handle_vfsbot_error(error, mock_request)

        assert response.media_type == "application/problem+json"
        import json

        body = json.loads(response.body)

        assert body["type"].startswith("urn:vfsbot:error:")
        assert "title" in body
        assert "status" in body
        assert body["detail"] == "Generic error"
        assert body["instance"] == "/test/endpoint"
        assert body["recoverable"] is True
