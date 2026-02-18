"""Tests for packaging metadata and pyproject.toml validation."""

import re
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


class TestPackagingMetadata:
    """Tests for pyproject.toml packaging metadata."""

    def test_build_system_exists(self):
        """Test that [build-system] section exists in pyproject.toml."""
        pyproject_file = Path("pyproject.toml")
        assert pyproject_file.exists(), "pyproject.toml not found"

        with open(pyproject_file, "rb") as f:
            pyproject_data = tomllib.load(f)

        assert "build-system" in pyproject_data, "[build-system] section missing"
        build_system = pyproject_data["build-system"]
        assert "requires" in build_system, "build-system.requires missing"
        assert "build-backend" in build_system, "build-system.build-backend missing"
        assert isinstance(build_system["requires"], list), "build-system.requires must be a list"
        assert len(build_system["requires"]) > 0, "build-system.requires is empty"

    def test_dependencies_exist(self):
        """Test that dependencies field exists and is not empty."""
        pyproject_file = Path("pyproject.toml")
        assert pyproject_file.exists(), "pyproject.toml not found"

        with open(pyproject_file, "rb") as f:
            pyproject_data = tomllib.load(f)

        assert "project" in pyproject_data, "[project] section missing"
        project = pyproject_data["project"]
        assert "dependencies" in project, "dependencies field missing"
        assert isinstance(project["dependencies"], list), "dependencies must be a list"
        assert len(project["dependencies"]) > 0, "dependencies list is empty"

    def test_requires_python_exists(self):
        """Test that requires-python field exists."""
        pyproject_file = Path("pyproject.toml")
        assert pyproject_file.exists(), "pyproject.toml not found"

        with open(pyproject_file, "rb") as f:
            pyproject_data = tomllib.load(f)

        project = pyproject_data.get("project", {})
        assert "requires-python" in project, "requires-python field missing"
        assert isinstance(project["requires-python"], str), "requires-python must be a string"
        assert len(project["requires-python"]) > 0, "requires-python is empty"

    def test_optional_dependencies_dev_exists(self):
        """Test that dev optional dependencies exist."""
        pyproject_file = Path("pyproject.toml")
        assert pyproject_file.exists(), "pyproject.toml not found"

        with open(pyproject_file, "rb") as f:
            pyproject_data = tomllib.load(f)

        project = pyproject_data.get("project", {})
        assert "optional-dependencies" in project, "[project.optional-dependencies] missing"
        optional_deps = project["optional-dependencies"]
        assert "dev" in optional_deps, "[project.optional-dependencies.dev] missing"
        assert isinstance(optional_deps["dev"], list), "dev dependencies must be a list"
        assert len(optional_deps["dev"]) > 0, "dev dependencies list is empty"


class TestDependencySynchronization:
    """Tests for dependency verification with pyproject.toml and requirements.lock."""

    def parse_package_name(self, dep_string):
        """Extract package name from a dependency string.

        Handles extras like sqlalchemy[asyncio] and inline comments.
        """
        # Remove inline comments
        if "#" in dep_string:
            dep_string = dep_string.split("#")[0].strip()

        if "[" in dep_string:
            return dep_string.split("[")[0].lower()
        else:
            match = re.match(r"^([a-zA-Z0-9_-]+)", dep_string)
            if match:
                return match.group(1).lower()
        return None

    def test_lock_file_consistency(self):
        """Test that requirements.lock exists and contains pinned versions from pyproject.toml."""
        pyproject_file = Path("pyproject.toml")
        lock_file = Path("requirements.lock")

        assert pyproject_file.exists(), "pyproject.toml not found"
        assert lock_file.exists(), "requirements.lock not found"

        # Parse pyproject.toml
        with open(pyproject_file, "rb") as f:
            pyproject_data = tomllib.load(f)

        pyproject_deps = pyproject_data.get("project", {}).get("dependencies", [])
        assert len(pyproject_deps) > 0, "No dependencies found in pyproject.toml"

        pyproject_packages = set()
        for dep in pyproject_deps:
            pkg = self.parse_package_name(dep)
            if pkg:
                pyproject_packages.add(pkg)

        # Parse requirements.lock
        with open(lock_file) as f:
            lock_lines = [
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#") and "==" in line
            ]

        lock_packages = {}
        for line in lock_lines:
            if "==" not in line:
                continue
            pkg, version = line.split("==", 1)
            lock_packages[pkg.lower()] = version

        # Check that key packages from pyproject.toml exist in requirements.lock
        # We test a sampling of critical packages that represent different package types:
        # - fastapi: web framework (strict pin)
        # - playwright: browser automation (range pin)
        # - uvicorn: ASGI server (strict pin)
        # - pydantic: data validation (strict pin)
        # These are foundational to the application and unlikely to be removed.
        critical_packages = ["fastapi", "playwright", "uvicorn", "pydantic"]
        for pkg in critical_packages:
            # Normalize package names for comparison
            found = False
            for lock_pkg in lock_packages:
                if lock_pkg.replace("_", "-").replace(".", "-") == pkg.replace("_", "-").replace(
                    ".", "-"
                ):
                    found = True
                    # Verify it has a pinned version
                    assert (
                        len(lock_packages[lock_pkg]) > 0
                    ), f"Package {pkg} has empty version in lock file"
                    break
            assert found, f"Critical package {pkg} not found in requirements.lock"

    def test_version_sync(self):
        """Test that pyproject.toml version matches frontend/package.json version."""
        import json

        pyproject_file = Path("pyproject.toml")
        package_json_file = Path("frontend/package.json")

        assert pyproject_file.exists(), "pyproject.toml not found"
        assert package_json_file.exists(), "frontend/package.json not found"

        # Get pyproject.toml version
        with open(pyproject_file, "rb") as f:
            pyproject_data = tomllib.load(f)

        pyproject_version = pyproject_data.get("project", {}).get("version")
        assert pyproject_version, "version not found in pyproject.toml"

        # Get frontend/package.json version
        with open(package_json_file) as f:
            package_data = json.load(f)

        frontend_version = package_data.get("version")
        assert frontend_version, "version not found in frontend/package.json"

        # Verify they match
        assert pyproject_version == frontend_version, (
            f"Version mismatch: pyproject.toml has {pyproject_version}, "
            f"frontend/package.json has {frontend_version}"
        )

    def test_project_metadata_complete(self):
        """Test that all required project metadata fields exist."""
        pyproject_file = Path("pyproject.toml")
        assert pyproject_file.exists(), "pyproject.toml not found"

        with open(pyproject_file, "rb") as f:
            pyproject_data = tomllib.load(f)

        project = pyproject_data.get("project", {})
        required_fields = ["name", "version", "description", "requires-python"]

        for field in required_fields:
            assert field in project, f"Required field '{field}' missing from [project]"
            assert project[field] and len(str(project[field])) > 0, f"Field '{field}' is empty"
