"""Tests for utils/decorators module."""

import asyncio

import pytest

from src.core.exceptions import VFSBotError
from src.utils.decorators import handle_errors


class TestHandleErrors:
    """Tests for handle_errors decorator."""

    @pytest.mark.asyncio
    async def test_handle_errors_async_success(self):
        """Test handle_errors with successful async function."""

        @handle_errors("test_operation")
        async def successful_func():
            return "success"

        result = await successful_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_handle_errors_async_failure_reraise(self):
        """Test handle_errors with async function that raises."""

        @handle_errors("test_operation", reraise=True)
        async def failing_func():
            raise ValueError("Test error")

        with pytest.raises(VFSBotError):
            await failing_func()

    @pytest.mark.asyncio
    async def test_handle_errors_async_failure_no_reraise(self):
        """Test handle_errors without reraising."""

        @handle_errors("test_operation", reraise=False)
        async def failing_func():
            raise ValueError("Test error")

        result = await failing_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_errors_async_with_vfsbot_error(self):
        """Test handle_errors with VFSBotError (should passthrough)."""

        @handle_errors("test_operation")
        async def func_with_vfsbot_error():
            raise VFSBotError("Already handled error")

        with pytest.raises(VFSBotError) as exc_info:
            await func_with_vfsbot_error()
        assert "Already handled error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handle_errors_async_cancelled(self):
        """Test handle_errors with CancelledError."""

        @handle_errors("test_operation")
        async def cancelled_func():
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await cancelled_func()

    def test_handle_errors_sync_success(self):
        """Test handle_errors with successful sync function."""

        @handle_errors("test_operation")
        def successful_func():
            return "success"

        result = successful_func()
        assert result == "success"

    def test_handle_errors_sync_failure_reraise(self):
        """Test handle_errors with sync function that raises."""

        @handle_errors("test_operation", reraise=True)
        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(VFSBotError):
            failing_func()

    def test_handle_errors_sync_failure_no_reraise(self):
        """Test handle_errors with sync function without reraising."""

        @handle_errors("test_operation", reraise=False)
        def failing_func():
            raise ValueError("Test error")

        result = failing_func()
        assert result is None

    def test_handle_errors_sync_with_vfsbot_error(self):
        """Test handle_errors with VFSBotError in sync function."""

        @handle_errors("test_operation")
        def func_with_vfsbot_error():
            raise VFSBotError("Already handled error")

        with pytest.raises(VFSBotError):
            func_with_vfsbot_error()

    @pytest.mark.asyncio
    async def test_handle_errors_with_warning_level(self):
        """Test handle_errors with warning log level."""

        @handle_errors("test_operation", reraise=False, log_level="warning")
        async def failing_func():
            raise ValueError("Test error")

        result = await failing_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_errors_preserves_function_name(self):
        """Test that decorator preserves function metadata."""

        @handle_errors("test_operation")
        async def my_async_function():
            """My docstring."""
            return "test"

        assert my_async_function.__name__ == "my_async_function"
        assert my_async_function.__doc__ == "My docstring."


class TestHandleErrorsWithoutWrapping:
    """Tests for handle_errors decorator with wrap_error=False (replaces old log_errors)."""

    @pytest.mark.asyncio
    async def test_handle_errors_no_wrap_success(self):
        """Test handle_errors without error wrapping with successful function."""

        @handle_errors(wrap_error=False)
        async def successful_func():
            return "success"

        result = await successful_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_handle_errors_no_wrap_failure_reraise(self):
        """Test handle_errors without wrapping with function that raises."""

        @handle_errors(wrap_error=False, reraise=True)
        async def failing_func():
            raise ValueError("Test error")

        # Should reraise the original ValueError, not VFSBotError
        with pytest.raises(ValueError):
            await failing_func()

    @pytest.mark.asyncio
    async def test_handle_errors_no_wrap_failure_no_reraise(self):
        """Test handle_errors without wrapping and without reraising."""

        @handle_errors(wrap_error=False, reraise=False)
        async def failing_func():
            raise ValueError("Test error")

        result = await failing_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_errors_no_wrap_with_default_return(self):
        """Test handle_errors with custom default return value."""

        @handle_errors(wrap_error=False, reraise=False, default_return=[])
        async def failing_func():
            raise ValueError("Test error")

        result = await failing_func()
        assert result == []

    @pytest.mark.asyncio
    async def test_handle_errors_no_wrap_with_args(self):
        """Test handle_errors without wrapping with function that has arguments."""

        @handle_errors(wrap_error=False)
        async def func_with_args(a, b):
            return a + b

        result = await func_with_args(2, 3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_handle_errors_no_wrap_with_kwargs(self):
        """Test handle_errors without wrapping with keyword arguments."""

        @handle_errors(wrap_error=False)
        async def func_with_kwargs(a, b=10):
            return a + b

        result = await func_with_kwargs(5, b=7)
        assert result == 12

    @pytest.mark.asyncio
    async def test_handle_errors_no_wrap_preserves_function_name(self):
        """Test that decorator preserves function metadata."""

        @handle_errors(wrap_error=False)
        async def my_function():
            """My docstring."""
            return "test"

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."
