"""OTP-related constants."""

from typing import Final


class OTP:
    """OTP service configuration."""

    MAX_ENTRIES: Final[int] = 100
    TIMEOUT_SECONDS: Final[int] = 300
    CLEANUP_INTERVAL_SECONDS: Final[int] = 60


class BookingOTPSelectors:
    """Selectors for booking OTP verification screens (country-specific)."""

    # OTP Generate button (Turkish and English)
    GENERATE_BUTTON: Final[str] = (
        'span.mdc-button__label:has-text("Tek Seferlik Şifre (OTP) Oluştur"), '
        'span.mdc-button__label:has-text("Generate One Time Password")'
    )

    # OTP input field
    INPUT_FIELD: Final[str] = 'input[placeholder="OTP"][maxlength="6"]'

    # Verify button (Turkish and English)
    VERIFY_BUTTON: Final[str] = (
        'span.mdc-button__label:has-text("Doğrula"), ' 'span.mdc-button__label:has-text("Verify")'
    )

    # Success message (Turkish and English regex)
    SUCCESS_MESSAGE: Final[str] = "text=/OTP doğrulaması başarılı|OTP verification successful/i"

    # Continue button (Turkish and English)
    CONTINUE_BUTTON: Final[str] = (
        'span.mdc-button__label:has-text("Devam Et"), '
        'span.mdc-button__label:has-text("Continue")'
    )
