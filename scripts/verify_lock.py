#!/usr/bin/env python3
"""Verify requirements.lock is consistent with requirements.txt."""

import re
import sys
from pathlib import Path


def main():
    """Verify requirements.lock consistency with requirements.txt."""
    # Read requirements.txt and extract main packages with their constraints
    req_file = Path("requirements.txt")
    if not req_file.exists():
        print("❌ requirements.txt not found")
        return 1

    with open(req_file) as f:
        req_lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    # Parse package names and version constraints from requirements.txt
    req_packages = {}
    for line in req_lines:
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
        req_packages[pkg] = constraint.strip()

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
        print("\n".join(errors))
        print(
            f"\n⚠️  Found {len(errors)} issue(s). Run 'make lock' to regenerate requirements.lock"
        )
        return 1
    else:
        print(
            "✅ All package versions in requirements.lock are consistent with requirements.txt"
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
