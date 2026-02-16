"""Captcha-related constants."""

from typing import Final


class CaptchaConfig:
    """Captcha configuration."""

    MANUAL_TIMEOUT: Final[int] = 120
    TWOCAPTCHA_TIMEOUT: Final[int] = 180
    TURNSTILE_TIMEOUT: Final[int] = 120
