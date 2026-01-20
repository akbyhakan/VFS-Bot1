"""Middleware package for VFS-Bot web application."""

from .security_headers import SecurityHeadersMiddleware

__all__ = ["SecurityHeadersMiddleware"]
