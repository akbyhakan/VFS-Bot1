#!/usr/bin/env python3
"""Verify version synchronization between pyproject.toml, frontend/package.json, and src/__init__.py."""

import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def get_pyproject_version():
    """Get version from pyproject.toml."""
    pyproject_file = Path("pyproject.toml")
    if not pyproject_file.exists():
        print("❌ pyproject.toml not found")
        return None

    with open(pyproject_file, "rb") as f:
        pyproject_data = tomllib.load(f)

    version = pyproject_data.get("project", {}).get("version")
    if not version:
        print("❌ version field not found in pyproject.toml")
        return None

    return version


def get_frontend_version():
    """Get version from frontend/package.json."""
    package_json_file = Path("frontend/package.json")
    if not package_json_file.exists():
        print("❌ frontend/package.json not found")
        return None

    with open(package_json_file) as f:
        package_data = json.load(f)

    version = package_data.get("version")
    if not version:
        print("❌ version field not found in frontend/package.json")
        return None

    return version


def get_init_version():
    """Get version from src/__init__.py."""
    init_file = Path("src/__init__.py")
    if not init_file.exists():
        print("❌ src/__init__.py not found")
        return None

    with open(init_file) as f:
        for line in f:
            match = re.match(r'^__version__\s*=\s*["\']([^"\']+)["\']', line)
            if match:
                return match.group(1)

    print("❌ __version__ not found in src/__init__.py")
    return None


def main():
    """Main function to verify version synchronization."""
    pyproject_version = get_pyproject_version()
    frontend_version = get_frontend_version()
    init_version = get_init_version()

    if pyproject_version is None or frontend_version is None or init_version is None:
        return 1

    versions = {
        "pyproject.toml": pyproject_version,
        "frontend/package.json": frontend_version,
        "src/__init__.py": init_version,
    }
    unique_versions = set(versions.values())

    if len(unique_versions) > 1:
        print("❌ Version mismatch detected:")
        for source, version in versions.items():
            print(f"   {source:<30} {version}")
        print("\n⚠️  Please ensure all files have the same version")
        return 1

    print(
        f"✅ Version {pyproject_version} is in sync across pyproject.toml, frontend/package.json, and src/__init__.py"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
