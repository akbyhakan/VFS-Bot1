#!/usr/bin/env python3
"""Bump version in pyproject.toml and frontend/package.json."""

import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


def get_current_version() -> str:
    """Read current version from pyproject.toml."""
    pyproject_file = Path("pyproject.toml")
    if not pyproject_file.exists():
        print("❌ pyproject.toml not found")
        sys.exit(1)
    with open(pyproject_file, "rb") as f:
        data = tomllib.load(f)
    version = data.get("project", {}).get("version")
    if not version:
        print("❌ version field not found in pyproject.toml")
        sys.exit(1)
    return version


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse a semver string into (major, minor, patch)."""
    parts = version.split(".")
    if len(parts) != 3:
        print(f"❌ Invalid version format: {version} (expected X.Y.Z)")
        sys.exit(1)
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        print(f"❌ Invalid version format: {version} (expected integers)")
        sys.exit(1)


def compute_new_version(arg: str) -> str:
    """Return the new version string given a bump type or explicit version."""
    bump_types = ("major", "minor", "patch")
    if arg in bump_types:
        current = get_current_version()
        major, minor, patch = parse_version(current)
        if arg == "major":
            return f"{major + 1}.0.0"
        if arg == "minor":
            return f"{major}.{minor + 1}.0"
        return f"{major}.{minor}.{patch + 1}"
    # Treat as explicit version
    parse_version(arg)  # validate format
    return arg


def update_pyproject(new_version: str) -> None:
    """Update version in pyproject.toml using regex to preserve formatting."""
    pyproject_file = Path("pyproject.toml")
    content = pyproject_file.read_text(encoding="utf-8")
    new_content, count = re.subn(
        r'^(version\s*=\s*")[^"]*(")',
        rf'\g<1>{new_version}\g<2>',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        print("❌ Could not find version field in pyproject.toml")
        sys.exit(1)
    pyproject_file.write_text(new_content, encoding="utf-8")
    print(f"  ✅ pyproject.toml → {new_version}")


def update_package_json(new_version: str) -> None:
    """Update version in frontend/package.json."""
    package_json_file = Path("frontend/package.json")
    if not package_json_file.exists():
        print("❌ frontend/package.json not found")
        sys.exit(1)
    with open(package_json_file, encoding="utf-8") as f:
        data = json.load(f)
    data["version"] = new_version
    with open(package_json_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"  ✅ frontend/package.json → {new_version}")


def verify_sync() -> None:
    """Run verify_version_sync.py as a post-check."""
    result = subprocess.run(
        [sys.executable, "scripts/verify_version_sync.py"],
        capture_output=True,
        text=True,
    )
    print(result.stdout, end="")
    if result.returncode != 0:
        print(result.stderr, end="")
        print("❌ Version sync verification failed")
        sys.exit(1)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/bump_version.py <version|major|minor|patch>")
        print("Examples:")
        print("  python3 scripts/bump_version.py 2.3.0")
        print("  python3 scripts/bump_version.py patch")
        sys.exit(1)

    arg = sys.argv[1]
    new_version = compute_new_version(arg)

    print(f"📦 Bumping version to {new_version}...")
    update_pyproject(new_version)
    update_package_json(new_version)
    verify_sync()
    print(f"✅ Version bumped to {new_version}")


if __name__ == "__main__":
    main()
