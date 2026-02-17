#!/usr/bin/env python3
"""Verify requirements.lock is consistent with requirements.txt."""

import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def parse_requirements_txt(file_path):
    """Parse requirements from a requirements.txt file."""
    with open(file_path) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    packages = {}
    for line in lines:
        if "[" in line:  # Handle extras like sqlalchemy[asyncio]
            pkg = line.split("[")[0].lower()
            constraint = line.split("]")[1] if "]" in line else ""
        else:
            match = re.match(r"^([a-zA-Z0-9_-]+)", line)
            if match:
                pkg = match.group(1).lower()
                constraint = line[len(match.group(1)) :]
            else:
                continue
        packages[pkg] = constraint.strip()
    return packages


def verify_pyproject_sync():
    """Verify pyproject.toml dependencies are in sync with requirements.txt."""
    pyproject_file = Path("pyproject.toml")
    req_file = Path("requirements.txt")

    if not pyproject_file.exists():
        print("⚠️  pyproject.toml not found, skipping sync check")
        return True

    if not req_file.exists():
        print("❌ requirements.txt not found")
        return False

    # Parse pyproject.toml
    with open(pyproject_file, "rb") as f:
        pyproject_data = tomllib.load(f)

    pyproject_deps = pyproject_data.get("project", {}).get("dependencies", [])
    if not pyproject_deps:
        print("⚠️  No dependencies found in pyproject.toml [project.dependencies]")
        return False

    # Parse dependencies from pyproject.toml
    pyproject_packages = {}
    for dep in pyproject_deps:
        if "[" in dep:  # Handle extras
            pkg = dep.split("[")[0].lower()
            constraint = dep.split("]")[1] if "]" in dep else ""
        else:
            match = re.match(r"^([a-zA-Z0-9_-]+)", dep)
            if match:
                pkg = match.group(1).lower()
                constraint = dep[len(match.group(1)) :]
            else:
                continue
        pyproject_packages[pkg] = constraint.strip()

    # Parse requirements.txt
    req_packages = parse_requirements_txt(req_file)

    # Compare packages
    errors = []

    # Check for packages in pyproject.toml but not in requirements.txt
    for pkg in pyproject_packages:
        if pkg not in req_packages:
            errors.append(
                f"❌ {pkg} is in pyproject.toml but missing from requirements.txt"
            )

    # Check for packages in requirements.txt but not in pyproject.toml
    for pkg in req_packages:
        if pkg not in pyproject_packages:
            errors.append(
                f"❌ {pkg} is in requirements.txt but missing from pyproject.toml"
            )

    # Check for version constraint mismatches
    for pkg in pyproject_packages:
        if pkg in req_packages:
            pyproject_constraint = pyproject_packages[pkg]
            req_constraint = req_packages[pkg]
            # Normalize constraints for comparison
            if pyproject_constraint != req_constraint:
                errors.append(
                    f"⚠️  {pkg}: version constraint mismatch - "
                    f"pyproject.toml has '{pyproject_constraint}', "
                    f"requirements.txt has '{req_constraint}'"
                )

    if errors:
        print("\n🔍 pyproject.toml ↔ requirements.txt synchronization issues:")
        print("\n".join(errors))
        print(
            "\n⚠️  Please ensure both files have the same dependencies with matching version constraints"
        )
        return False
    else:
        print("✅ pyproject.toml dependencies are in sync with requirements.txt")
        return True


def main():
    """Verify requirements.lock consistency with requirements.txt."""
    # First verify pyproject.toml sync
    pyproject_sync_ok = verify_pyproject_sync()

    # Read requirements.txt and extract main packages with their constraints
    req_file = Path("requirements.txt")
    if not req_file.exists():
        print("❌ requirements.txt not found")
        return 1

    req_packages = parse_requirements_txt(req_file)

    # Read requirements.lock and extract versions
    lock_file = Path("requirements.lock")
    if not lock_file.exists():
        print("❌ requirements.lock not found")
        return 1

    with open(lock_file) as f:
        lock_lines = [
            l.strip() for l in f if l.strip() and not l.startswith("#") and "==" in l
        ]

    lock_packages = {}
    for line in lock_lines:
        if "==" not in line:
            continue
        pkg, version = line.split("==", 1)
        lock_packages[pkg.lower()] = version

    # Check critical packages from requirements.txt
    errors = []
    for pkg, constraint in req_packages.items():
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
                errors.append(
                    f"❌ {pkg}: expected version {expected}, got {lock_version}"
                )
        elif "~=" in constraint:
            expected_base = constraint.replace("~=", "")
            # Compatible release: should match major.minor
            base_version = expected_base.rsplit(".", 1)[0]
            if not lock_version.startswith(base_version):
                errors.append(
                    f"❌ {pkg}: ~={expected_base} not compatible with {lock_version}"
                )

    if errors:
        print("\n🔍 requirements.lock validation issues:")
        print("\n".join(errors))
        print(
            f"\n⚠️  Found {len(errors)} issue(s). Run 'make lock' to regenerate requirements.lock"
        )
        return 1
    else:
        print("✅ All package versions in requirements.lock are consistent with requirements.txt")

    # Return non-zero if pyproject.toml sync failed
    return 0 if pyproject_sync_ok else 1


if __name__ == "__main__":
    sys.exit(main())
