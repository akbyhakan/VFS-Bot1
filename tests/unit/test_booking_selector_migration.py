"""Test suite to verify VFS_SELECTORS migration to config/selectors.yaml."""

import pytest

from src.selector import get_selector_manager
from src.services.booking import (
    get_selector,
    get_selector_with_fallback,
    resolve_selector,
)


class TestBookingSelectorMigration:
    """Test booking selector migration from VFS_SELECTORS to YAML config."""

    def test_all_booking_selectors_accessible(self):
        """Verify all 35 booking selectors are accessible via manager."""
        manager = get_selector_manager()

        # List of all selector keys that should exist
        selector_keys = [
            # Form fields
            "first_name",
            "last_name",
            "gender_dropdown",
            "gender_female",
            "gender_male",
            "birth_date",
            "nationality_dropdown",
            "nationality_turkey",
            "passport_number",
            "passport_expiry",
            "phone_code",
            "phone_number",
            "email",
            "child_checkbox",
            # Buttons
            "save_button",
            "add_another_button",
            "continue_button",
            "back_button",
            "online_pay_button",
            # Calendar
            "available_date_cell",
            "time_slot_button",
            "load_more_times",
            "next_month_button",
            # Checkboxes
            "terms_checkbox",
            "waitlist_checkbox",
            "terms_consent_checkbox",
            "marketing_consent_checkbox",
            "waitlist_consent_checkbox",
            "confirm_button",
            "waitlist_success_indicator",
            # Payment
            "card_number",
            "expiry_month",
            "expiry_year",
            "cvv",
            "payment_submit",
            # OTP
            "otp_input",
            "otp_submit",
            # UI elements
            "overlay",
            "captcha_modal",
            "captcha_submit",
        ]

        # Test each selector can be retrieved
        for key in selector_keys:
            result = manager.get_all(f"booking.{key}")
            assert result, f"Selector booking.{key} should exist and have at least one value"

    def test_resolve_selector_with_flat_keys(self):
        """Test resolve_selector works with flat keys (backward compatibility)."""
        # Test with form field
        result = resolve_selector("first_name")
        assert result == [
            "#mat-input-3",
            'input[formcontrolname="firstName"]',
            'input[name="firstName"]',
        ]

        # Test with button
        result = resolve_selector("continue_button")
        assert len(result) == 3
        assert result[0] == '//button[contains(., "Devam et")]'

    def test_resolve_selector_with_dot_path(self):
        """Test resolve_selector works with dot-path keys."""
        result = resolve_selector("booking.first_name")
        assert result == [
            "#mat-input-3",
            'input[formcontrolname="firstName"]',
            'input[name="firstName"]',
        ]

    def test_get_selector_returns_primary(self):
        """Test get_selector returns the primary selector."""
        # Test with simple field
        result = get_selector("first_name")
        assert result == "#mat-input-3"

        # Test with button
        result = get_selector("continue_button")
        assert result == '//button[contains(., "Devam et")]'

        # Test with string-only selector (no fallbacks)
        result = get_selector("gender_male")
        assert result == '//mat-option[contains(., "Male")]'

    def test_get_selector_with_fallback_returns_list(self):
        """Test get_selector_with_fallback returns list of selectors."""
        result = get_selector_with_fallback("first_name")
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == "#mat-input-3"

    def test_get_selector_with_fallback_raises_on_unknown(self):
        """Test get_selector_with_fallback raises ValueError for unknown selector."""
        with pytest.raises(ValueError, match="Unknown selector name"):
            get_selector_with_fallback("nonexistent_selector_xyz")

    def test_selector_fallback_order_preserved(self):
        """Test that fallback order is preserved from YAML config."""
        manager = get_selector_manager()

        # email should have 3 fallbacks in specific order
        result = manager.get_all("booking.email")
        assert len(result) == 4  # primary + 3 fallbacks
        assert result[0] == "#mat-input-8"
        assert result[1] == 'input[formcontrolname="email"]'
        assert result[2] == 'input[name="email"]'
        assert result[3] == 'input[type="email"]'

    def test_waitlist_selectors_available(self):
        """Test waitlist-specific selectors are available."""
        # These are critical for waitlist flow
        waitlist_keys = [
            "waitlist_checkbox",
            "terms_consent_checkbox",
            "marketing_consent_checkbox",
            "waitlist_consent_checkbox",
            "confirm_button",
            "waitlist_success_indicator",
        ]

        for key in waitlist_keys:
            result = get_selector(key)
            assert result, f"Waitlist selector {key} should exist"

    def test_payment_selectors_available(self):
        """Test payment-related selectors are available."""
        payment_keys = [
            "card_number",
            "expiry_month",
            "expiry_year",
            "cvv",
            "payment_submit",
            "otp_input",
            "otp_submit",
        ]

        for key in payment_keys:
            result = get_selector(key)
            assert result, f"Payment selector {key} should exist"

    def test_calendar_selectors_available(self):
        """Test calendar-related selectors are available."""
        calendar_keys = [
            "available_date_cell",
            "time_slot_button",
            "load_more_times",
            "next_month_button",
        ]

        for key in calendar_keys:
            result = get_selector(key)
            assert result, f"Calendar selector {key} should exist"

    def test_manager_get_all_method(self):
        """Test the new get_all() method on CountryAwareSelectorManager."""
        manager = get_selector_manager()

        # Test with selector that has fallbacks
        result = manager.get_all("booking.first_name")
        assert isinstance(result, list)
        assert len(result) == 3

        # Test with string-only selector
        result = manager.get_all("booking.gender_male")
        assert isinstance(result, list)
        assert len(result) == 1

        # Test with nonexistent selector
        result = manager.get_all("booking.nonexistent")
        assert result == []
