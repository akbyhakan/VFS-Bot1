#!/usr/bin/env python3
"""Verify version synchronization between pyproject.toml and frontend/package.json."""

import json
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


def main():
    """Main function to verify version synchronization."""
    pyproject_version = get_pyproject_version()
    frontend_version = get_frontend_version()

    if pyproject_version is None or frontend_version is None:
        return 1

    if pyproject_version != frontend_version:
        print(f"❌ Version mismatch detected:")
        print(f"   pyproject.toml:          {pyproject_version}")
        print(f"   frontend/package.json:   {frontend_version}")
        print("\n⚠️  Please ensure both files have the same version")
        return 1

    print(f"✅ Version {pyproject_version} is in sync across pyproject.toml and frontend/package.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
