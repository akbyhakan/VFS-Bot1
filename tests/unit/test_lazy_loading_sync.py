"""Test that __all__ is correctly auto-derived from _LAZY_MODULE_MAP."""

import ast
from pathlib import Path

import pytest


class TestLazyLoadingSync:
    """Ensure __all__ is auto-derived from _LAZY_MODULE_MAP."""

    def test_all_keys_match_lazy_map(self):
        """Verify __all__ contains all items from _LAZY_MODULE_MAP (auto-derivation check)."""
        import src

        all_set = set(src.__all__)
        lazy_set = set(src._LAZY_MODULE_MAP.keys())
        missing_from_lazy = all_set - lazy_set
        assert (
            not missing_from_lazy
        ), f"Items in __all__ but NOT in _LAZY_MODULE_MAP: {missing_from_lazy}"

    def test_lazy_map_keys_match_all(self):
        """Verify all _LAZY_MODULE_MAP keys are in __all__ (auto-derivation check)."""
        import src

        all_set = set(src.__all__)
        lazy_set = set(src._LAZY_MODULE_MAP.keys())
        extra_in_lazy = lazy_set - all_set
        assert not extra_in_lazy, f"Items in _LAZY_MODULE_MAP but NOT in __all__: {extra_in_lazy}"

    def test_lazy_map_modules_are_valid_paths(self):
        """Every module path in _LAZY_MODULE_MAP should be a valid dotted path."""
        import src

        for name, (module_path, attr_name) in src._LAZY_MODULE_MAP.items():
            assert "." in module_path, f"Module path '{module_path}' for '{name}' not dotted"
            assert attr_name, f"Empty attribute name for '{name}'"

    def test_type_checking_imports_match_lazy_map(self):
        """TYPE_CHECKING imports should match _LAZY_MODULE_MAP entries."""
        init_path = Path("src/__init__.py")
        if not init_path.exists():
            pytest.skip("src/__init__.py not found")
        source = init_path.read_text()
        tree = ast.parse(source)
        type_checking_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                    for stmt in node.body:
                        if isinstance(stmt, ast.ImportFrom):
                            for alias in stmt.names:
                                type_checking_names.add(alias.asname or alias.name)
        import src

        lazy_set = set(src._LAZY_MODULE_MAP.keys())
        missing = lazy_set - type_checking_names
        assert not missing, f"Items without TYPE_CHECKING import: {missing}"

    def test_all_is_derived_from_lazy_map(self):
        """Verify __all__ is auto-derived from _LAZY_MODULE_MAP for src module."""
        import src

        # This test verifies that __all__ == list(_LAZY_MODULE_MAP.keys())
        assert set(src.__all__) == set(
            src._LAZY_MODULE_MAP.keys()
        ), "src.__all__ must be auto-derived from _LAZY_MODULE_MAP.keys()"

    def test_all_length_matches_lazy_map(self):
        """Verify __all__ and _LAZY_MODULE_MAP have the same length for src module."""
        import src

        assert len(src.__all__) == len(src._LAZY_MODULE_MAP), (
            f"Length mismatch: __all__ has {len(src.__all__)} items, "
            f"_LAZY_MODULE_MAP has {len(src._LAZY_MODULE_MAP)} items"
        )

    def test_models_all_derived_from_lazy_map(self):
        """Verify __all__ is auto-derived from _LAZY_MODULE_MAP for src.models module."""
        import src.models

        # This test verifies that __all__ == list(_LAZY_MODULE_MAP.keys())
        assert set(src.models.__all__) == set(
            src.models._LAZY_MODULE_MAP.keys()
        ), "src.models.__all__ must be auto-derived from _LAZY_MODULE_MAP.keys()"

    def test_no_duplicates_in_all(self):
        """Verify there are no duplicate entries in __all__ for both modules."""
        import src
        import src.models

        # Test src module
        assert len(src.__all__) == len(set(src.__all__)), (
            f"Duplicate entries found in src.__all__: "
            f"{[item for item in src.__all__ if src.__all__.count(item) > 1]}"
        )

        # Test src.models module
        assert len(src.models.__all__) == len(set(src.models.__all__)), (
            f"Duplicate entries found in src.models.__all__: "
            f"{[item for item in src.models.__all__ if src.models.__all__.count(item) > 1]}"
        )

    # New tests for Issue 4.3 - Lazy Import Pattern Consistency

    def test_services_all_derived_from_lazy_map(self):
        """Verify __all__ is auto-derived from _LAZY_MODULE_MAP for src.services module."""
        import src.services

        assert set(src.services.__all__) == set(
            src.services._LAZY_MODULE_MAP.keys()
        ), "src.services.__all__ must be auto-derived from _LAZY_MODULE_MAP.keys()"

    def test_security_utils_all_derived_from_lazy_map(self):
        """Verify __all__ is auto-derived from _LAZY_MODULE_MAP for src.utils.security module."""
        import src.utils.security

        assert set(src.utils.security.__all__) == set(
            src.utils.security._LAZY_MODULE_MAP.keys()
        ), "src.utils.security.__all__ must be auto-derived from _LAZY_MODULE_MAP.keys()"

    def test_anti_detection_all_derived_from_lazy_map(self):
        """Verify __all__ auto-derived from _LAZY_MODULE_MAP for anti_detection."""
        import src.utils.anti_detection

        assert set(src.utils.anti_detection.__all__) == set(
            src.utils.anti_detection._LAZY_MODULE_MAP.keys()
        ), "src.utils.anti_detection.__all__ must be auto-derived from _LAZY_MODULE_MAP.keys()"

    def test_services_lazy_map_modules_are_valid_paths(self):
        """Every module path in src.services._LAZY_MODULE_MAP should be valid."""
        import src.services

        for name, (module_path, attr_name) in src.services._LAZY_MODULE_MAP.items():
            assert "." in module_path, f"Module path '{module_path}' for '{name}' not dotted"
            assert attr_name, f"Empty attribute name for '{name}'"

    def test_security_lazy_map_modules_are_valid_paths(self):
        """Every module path in src.utils.security._LAZY_MODULE_MAP should be valid."""
        import src.utils.security

        for name, (module_path, attr_name) in src.utils.security._LAZY_MODULE_MAP.items():
            assert "." in module_path, f"Module path '{module_path}' for '{name}' not dotted"
            assert attr_name, f"Empty attribute name for '{name}'"

    def test_anti_detection_lazy_map_modules_are_valid_paths(self):
        """Every module path in src.utils.anti_detection._LAZY_MODULE_MAP should be valid."""
        import src.utils.anti_detection

        for name, (module_path, attr_name) in src.utils.anti_detection._LAZY_MODULE_MAP.items():
            assert "." in module_path, f"Module path '{module_path}' for '{name}' not dotted"
            assert attr_name, f"Empty attribute name for '{name}'"

    def test_services_type_checking_imports_match_lazy_map(self):
        """TYPE_CHECKING imports should match _LAZY_MODULE_MAP entries for src.services."""
        init_path = Path("src/services/__init__.py")
        if not init_path.exists():
            pytest.skip("src/services/__init__.py not found")
        source = init_path.read_text()
        tree = ast.parse(source)
        type_checking_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                    for stmt in node.body:
                        if isinstance(stmt, ast.ImportFrom):
                            for alias in stmt.names:
                                type_checking_names.add(alias.asname or alias.name)

        import src.services

        lazy_set = set(src.services._LAZY_MODULE_MAP.keys())
        missing = lazy_set - type_checking_names
        assert not missing, f"Items without TYPE_CHECKING import in src.services: {missing}"

    def test_security_type_checking_imports_match_lazy_map(self):
        """TYPE_CHECKING imports should match _LAZY_MODULE_MAP entries for src.utils.security."""
        init_path = Path("src/utils/security/__init__.py")
        if not init_path.exists():
            pytest.skip("src/utils/security/__init__.py not found")
        source = init_path.read_text()
        tree = ast.parse(source)
        type_checking_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                    for stmt in node.body:
                        if isinstance(stmt, ast.ImportFrom):
                            for alias in stmt.names:
                                type_checking_names.add(alias.asname or alias.name)

        import src.utils.security

        lazy_set = set(src.utils.security._LAZY_MODULE_MAP.keys())
        missing = lazy_set - type_checking_names
        assert not missing, f"Items without TYPE_CHECKING import in src.utils.security: {missing}"

    def test_anti_detection_type_checking_imports_match_lazy_map(self):
        """TYPE_CHECKING imports match _LAZY_MODULE_MAP for anti_detection."""
        init_path = Path("src/utils/anti_detection/__init__.py")
        if not init_path.exists():
            pytest.skip("src/utils/anti_detection/__init__.py not found")
        source = init_path.read_text()
        tree = ast.parse(source)
        type_checking_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                    for stmt in node.body:
                        if isinstance(stmt, ast.ImportFrom):
                            for alias in stmt.names:
                                type_checking_names.add(alias.asname or alias.name)

        import src.utils.anti_detection

        lazy_set = set(src.utils.anti_detection._LAZY_MODULE_MAP.keys())
        missing = lazy_set - type_checking_names
        assert (
            not missing
        ), f"Items without TYPE_CHECKING import in src.utils.anti_detection: {missing}"
