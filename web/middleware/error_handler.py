"""Global error handling middleware for VFS-Bot web application."""

import traceback
from typing import Callable, cast

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.exceptions import (
    AuthenticationError,
    DatabaseError,
    RateLimitError,
    ValidationError,
    VFSBotError,
)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware with consistent JSON responses.

    Catches all unhandled exceptions and returns structured JSON error responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and handle any exceptions.

        Args:
            request: FastAPI request
            call_next: Next middleware/handler in chain

        Returns:
            Response object
        """
        try:
            response = await call_next(request)
            return cast(Response, response)
        except ValidationError as e:
            # Handle validation errors (400)
            return self._handle_validation_error(e, request)
        except AuthenticationError as e:
            # Handle authentication errors (401)
            return self._handle_auth_error(e, request)
        except DatabaseError as e:
            # Handle database errors (500)
            return self._handle_database_error(e, request)
        except RateLimitError as e:
            # Handle rate limit errors (429)
            return self._handle_rate_limit_error(e, request)
        except VFSBotError as e:
            # Handle known VFSBot exceptions
            return self._handle_vfsbot_error(e, request)
        except Exception as e:
            # Handle unexpected errors (500)
            return self._handle_unexpected_error(e, request)

    def _handle_vfsbot_error(self, error: VFSBotError, request: Request) -> JSONResponse:
        """Handle VFSBot-specific errors with RFC 7807 format."""
        logger.error(
            f"VFSBot error: {error.__class__.__name__}: {error.message} "
            f"(recoverable={error.recoverable})",
            extra={"path": request.url.path},
        )

        status_code = error._get_http_status()

        # Build RFC 7807 response
        content = {
            "type": error.error_type_uri,
            "title": error.title,
            "status": status_code,
            "detail": error.message,
            "instance": request.url.path,
            "recoverable": error.recoverable,
        }

        # Add extension members from details
        if error.details:
            content.update(error.details)

        return JSONResponse(
            status_code=status_code,
            content=content,
            media_type="application/problem+json",
        )

    def _handle_validation_error(self, error: ValidationError, request: Request) -> JSONResponse:
        """Handle validation errors with RFC 7807 format."""
        logger.warning(
            f"Validation error: {error.message}",
            extra={"path": request.url.path, "field": error.field},
        )

        content = {
            "type": error.error_type_uri,
            "title": error.title,
            "status": 400,
            "detail": error.message,
            "instance": request.url.path,
        }

        # Add field as extension member if present
        if error.field:
            content["field"] = error.field

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=content,
            media_type="application/problem+json",
        )

    def _handle_auth_error(self, error: AuthenticationError, request: Request) -> JSONResponse:
        """Handle authentication errors with RFC 7807 format."""
        logger.warning(f"Authentication error: {error.message}", extra={"path": request.url.path})

        content = {
            "type": error.error_type_uri,
            "title": error.title,
            "status": 401,
            "detail": error.message,
            "instance": request.url.path,
        }

        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=content,
            headers={"WWW-Authenticate": "Bearer"},
            media_type="application/problem+json",
        )

    def _handle_database_error(self, error: DatabaseError, request: Request) -> JSONResponse:
        """Handle database errors with RFC 7807 format."""
        logger.error(
            f"Database error: {error.message}",
            extra={"path": request.url.path, "details": error.details},
        )

        content = {
            "type": error.error_type_uri,
            "title": error.title,
            "status": 500,
            "detail": error.message,
            "instance": request.url.path,
            "recoverable": error.recoverable,
        }

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=content,
            media_type="application/problem+json",
        )

    def _handle_rate_limit_error(self, error: RateLimitError, request: Request) -> JSONResponse:
        """Handle rate limit errors with RFC 7807 format."""
        client_host = request.client.host if request.client else "unknown"
        logger.warning(f"Rate limit exceeded for {client_host}", extra={"path": request.url.path})

        headers = {}
        if error.retry_after:
            headers["Retry-After"] = str(error.retry_after)

        content = {
            "type": error.error_type_uri,
            "title": error.title,
            "status": 429,
            "detail": error.message,
            "instance": request.url.path,
            "recoverable": True,
        }

        # Add retry_after as extension member
        if error.retry_after:
            content["retry_after"] = error.retry_after

        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=content,
            headers=headers,
            media_type="application/problem+json",
        )

    def _handle_unexpected_error(self, error: Exception, request: Request) -> JSONResponse:
        """Handle unexpected errors with RFC 7807 format. Must not leak internal details."""
        # Log full traceback for debugging
        logger.error(
            f"Unexpected error: {str(error)}",
            extra={"path": request.url.path, "traceback": traceback.format_exc()},
        )

        # Return generic error message (don't leak internal details)
        content = {
            "type": "urn:vfsbot:error:internal-server",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "An unexpected error occurred. Please try again later.",
            "instance": request.url.path,
        }

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=content,
            media_type="application/problem+json",
        )
