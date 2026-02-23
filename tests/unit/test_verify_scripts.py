"""Tests for scripts/verify_lock.py and scripts/verify_version_sync.py."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers to load scripts as modules without a package structure
# ---------------------------------------------------------------------------


def _load_script(script_path: Path):
    """Load a standalone script as a module by file path."""
    spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"


def _verify_lock_module():
    return _load_script(_SCRIPTS_DIR / "verify_lock.py")


def _verify_version_sync_module():
    return _load_script(_SCRIPTS_DIR / "verify_version_sync.py")


# ---------------------------------------------------------------------------
# Tests for scripts/verify_lock.py – pure helper functions
# ---------------------------------------------------------------------------


class TestParsePackageName:
    """Tests for verify_lock.parse_package_name."""

    def test_simple_package(self):
        mod = _verify_lock_module()
        assert mod.parse_package_name("fastapi==0.129.0") == "fastapi"

    def test_package_with_extras(self):
        mod = _verify_lock_module()
        assert mod.parse_package_name("sqlalchemy[asyncio]~=2.0.37") == "sqlalchemy"

    def test_package_with_inline_comment(self):
        mod = _verify_lock_module()
        assert mod.parse_package_name("requests>=2.0  # HTTP library") == "requests"

    def test_package_name_is_lowercased(self):
        mod = _verify_lock_module()
        assert mod.parse_package_name("SQLAlchemy~=2.0.37") == "sqlalchemy"

    def test_package_with_hyphen(self):
        mod = _verify_lock_module()
        assert mod.parse_package_name("python-dotenv==1.0.1") == "python-dotenv"


class TestExtractConstraint:
    """Tests for verify_lock.extract_constraint."""

    def test_equality_constraint(self):
        mod = _verify_lock_module()
        assert mod.extract_constraint("fastapi==0.129.0") == "==0.129.0"

    def test_compatible_release_constraint(self):
        mod = _verify_lock_module()
        assert mod.extract_constraint("aiohttp~=3.13.3") == "~=3.13.3"

    def test_extras_with_constraint(self):
        mod = _verify_lock_module()
        assert mod.extract_constraint("sqlalchemy[asyncio]~=2.0.37") == "~=2.0.37"

    def test_inline_comment_stripped(self):
        mod = _verify_lock_module()
        assert mod.extract_constraint("requests>=2.0  # comment") == ">=2.0"

    def test_no_constraint(self):
        mod = _verify_lock_module()
        # Package with no version specifier returns empty string
        assert mod.extract_constraint("somepackage") == ""


# ---------------------------------------------------------------------------
# Tests for scripts/verify_lock.py – main() integration
# ---------------------------------------------------------------------------


def _write_pyproject(path: Path, deps: list[str], version: str = "1.0.0") -> None:
    """Write a minimal pyproject.toml with the given dependencies."""
    dep_lines = "\n".join(f'    "{d}",' for d in deps)
    path.write_text(
        f'[project]\nname = "test"\nversion = "{version}"\ndependencies = [\n{dep_lines}\n]\n'
    )


def _write_lock(path: Path, entries: list[str]) -> None:
    """Write a minimal requirements.lock file."""
    path.write_text("# lock file\n" + "\n".join(entries) + "\n")


class TestVerifyLockMain:
    """Integration tests for verify_lock.main()."""

    def test_happy_path_exact_pin(self, tmp_path, monkeypatch):
        """Lock file matches exact pin in pyproject.toml → exit 0."""
        monkeypatch.chdir(tmp_path)
        _write_pyproject(tmp_path / "pyproject.toml", ["fastapi==0.129.0"])
        _write_lock(tmp_path / "requirements.lock", ["fastapi==0.129.0"])
        mod = _verify_lock_module()
        assert mod.main() == 0

    def test_happy_path_compatible_release(self, tmp_path, monkeypatch):
        """Lock file satisfies compatible-release constraint → exit 0."""
        monkeypatch.chdir(tmp_path)
        _write_pyproject(tmp_path / "pyproject.toml", ["aiohttp~=3.13.3"])
        _write_lock(tmp_path / "requirements.lock", ["aiohttp==3.13.4"])
        mod = _verify_lock_module()
        assert mod.main() == 0

    def test_missing_package_in_lock(self, tmp_path, monkeypatch):
        """Package present in pyproject.toml but absent from lock → exit 1."""
        monkeypatch.chdir(tmp_path)
        _write_pyproject(tmp_path / "pyproject.toml", ["fastapi==0.129.0"])
        _write_lock(tmp_path / "requirements.lock", ["uvicorn==0.40.0"])
        mod = _verify_lock_module()
        assert mod.main() == 1

    def test_version_mismatch_strict_pin(self, tmp_path, monkeypatch):
        """Lock file has wrong version for an exact-pin dep → exit 1."""
        monkeypatch.chdir(tmp_path)
        _write_pyproject(tmp_path / "pyproject.toml", ["fastapi==0.129.0"])
        _write_lock(tmp_path / "requirements.lock", ["fastapi==0.128.0"])
        mod = _verify_lock_module()
        assert mod.main() == 1

    def test_compatible_release_mismatch(self, tmp_path, monkeypatch):
        """Lock file version is incompatible with ~= constraint → exit 1."""
        monkeypatch.chdir(tmp_path)
        _write_pyproject(tmp_path / "pyproject.toml", ["aiohttp~=3.13.3"])
        _write_lock(tmp_path / "requirements.lock", ["aiohttp==4.0.0"])
        mod = _verify_lock_module()
        assert mod.main() == 1

    def test_extras_handling(self, tmp_path, monkeypatch):
        """Extras in dep string are handled transparently → exit 0."""
        monkeypatch.chdir(tmp_path)
        _write_pyproject(tmp_path / "pyproject.toml", ["sqlalchemy[asyncio]~=2.0.37"])
        _write_lock(tmp_path / "requirements.lock", ["sqlalchemy==2.0.40"])
        mod = _verify_lock_module()
        assert mod.main() == 0

    def test_inline_comment_in_dep(self, tmp_path, monkeypatch):
        """Inline comments in dependency strings are ignored → exit 0."""
        monkeypatch.chdir(tmp_path)
        content = (
            '[project]\nname = "test"\nversion = "1.0.0"\n'
            'dependencies = [\n    "requests==2.32.3  # HTTP client",\n]\n'
        )
        (tmp_path / "pyproject.toml").write_text(content)
        _write_lock(tmp_path / "requirements.lock", ["requests==2.32.3"])
        mod = _verify_lock_module()
        assert mod.main() == 0

    def test_missing_requirements_lock(self, tmp_path, monkeypatch):
        """Missing requirements.lock → exit 1."""
        monkeypatch.chdir(tmp_path)
        _write_pyproject(tmp_path / "pyproject.toml", ["fastapi==0.129.0"])
        # do NOT create requirements.lock
        mod = _verify_lock_module()
        assert mod.main() == 1

    def test_missing_pyproject_toml(self, tmp_path, monkeypatch):
        """Missing pyproject.toml → exit 1."""
        monkeypatch.chdir(tmp_path)
        _write_lock(tmp_path / "requirements.lock", ["fastapi==0.129.0"])
        # do NOT create pyproject.toml
        mod = _verify_lock_module()
        assert mod.main() == 1


# ---------------------------------------------------------------------------
# Tests for scripts/verify_version_sync.py
# ---------------------------------------------------------------------------


def _write_package_json(path: Path, version: str) -> None:
    """Write a minimal frontend/package.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"name": "frontend", "version": version}))


class TestVerifyVersionSyncHelpers:
    """Tests for get_pyproject_version and get_frontend_version."""

    def test_get_pyproject_version_returns_version(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_pyproject(tmp_path / "pyproject.toml", [], version="2.2.0")
        mod = _verify_version_sync_module()
        assert mod.get_pyproject_version() == "2.2.0"

    def test_get_pyproject_version_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mod = _verify_version_sync_module()
        assert mod.get_pyproject_version() is None

    def test_get_frontend_version_returns_version(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_package_json(tmp_path / "frontend" / "package.json", "2.2.0")
        mod = _verify_version_sync_module()
        assert mod.get_frontend_version() == "2.2.0"

    def test_get_frontend_version_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mod = _verify_version_sync_module()
        assert mod.get_frontend_version() is None


class TestVerifyVersionSyncMain:
    """Integration tests for verify_version_sync.main()."""

    def test_happy_path_versions_match(self, tmp_path, monkeypatch):
        """Both files have same version → exit 0."""
        monkeypatch.chdir(tmp_path)
        _write_pyproject(tmp_path / "pyproject.toml", [], version="2.2.0")
        _write_package_json(tmp_path / "frontend" / "package.json", "2.2.0")
        mod = _verify_version_sync_module()
        assert mod.main() == 0

    def test_version_mismatch(self, tmp_path, monkeypatch):
        """pyproject.toml and package.json have different versions → exit 1."""
        monkeypatch.chdir(tmp_path)
        _write_pyproject(tmp_path / "pyproject.toml", [], version="2.2.0")
        _write_package_json(tmp_path / "frontend" / "package.json", "2.1.0")
        mod = _verify_version_sync_module()
        assert mod.main() == 1

    def test_missing_package_json(self, tmp_path, monkeypatch):
        """Missing frontend/package.json → exit 1."""
        monkeypatch.chdir(tmp_path)
        _write_pyproject(tmp_path / "pyproject.toml", [], version="2.2.0")
        # do NOT create frontend/package.json
        mod = _verify_version_sync_module()
        assert mod.main() == 1

    def test_missing_pyproject_toml(self, tmp_path, monkeypatch):
        """Missing pyproject.toml → exit 1."""
        monkeypatch.chdir(tmp_path)
        _write_package_json(tmp_path / "frontend" / "package.json", "2.2.0")
        # do NOT create pyproject.toml
        mod = _verify_version_sync_module()
        assert mod.main() == 1
