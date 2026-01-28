"""Captcha solving module with support for multiple providers.

DEPRECATED: This module is deprecated. Use src.services.captcha_solver instead.
This file exists only for backward compatibility and will be removed in a future version.
"""

import warnings
from src.services.captcha_solver import CaptchaSolver  # noqa: F401

warnings.warn(
    "src.captcha_solver is deprecated. Use src.services.captcha_solver instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export for backward compatibility
__all__ = ["CaptchaSolver"]
