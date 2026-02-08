"""Tests for booking package structure and backward compatibility."""

import pytest
import warnings


class TestBookingPackageStructure:
    """Test the new modular booking package structure."""

    def test_can_import_from_booking_package(self):
        """Verify all public symbols importable from booking package."""
        from src.services.booking import (
            AppointmentBookingService,
            BookingOrchestrator,
            FormFiller,
            SlotSelector,
            PaymentHandler,
            BookingValidator,
            get_selector,
            get_selector_with_fallback,
            resolve_selector,
            try_selectors,
            TURKISH_MONTHS,
            DOUBLE_MATCH_PATTERNS,
        )

        # Verify classes exist
        assert AppointmentBookingService is not None
        assert BookingOrchestrator is not None
        assert FormFiller is not None
        assert SlotSelector is not None
        assert PaymentHandler is not None
        assert BookingValidator is not None

        # Verify functions exist
        assert callable(get_selector)
        assert callable(get_selector_with_fallback)
        assert callable(resolve_selector)
        assert callable(try_selectors)

        # Verify constants exist
        assert isinstance(TURKISH_MONTHS, dict)
        assert isinstance(DOUBLE_MATCH_PATTERNS, list)

    def test_appointment_booking_service_is_alias(self):
        """Verify AppointmentBookingService is an alias for BookingOrchestrator."""
        from src.services.booking import AppointmentBookingService, BookingOrchestrator

        assert AppointmentBookingService is BookingOrchestrator

    def test_booking_orchestrator_initialization(self):
        """Test BookingOrchestrator can be initialized."""
        from src.services.booking import BookingOrchestrator

        config = {"vfs": {"form_wait_seconds": 21}}
        service = BookingOrchestrator(config=config)

        assert service.config == config
        assert service.form_filler is not None
        assert service.slot_selector is not None
        assert service.payment_handler is not None
        assert service.validator is not None

    def test_form_filler_initialization(self):
        """Test FormFiller can be initialized."""
        from src.services.booking import FormFiller

        config = {"vfs": {"form_wait_seconds": 21}}
        filler = FormFiller(config=config)

        assert filler.config == config

    def test_slot_selector_initialization(self):
        """Test SlotSelector can be initialized."""
        from src.services.booking import SlotSelector

        selector = SlotSelector()
        assert selector.captcha_solver is None

    def test_payment_handler_initialization(self):
        """Test PaymentHandler can be initialized."""
        from src.services.booking import PaymentHandler

        config = {"payment": {}}
        handler = PaymentHandler(config=config)

        assert handler.config == config

    def test_booking_validator_initialization(self):
        """Test BookingValidator can be initialized."""
        from src.services.booking import BookingValidator

        validator = BookingValidator()
        assert validator is not None

    def test_turkish_months_constant(self):
        """Test TURKISH_MONTHS constant has expected values."""
        from src.services.booking import TURKISH_MONTHS

        assert TURKISH_MONTHS["Ocak"] == "01"
        assert TURKISH_MONTHS["Aralık"] == "12"
        assert len(TURKISH_MONTHS) == 12

    def test_double_match_patterns_constant(self):
        """Test DOUBLE_MATCH_PATTERNS constant has expected format."""
        from src.services.booking import DOUBLE_MATCH_PATTERNS

        assert len(DOUBLE_MATCH_PATTERNS) == 2
        assert all(isinstance(p, str) for p in DOUBLE_MATCH_PATTERNS)


class TestBackwardCompatibility:
    """Test backward compatibility with old imports."""

    def test_deprecated_module_import_shows_warning(self):
        """Verify importing from old module shows deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Import from old module
            from src.services.appointment_booking_service import AppointmentBookingService
            
            # Check warning was raised
            assert len(w) > 0
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "booking" in str(w[0].message).lower()

    def test_old_import_provides_same_class(self):
        """Verify old import provides the same class as new import."""
        # Suppress deprecation warnings for this test
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            
            from src.services.appointment_booking_service import AppointmentBookingService as OldService
            from src.services.booking import AppointmentBookingService as NewService

            assert OldService is NewService

    def test_old_import_get_selector(self):
        """Verify get_selector importable from old module."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            
            from src.services.appointment_booking_service import get_selector
            
            assert callable(get_selector)

    def test_old_import_get_selector_with_fallback(self):
        """Verify get_selector_with_fallback importable from old module."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            
            from src.services.appointment_booking_service import get_selector_with_fallback
            
            assert callable(get_selector_with_fallback)

    def test_old_import_resolve_selector(self):
        """Verify resolve_selector importable from old module."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            
            from src.services.appointment_booking_service import resolve_selector
            
            assert callable(resolve_selector)

    def test_old_import_try_selectors(self):
        """Verify try_selectors importable from old module."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            
            from src.services.appointment_booking_service import try_selectors
            
            assert callable(try_selectors)

    def test_old_module_all_exports(self):
        """Verify __all__ in old module contains expected exports."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            
            import src.services.appointment_booking_service as old_module
            
            expected = [
                "AppointmentBookingService",
                "get_selector",
                "get_selector_with_fallback",
                "resolve_selector",
                "try_selectors",
            ]
            
            assert hasattr(old_module, "__all__")
            assert set(old_module.__all__) == set(expected)


class TestComponentIntegration:
    """Test that components work together correctly."""

    def test_orchestrator_has_all_components(self):
        """Test orchestrator contains all required components."""
        from src.services.booking import BookingOrchestrator

        config = {"vfs": {"form_wait_seconds": 21}}
        orchestrator = BookingOrchestrator(config=config)

        # Verify components exist
        assert hasattr(orchestrator, "form_filler")
        assert hasattr(orchestrator, "slot_selector")
        assert hasattr(orchestrator, "payment_handler")
        assert hasattr(orchestrator, "validator")

        # Verify they're the right types
        from src.services.booking import FormFiller, SlotSelector, PaymentHandler, BookingValidator

        assert isinstance(orchestrator.form_filler, FormFiller)
        assert isinstance(orchestrator.slot_selector, SlotSelector)
        assert isinstance(orchestrator.payment_handler, PaymentHandler)
        assert isinstance(orchestrator.validator, BookingValidator)

    def test_normalize_date_in_validator(self):
        """Test normalize_date method in validator."""
        from src.services.booking import BookingValidator

        validator = BookingValidator()
        
        # Test date normalization
        assert validator.normalize_date("01-01-2024") == "01/01/2024"
        assert validator.normalize_date("15-06-2024") == "15/06/2024"
        assert validator.normalize_date("31-12-2024") == "31/12/2024"


class TestSelectorUtils:
    """Test selector utility functions."""

    def test_resolve_selector_returns_list(self):
        """Test resolve_selector returns a list."""
        from src.services.booking import resolve_selector

        # Even for unknown selectors, should return list
        result = resolve_selector("unknown_selector")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_get_selector_returns_string(self):
        """Test get_selector returns a string."""
        from src.services.booking import get_selector

        # Should return first selector from list
        result = get_selector("unknown_selector")
        assert isinstance(result, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
