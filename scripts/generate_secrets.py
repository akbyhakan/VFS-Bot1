#!/usr/bin/env python3
"""Generate secure secrets for VFS-Bot configuration."""

import secrets
from cryptography.fernet import Fernet


def generate_all_secrets():
    """Generate all required secrets for VFS-Bot."""
    print("=" * 60)
    print("VFS-Bot Secret Generator")
    print("=" * 60)
    print("\nCopy these values to your .env file:\n")

    print(f"ENCRYPTION_KEY={Fernet.generate_key().decode()}")
    print(f"API_SECRET_KEY={secrets.token_urlsafe(32)}")
    print(f"DASHBOARD_API_KEY={secrets.token_urlsafe(32)}")
    print(f"ADMIN_PASSWORD={secrets.token_urlsafe(24)}")
    print(f"ADMIN_SECRET={secrets.token_urlsafe(16)}")

    print("\n" + "=" * 60)
    print("⚠️  Keep these values secure and never commit them to git!")
    print("=" * 60)


if __name__ == "__main__":
    generate_all_secrets()
