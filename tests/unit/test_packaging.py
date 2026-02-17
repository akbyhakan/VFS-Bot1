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
    """Tests for dependency synchronization between pyproject.toml and requirements.txt."""

    def parse_requirements(self, file_path):
        """Parse requirements from a file."""
        packages = {}
        with open(file_path) as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

        for line in lines:
            if "[" in line:  # Handle extras like sqlalchemy[asyncio]
                pkg = line.split("[")[0].lower()
            else:
                match = re.match(r"^([a-zA-Z0-9_-]+)", line)
                if match:
                    pkg = match.group(1).lower()
                else:
                    continue
            packages[pkg] = line
        return packages

    def test_pyproject_requirements_sync(self):
        """Test that pyproject.toml dependencies match requirements.txt."""
        pyproject_file = Path("pyproject.toml")
        req_file = Path("requirements.txt")

        assert pyproject_file.exists(), "pyproject.toml not found"
        assert req_file.exists(), "requirements.txt not found"

        # Parse pyproject.toml
        with open(pyproject_file, "rb") as f:
            pyproject_data = tomllib.load(f)

        pyproject_deps = pyproject_data.get("project", {}).get("dependencies", [])
        pyproject_packages = set()
        for dep in pyproject_deps:
            if "[" in dep:
                pkg = dep.split("[")[0].lower()
            else:
                match = re.match(r"^([a-zA-Z0-9_-]+)", dep)
                if match:
                    pkg = match.group(1).lower()
                else:
                    continue
            pyproject_packages.add(pkg)

        # Parse requirements.txt
        req_packages = set(self.parse_requirements(req_file).keys())

        # Check for missing packages
        missing_in_req = pyproject_packages - req_packages
        missing_in_pyproject = req_packages - pyproject_packages

        assert (
            len(missing_in_req) == 0
        ), f"Packages in pyproject.toml but not in requirements.txt: {missing_in_req}"
        assert (
            len(missing_in_pyproject) == 0
        ), f"Packages in requirements.txt but not in pyproject.toml: {missing_in_pyproject}"

    def test_pyproject_dev_requirements_sync(self):
        """Test that pyproject.toml dev dependencies match requirements-dev.txt."""
        pyproject_file = Path("pyproject.toml")
        req_dev_file = Path("requirements-dev.txt")

        assert pyproject_file.exists(), "pyproject.toml not found"
        assert req_dev_file.exists(), "requirements-dev.txt not found"

        # Parse pyproject.toml
        with open(pyproject_file, "rb") as f:
            pyproject_data = tomllib.load(f)

        dev_deps = pyproject_data.get("project", {}).get("optional-dependencies", {}).get("dev", [])
        pyproject_dev_packages = set()
        for dep in dev_deps:
            if "[" in dep:
                pkg = dep.split("[")[0].lower()
            else:
                match = re.match(r"^([a-zA-Z0-9_-]+)", dep)
                if match:
                    pkg = match.group(1).lower()
                else:
                    continue
            pyproject_dev_packages.add(pkg)

        # Parse requirements-dev.txt
        req_dev_packages = set(self.parse_requirements(req_dev_file).keys())

        # Check for missing packages
        missing_in_req_dev = pyproject_dev_packages - req_dev_packages
        missing_in_pyproject = req_dev_packages - pyproject_dev_packages

        assert (
            len(missing_in_req_dev) == 0
        ), f"Packages in pyproject.toml [dev] but not in requirements-dev.txt: {missing_in_req_dev}"
        assert (
            len(missing_in_pyproject) == 0
        ), f"Packages in requirements-dev.txt but not in pyproject.toml [dev]: {missing_in_pyproject}"

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
