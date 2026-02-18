"""Tests for PR integration fixes: encapsulation, rotation, and PageStateDetector."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


class TestBrowserManagerEncapsulation:
    """Test BrowserManager encapsulation fixes."""

    @pytest.mark.asyncio
    async def test_force_restart_on_next_cycle(self):
        """Test force_restart_on_next_cycle method triggers restart."""
        from src.services.bot.browser_manager import BrowserManager

        config = {
            "bot": {"headless": True, "browser_restart_after_pages": 100},
            "anti_detection": {"enabled": False},
        }
        manager = BrowserManager(config)

        # Call force_restart_on_next_cycle
        manager.force_restart_on_next_cycle()

        # Verify it triggers restart through public interface
        # should_restart() increments page count, so we check if it returns True
        should_restart = await manager.should_restart()
        assert should_restart is True


class TestBrowserManagerRotationDeferral:
    """Test fingerprint rotation deferral logic."""

    def test_needs_rotation_flag_initialization(self):
        """Test that _needs_rotation flag is initialized."""
        from src.services.bot.browser_manager import BrowserManager

        config = {
            "bot": {"headless": True},
            "anti_detection": {"enabled": True},
        }
        manager = BrowserManager(config)

        # Flag should be initialized to False
        assert hasattr(manager, "_needs_rotation")
        assert manager._needs_rotation is False

    @pytest.mark.asyncio
    async def test_should_restart_checks_rotation_flag(self):
        """Test that should_restart checks _needs_rotation flag."""
        from src.services.bot.browser_manager import BrowserManager

        config = {
            "bot": {"headless": True, "browser_restart_after_pages": 100},
            "anti_detection": {"enabled": True},
        }
        manager = BrowserManager(config)

        # Set rotation flag
        manager._needs_rotation = True

        # should_restart should return True
        result = await manager.should_restart()
        assert result is True

    @pytest.mark.asyncio
    async def test_restart_fresh_clears_rotation_flag(self):
        """Test that restart_fresh clears _needs_rotation flag."""
        from src.services.bot.browser_manager import BrowserManager

        config = {
            "bot": {"headless": True},
            "anti_detection": {"enabled": True},
        }
        manager = BrowserManager(config)

        # Set flag
        manager._needs_rotation = True

        # Mock the methods to avoid actual browser operations
        with patch.object(manager, "close", new_callable=AsyncMock):
            with patch.object(manager, "start", new_callable=AsyncMock):
                await manager.restart_fresh()

        # Flag should be cleared
        assert manager._needs_rotation is False


class TestPageStateDetectorIntegration:
    """Test PageStateDetector integration in service context."""

    def test_page_state_detector_in_workflow_context(self):
        """Test that PageStateDetector is included in WorkflowServicesContext."""
        from src.services.bot.page_state_detector import PageStateDetector
        from src.services.bot.service_context import WorkflowServicesContext

        # Create mock services
        mock_auth = Mock()
        mock_slot_checker = Mock()
        mock_booking = Mock()
        mock_waitlist = Mock()
        mock_error = Mock()
        mock_detector = Mock(spec=PageStateDetector)

        # Create context with page_state_detector
        context = WorkflowServicesContext(
            auth_service=mock_auth,
            slot_checker=mock_slot_checker,
            booking_service=mock_booking,
            waitlist_handler=mock_waitlist,
            error_handler=mock_error,
            page_state_detector=mock_detector,
            payment_service=None,
            alert_service=None,
        )

        # Verify it's present
        assert context.page_state_detector is mock_detector

    def test_booking_workflow_accepts_page_state_detector(self):
        """Test that BookingWorkflow accepts page_state_detector parameter."""
        from src.services.bot.booking_workflow import BookingWorkflow
        from src.services.bot.page_state_detector import PageStateDetector

        # Create mock dependencies
        config = {"bot": {}}
        db = Mock()
        notifier = Mock()
        auth_service = Mock()
        slot_checker = Mock()
        booking_service = Mock()
        waitlist_handler = Mock()
        error_handler = Mock()
        slot_analyzer = Mock()
        session_recovery = Mock()
        page_state_detector = Mock(spec=PageStateDetector)

        # Create BookingWorkflow with page_state_detector
        workflow = BookingWorkflow(
            config=config,
            db=db,
            notifier=notifier,
            auth_service=auth_service,
            slot_checker=slot_checker,
            booking_service=booking_service,
            waitlist_handler=waitlist_handler,
            error_handler=error_handler,
            slot_analyzer=slot_analyzer,
            session_recovery=session_recovery,
            page_state_detector=page_state_detector,
        )

        # Verify it's stored
        assert workflow.page_state_detector is page_state_detector


class TestImportOrder:
    """Test that imports are properly ordered in booking_workflow.py."""

    def test_booking_workflow_imports_structure(self):
        """Test that booking_workflow.py has proper import structure."""
        import inspect

        from src.services.bot import booking_workflow

        # Get source code
        source = inspect.getsource(booking_workflow)
        lines = source.split("\n")

        # Find the function definition
        func_line = None
        for i, line in enumerate(lines):
            if "def _is_recoverable_vfs_error" in line:
                func_line = i
                break

        assert func_line is not None, "_is_recoverable_vfs_error function not found"

        # Check that no imports appear after the function
        # (before the class definition)
        class_line = None
        for i, line in enumerate(lines):
            if "class BookingWorkflow" in line:
                class_line = i
                break

        assert class_line is not None, "BookingWorkflow class not found"
        assert func_line < class_line, "Function should be before class"

        # Check no imports between function and class
        between_lines = lines[func_line:class_line]
        for line in between_lines:
            stripped = line.strip()
            if stripped.startswith("from ") or stripped.startswith("import "):
                pytest.fail(f"Found import after function definition: {line}")
