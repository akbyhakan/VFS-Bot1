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
        """Handle VFSBot-specific errors."""
        logger.error(
            f"VFSBot error: {error.__class__.__name__}: {error.message} "
            f"(recoverable={error.recoverable})",
            extra={"path": request.url.path},
        )

        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if not error.recoverable:
            status_code = status.HTTP_400_BAD_REQUEST

        return JSONResponse(
            status_code=status_code,
            content={
                "error": error.__class__.__name__,
                "message": error.message,
                "recoverable": error.recoverable,
                "details": error.details,
            },
        )

    def _handle_validation_error(self, error: ValidationError, request: Request) -> JSONResponse:
        """Handle validation errors."""
        logger.warning(
            f"Validation error: {error.message}",
            extra={"path": request.url.path, "field": error.field},
        )

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "ValidationError",
                "message": error.message,
                "field": error.field,
            },
        )

    def _handle_auth_error(self, error: AuthenticationError, request: Request) -> JSONResponse:
        """Handle authentication errors."""
        logger.warning(f"Authentication error: {error.message}", extra={"path": request.url.path})

        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": error.__class__.__name__,
                "message": error.message,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    def _handle_database_error(self, error: DatabaseError, request: Request) -> JSONResponse:
        """Handle database errors."""
        logger.error(
            f"Database error: {error.message}",
            extra={"path": request.url.path, "details": error.details},
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": error.__class__.__name__,
                "message": error.message,
                "recoverable": error.recoverable,
            },
        )

    def _handle_rate_limit_error(self, error: RateLimitError, request: Request) -> JSONResponse:
        """Handle rate limit errors."""
        client_host = request.client.host if request.client else "unknown"
        logger.warning(f"Rate limit exceeded for {client_host}", extra={"path": request.url.path})

        headers = {}
        if error.retry_after:
            headers["Retry-After"] = str(error.retry_after)

        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "RateLimitError",
                "message": error.message,
                "retry_after": error.retry_after,
            },
            headers=headers,
        )

    def _handle_unexpected_error(self, error: Exception, request: Request) -> JSONResponse:
        """Handle unexpected errors."""
        # Log full traceback for debugging
        logger.error(
            f"Unexpected error: {str(error)}",
            extra={"path": request.url.path, "traceback": traceback.format_exc()},
        )

        # Return generic error message (don't leak internal details)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred. Please try again later.",
            },
        )
