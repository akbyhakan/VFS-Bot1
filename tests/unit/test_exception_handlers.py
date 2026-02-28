"""Tests for web/exception_handlers module."""

from unittest.mock import MagicMock

import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError

from web.exception_handlers import (
    _ERROR_TITLES,
    _ERROR_TYPES,
    http_exception_handler,
    validation_exception_handler,
)


@pytest.fixture
def mock_request():
    """Create a mock request."""
    request = MagicMock(spec=Request)
    request.url.path = "/test"
    return request


class TestErrorConstants:
    """Tests for module-level constants."""

    def test_error_types_known_status_codes(self):
        """Test that known status codes have URN-format error types."""
        for code, urn in _ERROR_TYPES.items():
            assert urn.startswith("urn:vfsbot:error:"), f"Status {code} has invalid type: {urn}"

    def test_error_titles_known_status_codes(self):
        """Test that known status codes have non-empty titles."""
        for code, title in _ERROR_TITLES.items():
            assert isinstance(title, str) and title, f"Status {code} has empty title"

    def test_error_types_and_titles_same_keys(self):
        """Test that error types and titles have the same status codes."""
        assert set(_ERROR_TYPES.keys()) == set(_ERROR_TITLES.keys())


class TestHttpExceptionHandler:
    """Tests for http_exception_handler."""

    @pytest.mark.asyncio
    async def test_known_status_code_produces_correct_type(self, mock_request):
        """Test that known status codes use their configured URN type."""
        from fastapi import HTTPException

        exc = HTTPException(status_code=404, detail="Not found")
        response = await http_exception_handler(mock_request, exc)

        body = response.body
        import json
        data = json.loads(body)

        assert data["type"] == "urn:vfsbot:error:not-found"
        assert data["title"] == "Not Found"
        assert data["status"] == 404
        assert data["detail"] == "Not found"
        assert data["instance"] == "/test"

    @pytest.mark.asyncio
    async def test_unknown_status_code_produces_fallback_type(self, mock_request):
        """Test that unknown status codes get a generated URN fallback."""
        from fastapi import HTTPException

        exc = HTTPException(status_code=418, detail="I'm a teapot")
        response = await http_exception_handler(mock_request, exc)

        import json
        data = json.loads(response.body)

        assert data["type"] == "urn:vfsbot:error:http-418"
        assert data["title"] == "Error"
        assert data["status"] == 418

    @pytest.mark.asyncio
    async def test_response_media_type_is_problem_json(self, mock_request):
        """Test that response uses application/problem+json media type."""
        from fastapi import HTTPException

        exc = HTTPException(status_code=400, detail="Bad request")
        response = await http_exception_handler(mock_request, exc)

        assert response.media_type == "application/problem+json"

    @pytest.mark.asyncio
    async def test_non_string_detail_is_stringified(self, mock_request):
        """Test that non-string detail values are converted to strings."""
        from fastapi import HTTPException

        exc = HTTPException(status_code=400, detail={"code": "INVALID"})
        response = await http_exception_handler(mock_request, exc)

        import json
        data = json.loads(response.body)

        assert isinstance(data["detail"], str)

    @pytest.mark.asyncio
    async def test_exc_headers_included_in_response(self, mock_request):
        """Test that exception headers are forwarded to the response."""
        from fastapi import HTTPException

        exc = HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )
        response = await http_exception_handler(mock_request, exc)

        assert response.headers.get("www-authenticate") == "Bearer"

    @pytest.mark.asyncio
    async def test_all_known_status_codes(self, mock_request):
        """Test that all known status codes produce RFC 7807 responses."""
        from fastapi import HTTPException

        for code in _ERROR_TYPES:
            exc = HTTPException(status_code=code, detail="test")
            response = await http_exception_handler(mock_request, exc)

            import json
            data = json.loads(response.body)

            assert data["status"] == code
            assert data["type"] == _ERROR_TYPES[code]
            assert data["title"] == _ERROR_TITLES[code]


class TestValidationExceptionHandler:
    """Tests for validation_exception_handler."""

    @pytest.mark.asyncio
    async def test_validation_error_format(self, mock_request):
        """Test that validation errors produce RFC 7807 compliant responses."""
        errors = [
            {"loc": ("body", "email"), "msg": "field required", "type": "value_error.missing"}
        ]
        exc = MagicMock(spec=RequestValidationError)
        exc.errors.return_value = errors

        response = await validation_exception_handler(mock_request, exc)

        import json
        data = json.loads(response.body)

        assert response.status_code == 422
        assert data["type"] == "urn:vfsbot:error:validation"
        assert data["title"] == "Validation Error"
        assert data["status"] == 422
        assert data["detail"] == "Request validation failed"
        assert data["instance"] == "/test"
        assert "errors" in data
        assert data["errors"]["email"] == "field required"

    @pytest.mark.asyncio
    async def test_validation_response_media_type(self, mock_request):
        """Test that validation response uses application/problem+json."""
        exc = MagicMock(spec=RequestValidationError)
        exc.errors.return_value = []

        response = await validation_exception_handler(mock_request, exc)

        assert response.media_type == "application/problem+json"

    @pytest.mark.asyncio
    async def test_body_loc_is_excluded_from_field_name(self, mock_request):
        """Test that 'body' location prefix is stripped from field names."""
        errors = [
            {"loc": ("body", "user", "email"), "msg": "invalid email", "type": "value_error"}
        ]
        exc = MagicMock(spec=RequestValidationError)
        exc.errors.return_value = errors

        response = await validation_exception_handler(mock_request, exc)

        import json
        data = json.loads(response.body)

        assert "user.email" in data["errors"]
        assert "body" not in data["errors"]

    @pytest.mark.asyncio
    async def test_multiple_validation_errors(self, mock_request):
        """Test that multiple validation errors are all included."""
        errors = [
            {"loc": ("body", "email"), "msg": "field required", "type": "value_error.missing"},
            {"loc": ("body", "password"), "msg": "too short", "type": "value_error"},
        ]
        exc = MagicMock(spec=RequestValidationError)
        exc.errors.return_value = errors

        response = await validation_exception_handler(mock_request, exc)

        import json
        data = json.loads(response.body)

        assert "email" in data["errors"]
        assert "password" in data["errors"]
