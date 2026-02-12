"""Tests for R1-R6 refactoring fixes.

This test file validates the following refactoring changes:
- R1: Logger migration from stdlib logging to loguru (22 files)
- R2: Double shutdown fix in run_both_mode
- R3: SlotNotAvailableError removal
- R4: Config KeyError protection
- R5: Signal handler simplification
- R6: Runtime safety fixes (port parsing, DB pool size, bot failure handling, markdown injection)
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

            with open(full_path, "r") as f:
                content = f.read()

            # Should have loguru import
            assert (
                "from loguru import logger" in content
            ), f"{file_path} should import loguru logger"

            # Should NOT have stdlib logging.getLogger
            assert (
                "logging.getLogger(" not in content
            ), f"{file_path} should not use logging.getLogger()"

            # Should NOT have standalone import logging (unless it's for other purposes)
            # We check this by verifying if there's a getLogger call
            if "import logging" in content and "logging.getLogger" not in content:
                # This is acceptable - might be using logging for other purposes
                pass

    def test_migrated_files_no_logger_assignment(self):
        """Verify migrated files don't have logger = logging.getLogger(__name__)."""
        repo_root = Path(__file__).parent.parent.parent

        for file_path in self.MIGRATED_FILES:
            full_path = repo_root / file_path

            with open(full_path, "r") as f:
                content = f.read()

            # Should not have the old pattern
            assert (
                "logger = logging.getLogger(__name__)" not in content
            ), f"{file_path} should not have logger = logging.getLogger(__name__)"

    def test_special_case_files_kept_stdlib(self):
        """Verify special case files still have stdlib logging."""
        repo_root = Path(__file__).parent.parent.parent

        special_cases = [
            "src/core/retry.py",
            "src/core/monitoring.py",
            "src/core/logger.py",
        ]

        for file_path in special_cases:
            full_path = repo_root / file_path
            if not full_path.exists():
                continue

            with open(full_path, "r") as f:
                content = f.read()

            # Should still have import logging
            assert (
                "import logging" in content
            ), f"{file_path} should keep import logging for compatibility"


class TestR2DoubleShutdownFix:
    """Tests for R2: Double shutdown fix in run_both_mode."""

    def test_run_web_mode_skip_shutdown_parameter(self):
        """Test that run_web_mode accepts skip_shutdown parameter."""
        # Read the source file and verify the signature
        runners_file = Path(__file__).parent.parent.parent / "src/core/runners.py"

        with open(runners_file, "r") as f:
            content = f.read()

        # Check that skip_shutdown parameter exists in function signature
        assert (
            "skip_shutdown: bool = False" in content
        ), "run_web_mode should have skip_shutdown parameter with default False"

        # Also check in the docstring
        assert (
            "skip_shutdown: Whether to skip graceful shutdown" in content
        ), "skip_shutdown parameter should be documented"

    def test_run_web_mode_uses_skip_shutdown_flag(self):
        """Test that run_web_mode implementation uses skip_shutdown flag."""
        runners_file = Path(__file__).parent.parent.parent / "src/core/runners.py"

        with open(runners_file, "r") as f:
            content = f.read()

        # Check that skip_shutdown is used in the finally block
        assert (
            "if not skip_shutdown:" in content
        ), "run_web_mode should check skip_shutdown before calling graceful_shutdown"

        # Check that graceful_shutdown_with_timeout is conditionally called
        lines = content.split("\n")
        found_conditional = False
        for i, line in enumerate(lines):
            if "if not skip_shutdown:" in line:
                # Check next few lines for graceful_shutdown_with_timeout
                for j in range(i + 1, min(i + 10, len(lines))):
                    if "graceful_shutdown_with_timeout" in lines[j]:
                        found_conditional = True
                        break

        assert (
            found_conditional
        ), "graceful_shutdown_with_timeout should be called conditionally based on skip_shutdown"

    def test_run_both_mode_passes_skip_shutdown_true(self):
        """Test that run_both_mode passes skip_shutdown=True to run_web_mode."""
        runners_file = Path(__file__).parent.parent.parent / "src/core/runners.py"

        with open(runners_file, "r") as f:
            content = f.read()

        # Check that run_both_mode calls run_web_mode with skip_shutdown=True
        assert (
            "skip_shutdown=True" in content
        ), "run_both_mode should pass skip_shutdown=True to run_web_mode"

        # More specific check
        assert (
            "run_web_mode(config, start_cleanup=True, db=db, skip_shutdown=True)" in content
        ), "run_both_mode should call run_web_mode with correct parameters"


class TestR3SlotNotAvailableErrorRemoval:
    """Tests for R3: SlotNotAvailableError removal."""

    def test_slot_not_available_error_removed(self):
        """Verify that SlotNotAvailableError no longer exists in src/core/exceptions.py."""
        from src.core import exceptions

        # Should not have SlotNotAvailableError attribute
        assert not hasattr(
            exceptions, "SlotNotAvailableError"
        ), "SlotNotAvailableError should be removed from exceptions module"

        # Check the source file directly
        exceptions_file = Path(__file__).parent.parent.parent / "src/core/exceptions.py"
        with open(exceptions_file, "r") as f:
            content = f.read()

        assert (
            "class SlotNotAvailableError" not in content
        ), "SlotNotAvailableError class should not exist in exceptions.py"

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
        dirs_to_check = ["src", "web", "tests"]

        for dir_name in dirs_to_check:
            dir_path = repo_root / dir_name
            if not dir_path.exists():
                continue

            for py_file in dir_path.rglob("*.py"):
                with open(py_file, "r") as f:
                    content = f.read()

                # Skip this test file itself
                if "test_refactoring_r1_r5.py" in str(py_file):
                    continue

                assert (
                    "SlotNotAvailableError" not in content
                ), f"{py_file} should not reference SlotNotAvailableError"


class TestR4ConfigKeyErrorProtection:
    """Tests for R4: Config KeyError protection."""

    def test_run_bot_mode_uses_config_get(self):
        """Test that run_bot_mode uses config.get() for notifications."""
        runners_file = Path(__file__).parent.parent.parent / "src/core/runners.py"

        with open(runners_file, "r") as f:
            content = f.read()

        # In run_bot_mode, should use config.get("notifications", {})
        assert (
            'NotificationService(config.get("notifications", {}))' in content
        ), "run_bot_mode should use config.get('notifications', {}) to avoid KeyError"

    def test_run_both_mode_uses_config_get(self):
        """Test that run_both_mode uses config.get() for notifications."""
        runners_file = Path(__file__).parent.parent.parent / "src/core/runners.py"

        with open(runners_file, "r") as f:
            content = f.read()

        # In run_both_mode, should use config.get("notifications", {})
        # Check that we're not using config["notifications"] in run_both_mode
        lines = content.split("\n")
        in_run_both_mode = False
        for i, line in enumerate(lines):
            if "async def run_both_mode" in line:
                in_run_both_mode = True
            elif in_run_both_mode and "async def " in line:
                # Reached next function
                break
            elif in_run_both_mode and "NotificationService" in line:
                # Should use config.get
                assert (
                    'config.get("notifications", {})' in line
                ), "run_both_mode should use config.get('notifications', {}) to avoid KeyError"
                return

        # If we got here, we didn't find the NotificationService line
        pytest.fail("Could not find NotificationService initialization in run_both_mode")


class TestR5SignalHandlerSimplification:
    """Tests for R5: Signal handler simplification."""

    def test_signal_handler_no_deprecated_get_event_loop(self):
        """Test that handle_signal doesn't use deprecated asyncio.get_event_loop()."""
        shutdown_file = Path(__file__).parent.parent.parent / "src/core/shutdown.py"

        with open(shutdown_file, "r") as f:
            content = f.read()

        # Parse the file to find the handle_signal function
        tree = ast.parse(content)

        handle_signal_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "handle_signal":
                handle_signal_found = True
                # Convert function to string for analysis
                func_lines = content.split("\n")[node.lineno - 1 : node.end_lineno]
                func_str = "\n".join(func_lines)

                # Should not use get_event_loop
                assert (
                    "get_event_loop()" not in func_str
                ), "handle_signal should not use deprecated get_event_loop()"

                # Should use get_running_loop and asyncio.run
                assert (
                    "get_running_loop()" in func_str
                ), "handle_signal should use get_running_loop()"
                assert (
                    "asyncio.run(" in func_str
                ), "handle_signal should use asyncio.run() for fallback"

                # Should use os._exit instead of sys.exit(0)
                assert (
                    "os._exit" in func_str
                ), "handle_signal should use os._exit instead of sys.exit"

                # Should use add_done_callback for cleanup completion
                assert (
                    "add_done_callback" in func_str
                ), "handle_signal should use add_done_callback to wait for cleanup before exit"

        assert handle_signal_found, "handle_signal function not found in shutdown.py"

    def test_signal_handler_simplified_structure(self):
        """Test that signal handler has simplified structure (no triple nesting)."""
        shutdown_file = Path(__file__).parent.parent.parent / "src/core/shutdown.py"

        with open(shutdown_file, "r") as f:
            content = f.read()

        # Should not have the old triple-nested try-except pattern
        # Old pattern had: try -> except RuntimeError -> try -> except Exception
        # This is fragile to check exactly, so we check for the absence of the old comment
        assert (
            "we're in a sync context, try to get or create one" not in content.lower()
        ), "Old complex signal handler pattern should be removed"

        # Parse the file to find the handle_signal function
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "handle_signal":
                func_lines = content.split("\n")[node.lineno - 1 : node.end_lineno]
                func_str = "\n".join(func_lines)

                # sys.exit(0) should NOT be in handle_signal
                assert "sys.exit(0)" not in func_str, "handle_signal should not use sys.exit(0)"

                # os._exit should be used instead
                assert (
                    "os._exit" in func_str
                ), "handle_signal should use os._exit instead of sys.exit"
                break

    @pytest.mark.asyncio
    async def test_fast_emergency_cleanup_runs_without_loop(self):
        """Test that fast_emergency_cleanup can be invoked via asyncio.run() when no loop is running."""
        from src.core.infra.shutdown import fast_emergency_cleanup

        # This test verifies that the function can be called with asyncio.run()
        # Mock the database cleanup to avoid actual DB operations
        with patch("src.models.db_factory.DatabaseFactory") as mock_factory:
            mock_factory.close_instance = AsyncMock()

            # Should not raise any errors
            await fast_emergency_cleanup()

    def test_signal_handler_uses_done_callback(self):
        """Test that handle_signal uses add_done_callback for cleanup task completion."""
        shutdown_file = Path(__file__).parent.parent.parent / "src/core/shutdown.py"

        with open(shutdown_file, "r") as f:
            content = f.read()

        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "handle_signal":
                func_lines = content.split("\n")[node.lineno - 1 : node.end_lineno]
                func_str = "\n".join(func_lines)

                # Should use add_done_callback to wait for cleanup before exit
                assert (
                    "add_done_callback" in func_str
                ), "handle_signal should use add_done_callback to wait for cleanup before exit"

                # Should NOT have sys.exit in handle_signal (should use os._exit)
                assert (
                    "sys.exit(0)" not in func_str
                ), "handle_signal should use os._exit instead of sys.exit"
                break

    def test_signal_handler_no_immediate_exit_after_create_task(self):
        """Test that handle_signal does not immediately exit after creating a task."""
        shutdown_file = Path(__file__).parent.parent.parent / "src/core/shutdown.py"

        with open(shutdown_file, "r") as f:
            content = f.read()

        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "handle_signal":
                func_lines = content.split("\n")[node.lineno - 1 : node.end_lineno]
                func_str = "\n".join(func_lines)

                # The old pattern had a finally block with sys.exit that ran immediately
                # after create_task, preventing cleanup from executing.
                # Verify no finally block with exit exists in handle_signal
                assert not (
                    "finally:" in func_str and "sys.exit" in func_str
                ), "handle_signal should not have a finally block with sys.exit"
                break


class TestR6RuntimeSafetyFixes:
    """Tests for R6: Runtime safety fixes (port parsing, DB pool size, bot failure handling, markdown injection)."""

    def test_parse_safe_port_function_exists(self):
        """Test that parse_safe_port helper function was added."""
        runners_file = Path(__file__).parent.parent.parent / "src/core/runners.py"

        with open(runners_file, "r") as f:
            content = f.read()

        # Should have the parse_safe_port function
        assert (
            "def parse_safe_port(" in content
        ), "parse_safe_port function should be defined in runners.py"

        # Should have proper validation logic
        assert "1 <= port <= 65535" in content, "parse_safe_port should validate port range 1-65535"

        # Should have try/except for ValueError
        tree = ast.parse(content)
        found_function = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "parse_safe_port":
                found_function = True
                func_lines = content.split("\n")[node.lineno - 1 : node.end_lineno]
                func_str = "\n".join(func_lines)
                assert (
                    "try:" in func_str and "except ValueError" in func_str
                ), "parse_safe_port should have try/except ValueError"
                break

        assert found_function, "parse_safe_port function not found"

    def test_run_web_mode_uses_parse_safe_port(self):
        """Test that run_web_mode uses parse_safe_port instead of int()."""
        runners_file = Path(__file__).parent.parent.parent / "src/core/runners.py"

        with open(runners_file, "r") as f:
            content = f.read()

        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_web_mode":
                func_lines = content.split("\n")[node.lineno - 1 : node.end_lineno]
                func_str = "\n".join(func_lines)

                # Should use parse_safe_port()
                assert "parse_safe_port()" in func_str, "run_web_mode should use parse_safe_port()"

                # Should NOT have int(os.getenv("UVICORN_PORT"))
                assert (
                    'int(os.getenv("UVICORN_PORT"' not in func_str
                ), "run_web_mode should not use int(os.getenv('UVICORN_PORT'))"
                break

    def test_web_app_uses_parse_safe_port(self):
        """Test that web/app.py imports and uses parse_safe_port."""
        app_file = Path(__file__).parent.parent.parent / "web/app.py"

        with open(app_file, "r") as f:
            content = f.read()

        # Should import parse_safe_port from src.core.runners
        assert (
            "from src.core.infra.runners import parse_safe_port" in content
        ), "web/app.py should import parse_safe_port from src.core.runners"

        # Should use parse_safe_port()
        assert "parse_safe_port()" in content, "web/app.py should use parse_safe_port()"

        # Should NOT have int(os.getenv("UVICORN_PORT")) in main block
        lines = content.split("\n")
        in_main = False
        for line in lines:
            if 'if __name__ == "__main__"' in line:
                in_main = True
            if in_main and 'int(os.getenv("UVICORN_PORT"' in line:
                raise AssertionError(
                    "web/app.py should not use int(os.getenv('UVICORN_PORT')) in __main__"
                )

    def test_db_pool_size_has_error_handling(self):
        """Test that DB_POOL_SIZE parsing has try/except with validation."""
        db_file = Path(__file__).parent.parent.parent / "src/models/database.py"

        with open(db_file, "r") as f:
            content = f.read()

        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Database":
                # Find __init__ method
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and method.name == "__init__":
                        method_lines = content.split("\n")[method.lineno - 1 : method.end_lineno]
                        method_str = "\n".join(method_lines)

                        # Should have try/except for DB_POOL_SIZE
                        assert (
                            "DB_POOL_SIZE" in method_str
                        ), "Database.__init__ should reference DB_POOL_SIZE"

                        # Should have try/except ValueError
                        assert (
                            "try:" in method_str and "except ValueError" in method_str
                        ), "DB_POOL_SIZE parsing should have try/except ValueError"

                        # Should validate pool_size >= 1
                        assert (
                            "pool_size < 1" in method_str or "pool_size >= 1" in method_str
                        ), "DB_POOL_SIZE should be validated (>= 1)"
                        break
                break

    def test_run_both_mode_starts_web_on_bot_failure(self):
        """Test that run_both_mode starts web dashboard even when bot fails."""
        runners_file = Path(__file__).parent.parent.parent / "src/core/runners.py"

        with open(runners_file, "r") as f:
            content = f.read()

        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_both_mode":
                func_lines = content.split("\n")[node.lineno - 1 : node.end_lineno]
                func_str = "\n".join(func_lines)

                # Check that RuntimeError is not raised between bot failure check and web start
                # The old code raised RuntimeError immediately on bot failure, preventing web from starting
                if (
                    'if start_result["status"] != "success"' in func_str
                    and "run_web_mode" in func_str
                ):
                    # Extract the section between the failure check and web start
                    parts = func_str.split('if start_result["status"] != "success"')
                    if len(parts) > 1:
                        after_check = parts[1]
                        web_parts = after_check.split("run_web_mode")
                        if len(web_parts) > 0:
                            section_before_web = web_parts[0]
                            assert (
                                "raise RuntimeError" not in section_before_web
                            ), "run_both_mode should not raise RuntimeError when bot fails before starting web"

                # Should start web_task regardless of bot status
                assert "run_web_mode" in func_str, "run_both_mode should call run_web_mode"

                # Should have degraded mode message
                assert (
                    "degraded mode" in func_str.lower()
                ), "run_both_mode should mention degraded mode when bot fails"
                break

    def test_notification_has_escape_markdown(self):
        """Test that NotificationService has _escape_markdown static method."""
        notif_file = Path(__file__).parent.parent.parent / "src/services/notification.py"

        with open(notif_file, "r") as f:
            content = f.read()

        # Should have _escape_markdown method
        assert (
            "def _escape_markdown(" in content
        ), "NotificationService should have _escape_markdown method"

        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "NotificationService":
                # Find _escape_markdown method
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and method.name == "_escape_markdown":
                        # Check if it's a static method using AST decorator inspection
                        has_staticmethod = any(
                            isinstance(dec, ast.Name) and dec.id == "staticmethod"
                            for dec in method.decorator_list
                        )
                        assert has_staticmethod, "_escape_markdown should be a static method"

                        method_lines = content.split("\n")[method.lineno - 1 : method.end_lineno]
                        method_str = "\n".join(method_lines)

                        # Should escape markdown special characters
                        special_chars = ["*", "_", "`", "[", "]", "(", ")"]
                        for char in special_chars:
                            # Check if character is mentioned (escaped as string)
                            assert (
                                f"'{char}'" in method_str or f'"{char}"' in method_str
                            ), f"_escape_markdown should handle '{char}' character"
                        break
                break

    def test_send_telegram_uses_escape_markdown(self):
        """Test that send_telegram uses _escape_markdown for title and message."""
        notif_file = Path(__file__).parent.parent.parent / "src/services/notification.py"

        with open(notif_file, "r") as f:
            content = f.read()

        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "NotificationService":
                # Find send_telegram method
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and method.name == "send_telegram":
                        method_lines = content.split("\n")[method.lineno - 1 : method.end_lineno]
                        method_str = "\n".join(method_lines)

                        # Should call _escape_markdown
                        assert (
                            "_escape_markdown(" in method_str
                        ), "send_telegram should use _escape_markdown"

                        # Should escape both title and message
                        assert (
                            "escaped_title" in method_str or "_escape_markdown(title)" in method_str
                        ), "send_telegram should escape title"
                        assert (
                            "escaped_message" in method_str
                            or "_escape_markdown(message)" in method_str
                        ), "send_telegram should escape message"
                        break
                break

    def test_send_telegram_with_photo_uses_escape_markdown(self):
        """Test that _send_telegram_with_photo uses _escape_markdown."""
        notif_file = Path(__file__).parent.parent.parent / "src/services/notification.py"

        with open(notif_file, "r") as f:
            content = f.read()

        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "NotificationService":
                # Find _send_telegram_with_photo method
                for method in node.body:
                    if (
                        isinstance(method, ast.FunctionDef)
                        and method.name == "_send_telegram_with_photo"
                    ):
                        method_lines = content.split("\n")[method.lineno - 1 : method.end_lineno]
                        method_str = "\n".join(method_lines)

                        # Should call _escape_markdown
                        assert (
                            "_escape_markdown(" in method_str
                        ), "_send_telegram_with_photo should use _escape_markdown"

                        # Should escape both title and message
                        assert (
                            "escaped_title" in method_str or "_escape_markdown(title)" in method_str
                        ), "_send_telegram_with_photo should escape title"
                        assert (
                            "escaped_message" in method_str
                            or "_escape_markdown(message)" in method_str
                        ), "_send_telegram_with_photo should escape message"
                        break
                break


class TestDocumentationUpdates:
    """Test that documentation was updated."""

    def test_migration_summary_updated(self):
        """Test that MIGRATION_SUMMARY.md was updated with new files."""
        doc_file = Path(__file__).parent.parent.parent / "docs/MIGRATION_SUMMARY.md"

        with open(doc_file, "r") as f:
            content = f.read()

        # Should mention 42 files
        assert "42" in content, "MIGRATION_SUMMARY.md should mention 42 migrated files"

        # Should mention some of the newly migrated files
        assert "config_loader.py" in content
        assert "env_validator.py" in content
        assert "web/app.py" in content

    def test_final_verification_updated(self):
        """Test that FINAL_VERIFICATION.md was updated."""
        doc_file = Path(__file__).parent.parent.parent / "docs/FINAL_VERIFICATION.md"

        with open(doc_file, "r") as f:
            content = f.read()

        # Should mention 45 files (42 migrated + 4 special cases)
        assert (
            "45" in content or "42" in content
        ), "FINAL_VERIFICATION.md should mention total files"

        # Should list some web routes
        assert "web/routes/payment.py" in content
        assert "web/routes/webhook.py" in content
