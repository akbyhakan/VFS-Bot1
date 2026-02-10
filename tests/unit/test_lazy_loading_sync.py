"""Test that __all__ and _LAZY_MODULE_MAP stay synchronized in src/__init__.py."""

import ast
from pathlib import Path

import pytest


class TestLazyLoadingSync:
    """Ensure __all__ and _LAZY_MODULE_MAP are always in sync."""

    def test_all_keys_match_lazy_map(self):
        """Every item in __all__ must have a corresponding entry in _LAZY_MODULE_MAP."""
        import src
        all_set = set(src.__all__)
        lazy_set = set(src._LAZY_MODULE_MAP.keys())
        missing_from_lazy = all_set - lazy_set
        assert not missing_from_lazy, (
            f"Items in __all__ but NOT in _LAZY_MODULE_MAP: {missing_from_lazy}"
        )

    def test_lazy_map_keys_match_all(self):
        """Every key in _LAZY_MODULE_MAP must be listed in __all__."""
        import src
        all_set = set(src.__all__)
        lazy_set = set(src._LAZY_MODULE_MAP.keys())
        extra_in_lazy = lazy_set - all_set
        assert not extra_in_lazy, (
            f"Items in _LAZY_MODULE_MAP but NOT in __all__: {extra_in_lazy}"
        )

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
