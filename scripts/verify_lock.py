#!/usr/bin/env python3
"""Verify requirements.lock is consistent with pyproject.toml."""

import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def parse_package_name(dep_string):
    """Extract package name from a dependency string.

    Handles extras like sqlalchemy[asyncio] and inline comments.
    """
    # Remove inline comments
    if "#" in dep_string:
        dep_string = dep_string.split("#")[0].strip()

    if "[" in dep_string:  # Handle extras
        return dep_string.split("[")[0].lower()
    else:
        match = re.match(r"^([a-zA-Z0-9_-]+)", dep_string)
        if match:
            return match.group(1).lower()
    return None


def extract_constraint(dep_string):
    """Extract version constraint from a dependency string."""
    # Remove inline comments
    if "#" in dep_string:
        dep_string = dep_string.split("#")[0].strip()

    # Handle extras like sqlalchemy[asyncio]~=2.0.37
    if "[" in dep_string and "]" in dep_string:
        # Get everything after the closing bracket
        constraint = dep_string.split("]")[1].strip()
    else:
        # Get everything after the package name
        match = re.match(r"^([a-zA-Z0-9_-]+)", dep_string)
        if match:
            constraint = dep_string[len(match.group(1)) :].strip()
        else:
            constraint = ""

    return constraint


def main():
    """Verify requirements.lock consistency with pyproject.toml."""
    # Read pyproject.toml
    pyproject_file = Path("pyproject.toml")
    if not pyproject_file.exists():
        print("❌ pyproject.toml not found")
        return 1

    with open(pyproject_file, "rb") as f:
        pyproject_data = tomllib.load(f)

    pyproject_deps = pyproject_data.get("project", {}).get("dependencies", [])
    if not pyproject_deps:
        print("⚠️  No dependencies found in pyproject.toml [project.dependencies]")
        return 1

    # Parse dependencies from pyproject.toml
    pyproject_packages = {}
    for dep in pyproject_deps:
        pkg = parse_package_name(dep)
        if pkg:
            constraint = extract_constraint(dep)
            pyproject_packages[pkg] = constraint

    # Read requirements.lock
    lock_file = Path("requirements.lock")
    if not lock_file.exists():
        print("❌ requirements.lock not found")
        return 1

    with open(lock_file) as f:
        lock_lines = [
            line.strip() for line in f if line.strip() and not line.startswith("#") and "==" in line
        ]

    lock_packages = {}
    for line in lock_lines:
        if "==" not in line:
            continue
        pkg, version = line.split("==", 1)
        lock_packages[pkg.lower()] = version

    # Check critical packages from pyproject.toml
    errors = []
    for pkg, constraint in pyproject_packages.items():
        # Normalize package name (handle different separators)
        pkg_norm = pkg.replace("_", "-").replace(".", "-")
        lock_pkg = None
        for lpkg in lock_packages:
            if lpkg.replace("_", "-").replace(".", "-") == pkg_norm:
                lock_pkg = lpkg
                break

        if not lock_pkg:
            errors.append(f"❌ {pkg} missing from requirements.lock")
            continue

        lock_version = lock_packages[lock_pkg]

        # Validate version constraints
        if "==" in constraint:
            expected = constraint.replace("==", "")
            if lock_version != expected:
                errors.append(f"❌ {pkg}: expected version {expected}, got {lock_version}")
        elif "~=" in constraint:
            expected_base = constraint.replace("~=", "")
            # Compatible release: should match major.minor
            base_version = expected_base.rsplit(".", 1)[0]
            if not lock_version.startswith(base_version):
                errors.append(f"❌ {pkg}: ~={expected_base} not compatible with {lock_version}")

    if errors:
        print("\n🔍 requirements.lock validation issues:")
        print("\n".join(errors))
        print(
            f"\n⚠️  Found {len(errors)} issue(s). "
            "Run 'make lock' to regenerate requirements.lock"
        )
        return 1
    else:
        print("✅ All package versions in requirements.lock are consistent with pyproject.toml")
        return 0


if __name__ == "__main__":
    sys.exit(main())
