# Middleware Architecture

## Overview

This document clarifies the middleware architecture and separation of concerns in VFS-Bot.

## Directory Structure

### `web/middleware/` - HTTP Middleware Only

The `web/middleware/` directory contains **HTTP-specific middleware** for the FastAPI web application:

- **Error Handler** (`web/middleware/error_handler.py`) - Global error handling with RFC 7807 JSON responses
- **Security Headers** (`web/middleware/security_headers.py`) - X-Frame-Options, X-Content-Type-Options, etc.

**Purpose**: These middleware components operate at the HTTP request/response layer and are specific to the web API.

### `src/middleware/` - DO NOT CREATE

❌ **IMPORTANT**: Do NOT create a `src/middleware/` directory.

General cross-cutting concerns should be implemented as services or utilities, not as a separate middleware layer.

## Middleware Stack

The application uses three middleware components (in registration order):

1. **`ErrorHandlerMiddleware`** (`web/middleware/error_handler.py`) — Catches all unhandled exceptions and returns structured RFC 7807 JSON error responses.
2. **`SecurityHeadersMiddleware`** (`web/middleware/security_headers.py`) — Adds security headers (X-Frame-Options, X-Content-Type-Options, etc.) to all responses.
3. **`CORSMiddleware`** (FastAPI built-in) — Cross-Origin Resource Sharing configuration.

## Cross-Cutting Concerns Mapping

Common cross-cutting concerns are handled in the following locations:

| Concern | Location | Module/Class |
|---------|----------|--------------|
| Rate Limiting (In-Memory) | `src/core/rate_limiting/` | `RateLimiter` (sliding_window) |
| Rate Limiting (Redis-backed) | `src/core/rate_limiting/` | `AuthRateLimiter` (auth_limiter) |
| Rate Limiting (Adaptive) | `src/core/rate_limiting/` | `AdaptiveRateLimiter` (adaptive) |
| Rate Limiting (Endpoint) | `src/core/rate_limiting/` | `EndpointRateLimiter` (endpoint) |
| Circuit Breaker | `src/core/infra/circuit_breaker.py` | `CircuitBreaker` |
| Request Retry Logic | `src/utils/anti_detection/` | `TLSHandler.make_request()` |
| Authentication | `src/core/auth/` | `AuthManager` (`__init__.py`, `jwt_tokens.py`, `password.py`, `token_blacklist.py`) |
| Session Management | `src/utils/security/` | `SessionManager` |
| Header Management | `src/utils/security/` | `HeaderManager` |
| Proxy Management | `src/utils/security/` | `ProxyManager` |
| Error Capture | `src/utils/error_capture.py` | `ErrorCapture` |
| Logging | `src/core/logger.py` | `setup_structured_logging()` |
| Notification Service | `src/services/notification.py` | `NotificationService` |

## Best Practices

1. **HTTP Middleware**: Place in `web/middleware/` if it operates on HTTP requests/responses
2. **Business Logic**: Place in `src/services/` if it's domain-specific
3. **Cross-Cutting Utilities**: Place in `src/utils/` if it's a reusable utility
4. **Core Infrastructure**: Place in `src/core/` if it's fundamental infrastructure

## Examples

### ✅ Correct: HTTP Middleware

```python
# web/middleware/cors.py
from fastapi.middleware.cors import CORSMiddleware

def add_cors_middleware(app, origins):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

### ✅ Correct: Rate Limiting Utility

```python
# src/core/rate_limiting/sliding_window.py
class RateLimiter:
    """Token bucket rate limiter for API calls."""
    
    async def acquire(self) -> None:
        """Wait until rate limit allows a request."""
        # Implementation...
```

### ❌ Incorrect: General Middleware

```python
# src/middleware/rate_limiter.py  # DON'T DO THIS
# This should be in src/utils/security/ or src/core/
```

## Rationale

**Why separate HTTP middleware from general utilities?**

1. **Clarity**: HTTP middleware is tied to the web framework (FastAPI)
2. **Reusability**: Core utilities can be used in CLI, background tasks, etc.
3. **Testing**: Easier to test utilities without HTTP context
4. **Dependency Management**: Avoid coupling core logic to web frameworks

## Migration Notes

If you find middleware-like code outside of `web/middleware/`, consider:

1. Is it HTTP-specific? → Move to `web/middleware/`
2. Is it a reusable utility? → Move to `src/utils/`
3. Is it core infrastructure? → Move to `src/core/`
4. Is it business logic? → Move to `src/services/`

Never create `src/middleware/` as a catch-all directory.
