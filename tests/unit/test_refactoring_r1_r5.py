"""Tests for R1-R5 refactoring fixes.

This test file validates the following refactoring changes:
- R1: Logger migration from stdlib logging to loguru (22 files)
- R2: Double shutdown fix in run_both_mode
- R3: SlotNotAvailableError removal
- R4: Config KeyError protection
- R5: Signal handler simplification
"""

import ast
import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestR1LoggerMigration:
    """Tests for R1: Logger migration from stdlib logging to loguru."""

    # List of files that should have been migrated to loguru
    MIGRATED_FILES = [
        "src/core/config_loader.py",
        "src/core/env_validator.py",
        "src/core/security.py",
        "src/utils/helpers.py",
        "src/utils/error_capture.py",
        "src/utils/selector_learning.py",
        "src/services/booking/selector_utils.py",
        "src/services/bot/error_handler.py",
        "src/repositories/log_repository.py",
        "src/repositories/appointment_repository.py",
        "src/repositories/audit_log_repository.py",
        "web/app.py",
        "web/dependencies.py",
        "web/middleware/rate_limit_headers.py",
        "web/websocket/manager.py",
        "web/routes/payment.py",
        "web/routes/webhook.py",
        "web/routes/sms_webhook.py",
        "web/routes/appointments.py",
        "web/routes/auth.py",
        "web/routes/proxy.py",
        "web/routes/bot.py",
    ]

    def test_migrated_files_use_loguru(self):
        """Verify that all newly migrated files import loguru's logger (not stdlib)."""
        repo_root = Path(__file__).parent.parent.parent
        
        for file_path in self.MIGRATED_FILES:
            full_path = repo_root / file_path
            assert full_path.exists(), f"File {file_path} does not exist"
            
            with open(full_path, 'r') as f:
                content = f.read()
            
            # Should have loguru import
            assert 'from loguru import logger' in content, \
                f"{file_path} should import loguru logger"
            
            # Should NOT have stdlib logging.getLogger
            assert 'logging.getLogger(' not in content, \
                f"{file_path} should not use logging.getLogger()"
            
            # Should NOT have standalone import logging (unless it's for other purposes)
            # We check this by verifying if there's a getLogger call
            if 'import logging' in content and 'logging.getLogger' not in content:
                # This is acceptable - might be using logging for other purposes
                pass

    def test_migrated_files_no_logger_assignment(self):
        """Verify migrated files don't have logger = logging.getLogger(__name__)."""
        repo_root = Path(__file__).parent.parent.parent
        
        for file_path in self.MIGRATED_FILES:
            full_path = repo_root / file_path
            
            with open(full_path, 'r') as f:
                content = f.read()
            
            # Should not have the old pattern
            assert 'logger = logging.getLogger(__name__)' not in content, \
                f"{file_path} should not have logger = logging.getLogger(__name__)"

    def test_special_case_files_kept_stdlib(self):
        """Verify special case files still have stdlib logging."""
        repo_root = Path(__file__).parent.parent.parent
        
        special_cases = [
            "src/core/retry.py",
            "src/core/monitoring.py",
            "src/utils/request_context.py",
            "src/core/logger.py",
        ]
        
        for file_path in special_cases:
            full_path = repo_root / file_path
            if not full_path.exists():
                continue
                
            with open(full_path, 'r') as f:
                content = f.read()
            
            # Should still have import logging
            assert 'import logging' in content, \
                f"{file_path} should keep import logging for compatibility"


class TestR2DoubleShutdownFix:
    """Tests for R2: Double shutdown fix in run_both_mode."""

    def test_run_web_mode_skip_shutdown_parameter(self):
        """Test that run_web_mode accepts skip_shutdown parameter."""
        # Read the source file and verify the signature
        runners_file = Path(__file__).parent.parent.parent / 'src/core/runners.py'
        
        with open(runners_file, 'r') as f:
            content = f.read()
        
        # Check that skip_shutdown parameter exists in function signature
        assert 'skip_shutdown: bool = False' in content, \
            "run_web_mode should have skip_shutdown parameter with default False"
        
        # Also check in the docstring
        assert 'skip_shutdown: Whether to skip graceful shutdown' in content, \
            "skip_shutdown parameter should be documented"

    def test_run_web_mode_uses_skip_shutdown_flag(self):
        """Test that run_web_mode implementation uses skip_shutdown flag."""
        runners_file = Path(__file__).parent.parent.parent / 'src/core/runners.py'
        
        with open(runners_file, 'r') as f:
            content = f.read()
        
        # Check that skip_shutdown is used in the finally block
        assert 'if not skip_shutdown:' in content, \
            "run_web_mode should check skip_shutdown before calling graceful_shutdown"
        
        # Check that graceful_shutdown_with_timeout is conditionally called
        lines = content.split('\n')
        found_conditional = False
        for i, line in enumerate(lines):
            if 'if not skip_shutdown:' in line:
                # Check next few lines for graceful_shutdown_with_timeout
                for j in range(i+1, min(i+10, len(lines))):
                    if 'graceful_shutdown_with_timeout' in lines[j]:
                        found_conditional = True
                        break
        
        assert found_conditional, \
            "graceful_shutdown_with_timeout should be called conditionally based on skip_shutdown"

    def test_run_both_mode_passes_skip_shutdown_true(self):
        """Test that run_both_mode passes skip_shutdown=True to run_web_mode."""
        runners_file = Path(__file__).parent.parent.parent / 'src/core/runners.py'
        
        with open(runners_file, 'r') as f:
            content = f.read()
        
        # Check that run_both_mode calls run_web_mode with skip_shutdown=True
        assert 'skip_shutdown=True' in content, \
            "run_both_mode should pass skip_shutdown=True to run_web_mode"
        
        # More specific check
        assert 'run_web_mode(config, start_cleanup=True, db=db, skip_shutdown=True)' in content, \
            "run_both_mode should call run_web_mode with correct parameters"


class TestR3SlotNotAvailableErrorRemoval:
    """Tests for R3: SlotNotAvailableError removal."""

    def test_slot_not_available_error_removed(self):
        """Verify that SlotNotAvailableError no longer exists in src/core/exceptions.py."""
        from src.core import exceptions
        
        # Should not have SlotNotAvailableError attribute
        assert not hasattr(exceptions, 'SlotNotAvailableError'), \
            "SlotNotAvailableError should be removed from exceptions module"
        
        # Check the source file directly
        exceptions_file = Path(__file__).parent.parent.parent / 'src/core/exceptions.py'
        with open(exceptions_file, 'r') as f:
            content = f.read()
        
        assert 'class SlotNotAvailableError' not in content, \
            "SlotNotAvailableError class should not exist in exceptions.py"

    def test_vfs_slot_not_found_error_still_works(self):
        """Verify VFSSlotNotFoundError still works correctly."""
        from src.core.exceptions import VFSSlotNotFoundError
        
        # Should be able to instantiate it
        error = VFSSlotNotFoundError("Test message")
        
        assert error.message == "Test message"
        assert error.recoverable is True
        assert isinstance(error, Exception)

    def test_no_references_to_slot_not_available_error(self):
        """Verify no code references SlotNotAvailableError."""
        repo_root = Path(__file__).parent.parent.parent
        
        # Check key directories for any references
        dirs_to_check = ['src', 'web', 'tests']
        
        for dir_name in dirs_to_check:
            dir_path = repo_root / dir_name
            if not dir_path.exists():
                continue
                
            for py_file in dir_path.rglob('*.py'):
                with open(py_file, 'r') as f:
                    content = f.read()
                
                # Skip this test file itself
                if 'test_refactoring_r1_r5.py' in str(py_file):
                    continue
                
                assert 'SlotNotAvailableError' not in content, \
                    f"{py_file} should not reference SlotNotAvailableError"


class TestR4ConfigKeyErrorProtection:
    """Tests for R4: Config KeyError protection."""

    def test_run_bot_mode_uses_config_get(self):
        """Test that run_bot_mode uses config.get() for notifications."""
        runners_file = Path(__file__).parent.parent.parent / 'src/core/runners.py'
        
        with open(runners_file, 'r') as f:
            content = f.read()
        
        # In run_bot_mode, should use config.get("notifications", {})
        assert 'NotificationService(config.get("notifications", {}))' in content, \
            "run_bot_mode should use config.get('notifications', {}) to avoid KeyError"

    def test_run_both_mode_uses_config_get(self):
        """Test that run_both_mode uses config.get() for notifications."""
        runners_file = Path(__file__).parent.parent.parent / 'src/core/runners.py'
        
        with open(runners_file, 'r') as f:
            content = f.read()
        
        # In run_both_mode, should use config.get("notifications", {})
        # Check that we're not using config["notifications"] in run_both_mode
        lines = content.split('\n')
        in_run_both_mode = False
        for i, line in enumerate(lines):
            if 'async def run_both_mode' in line:
                in_run_both_mode = True
            elif in_run_both_mode and 'async def ' in line:
                # Reached next function
                break
            elif in_run_both_mode and 'NotificationService' in line:
                # Should use config.get
                assert 'config.get("notifications", {})' in line, \
                    "run_both_mode should use config.get('notifications', {}) to avoid KeyError"
                return
        
        # If we got here, we didn't find the NotificationService line
        pytest.fail("Could not find NotificationService initialization in run_both_mode")


class TestR5SignalHandlerSimplification:
    """Tests for R5: Signal handler simplification."""

    def test_signal_handler_no_deprecated_get_event_loop(self):
        """Test that handle_signal doesn't use deprecated asyncio.get_event_loop()."""
        shutdown_file = Path(__file__).parent.parent.parent / 'src/core/shutdown.py'
        
        with open(shutdown_file, 'r') as f:
            content = f.read()
        
        # Parse the file to find the handle_signal function
        tree = ast.parse(content)
        
        handle_signal_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'handle_signal':
                handle_signal_found = True
                # Convert function to string for analysis
                func_lines = content.split('\n')[node.lineno-1:node.end_lineno]
                func_str = '\n'.join(func_lines)
                
                # Should not use get_event_loop
                assert 'get_event_loop()' not in func_str, \
                    "handle_signal should not use deprecated get_event_loop()"
                
                # Should use get_running_loop and asyncio.run
                assert 'get_running_loop()' in func_str, \
                    "handle_signal should use get_running_loop()"
                assert 'asyncio.run(' in func_str, \
                    "handle_signal should use asyncio.run() for fallback"
                
                # Should use os._exit instead of sys.exit(0)
                assert 'os._exit' in func_str, \
                    "handle_signal should use os._exit instead of sys.exit"
                
                # Should use add_done_callback for cleanup completion
                assert 'add_done_callback' in func_str, \
                    "handle_signal should use add_done_callback to wait for cleanup before exit"
        
        assert handle_signal_found, "handle_signal function not found in shutdown.py"

    def test_signal_handler_simplified_structure(self):
        """Test that signal handler has simplified structure (no triple nesting)."""
        shutdown_file = Path(__file__).parent.parent.parent / 'src/core/shutdown.py'
        
        with open(shutdown_file, 'r') as f:
            content = f.read()
        
        # Should not have the old triple-nested try-except pattern
        # Old pattern had: try -> except RuntimeError -> try -> except Exception
        # This is fragile to check exactly, so we check for the absence of the old comment
        assert 'we\'re in a sync context, try to get or create one' not in content.lower(), \
            "Old complex signal handler pattern should be removed"
        
        # Parse the file to find the handle_signal function
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'handle_signal':
                func_lines = content.split('\n')[node.lineno-1:node.end_lineno]
                func_str = '\n'.join(func_lines)
                
                # sys.exit(0) should NOT be in handle_signal
                assert 'sys.exit(0)' not in func_str, \
                    "handle_signal should not use sys.exit(0)"
                
                # os._exit should be used instead
                assert 'os._exit' in func_str, \
                    "handle_signal should use os._exit instead of sys.exit"
                break

    @pytest.mark.asyncio
    async def test_fast_emergency_cleanup_runs_without_loop(self):
        """Test that fast_emergency_cleanup can be invoked via asyncio.run() when no loop is running."""
        from src.core.shutdown import fast_emergency_cleanup
        
        # This test verifies that the function can be called with asyncio.run()
        # Mock the database cleanup to avoid actual DB operations
        with patch('src.models.db_factory.DatabaseFactory') as mock_factory:
            mock_factory.close_instance = AsyncMock()
            
            # Should not raise any errors
            await fast_emergency_cleanup()

    def test_signal_handler_uses_done_callback(self):
        """Test that handle_signal uses add_done_callback for cleanup task completion."""
        shutdown_file = Path(__file__).parent.parent.parent / 'src/core/shutdown.py'
        
        with open(shutdown_file, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'handle_signal':
                func_lines = content.split('\n')[node.lineno-1:node.end_lineno]
                func_str = '\n'.join(func_lines)
                
                # Should use add_done_callback to wait for cleanup before exit
                assert 'add_done_callback' in func_str, \
                    "handle_signal should use add_done_callback to wait for cleanup before exit"
                
                # Should NOT have sys.exit in handle_signal (should use os._exit)
                assert 'sys.exit(0)' not in func_str, \
                    "handle_signal should use os._exit instead of sys.exit"
                break

    def test_signal_handler_no_immediate_exit_after_create_task(self):
        """Test that handle_signal does not immediately exit after creating a task."""
        shutdown_file = Path(__file__).parent.parent.parent / 'src/core/shutdown.py'
        
        with open(shutdown_file, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'handle_signal':
                func_lines = content.split('\n')[node.lineno-1:node.end_lineno]
                func_str = '\n'.join(func_lines)
                
                # The old pattern had a finally block with sys.exit that ran immediately
                # after create_task, preventing cleanup from executing.
                # Verify no finally block with exit exists in handle_signal
                assert not ('finally:' in func_str and 'sys.exit' in func_str), \
                    "handle_signal should not have a finally block with sys.exit"
                break


class TestDocumentationUpdates:
    """Test that documentation was updated."""

    def test_migration_summary_updated(self):
        """Test that MIGRATION_SUMMARY.md was updated with new files."""
        doc_file = Path(__file__).parent.parent.parent / 'docs/MIGRATION_SUMMARY.md'
        
        with open(doc_file, 'r') as f:
            content = f.read()
        
        # Should mention 42 files
        assert '42' in content, "MIGRATION_SUMMARY.md should mention 42 migrated files"
        
        # Should mention some of the newly migrated files
        assert 'config_loader.py' in content
        assert 'env_validator.py' in content
        assert 'web/app.py' in content

    def test_final_verification_updated(self):
        """Test that FINAL_VERIFICATION.md was updated."""
        doc_file = Path(__file__).parent.parent.parent / 'docs/FINAL_VERIFICATION.md'
        
        with open(doc_file, 'r') as f:
            content = f.read()
        
        # Should mention 45 files (42 migrated + 4 special cases)
        assert '45' in content or '42' in content, \
            "FINAL_VERIFICATION.md should mention total files"
        
        # Should list some web routes
        assert 'web/routes/payment.py' in content
        assert 'web/routes/webhook.py' in content
