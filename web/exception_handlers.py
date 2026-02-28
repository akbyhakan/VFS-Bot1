"""RFC 7807 Problem Details exception handlers for FastAPI."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

_ERROR_TYPES = {
    400: "urn:vfsbot:error:bad-request",
    401: "urn:vfsbot:error:unauthorized",
    403: "urn:vfsbot:error:forbidden",
    404: "urn:vfsbot:error:not-found",
    409: "urn:vfsbot:error:conflict",
    422: "urn:vfsbot:error:validation",
    429: "urn:vfsbot:error:rate-limit",
    500: "urn:vfsbot:error:internal-server",
    503: "urn:vfsbot:error:service-unavailable",
}

_ERROR_TITLES = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    422: "Validation Error",
    429: "Too Many Requests",
    500: "Internal Server Error",
    503: "Service Unavailable",
}


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Convert FastAPI HTTPException to RFC 7807 Problem Details format."""
    status_code = exc.status_code

    content = {
        "type": _ERROR_TYPES.get(status_code, f"urn:vfsbot:error:http-{status_code}"),
        "title": _ERROR_TITLES.get(status_code, "Error"),
        "status": status_code,
        "detail": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
        "instance": request.url.path,
    }

    headers = getattr(exc, "headers", None) or {}

    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=headers,
        media_type="application/problem+json",
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convert Pydantic validation errors to RFC 7807 format."""
    errors = {}
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        errors[field] = error["msg"]

    return JSONResponse(
        status_code=422,
        content={
            "type": "urn:vfsbot:error:validation",
            "title": "Validation Error",
            "status": 422,
            "detail": "Request validation failed",
            "instance": request.url.path,
            "errors": errors,
        },
        media_type="application/problem+json",
    )
