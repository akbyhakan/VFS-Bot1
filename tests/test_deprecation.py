"""Tests for utils/deprecation module."""

import pytest
import warnings
from src.utils.deprecation import deprecated, deprecated_module


class TestDeprecatedDecorator:
    """Tests for deprecated decorator."""

    def test_deprecated_function_warns(self):
        """Test that deprecated function issues warning."""

        @deprecated("This is old")
        def old_function():
            return "result"

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = old_function()
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "old_function is deprecated" in str(w[0].message)
            assert "This is old" in str(w[0].message)
            assert result == "result"

    def test_deprecated_with_replacement(self):
        """Test deprecated decorator with replacement."""

        @deprecated("Old implementation", replacement="new_function")
        def old_func():
            return 42

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = old_func()
            assert len(w) == 1
            assert "Use new_function instead" in str(w[0].message)
            assert result == 42

    def test_deprecated_preserves_function_name(self):
        """Test that decorator preserves function metadata."""

        @deprecated("Old")
        def my_function():
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    def test_deprecated_with_args(self):
        """Test deprecated function with arguments."""

        @deprecated("Old version")
        def add(a, b):
            return a + b

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = add(2, 3)
            assert result == 5
            assert len(w) == 1

    def test_deprecated_with_kwargs(self):
        """Test deprecated function with keyword arguments."""

        @deprecated("Old version")
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}"

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = greet("Alice", greeting="Hi")
            assert result == "Hi, Alice"
            assert len(w) == 1

    def test_multiple_calls_warn_each_time(self):
        """Test that multiple calls issue warnings each time."""

        @deprecated("Old")
        def func():
            return True

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            func()
            func()
            func()
            assert len(w) == 3


class TestDeprecatedModule:
    """Tests for deprecated_module function."""

    def test_deprecated_module_warns(self):
        """Test that deprecated_module issues warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            deprecated_module("old.module", "new.module")
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "old.module is deprecated" in str(w[0].message)
            assert "Use new.module instead" in str(w[0].message)

    def test_deprecated_module_message_format(self):
        """Test deprecated_module message format."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            deprecated_module("src.old_service", "src.services.new_service")
            assert len(w) == 1
            msg = str(w[0].message)
            assert "src.old_service" in msg
            assert "src.services.new_service" in msg
