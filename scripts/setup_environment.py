#!/usr/bin/env python3
"""Interactive environment setup."""

from cryptography.fernet import Fernet
from passlib.context import CryptContext
import secrets


def main():
    print("=== VFS-Bot Environment Setup ===\n")
    
    # Generate keys
    encryption_key = Fernet.generate_key().decode()
    api_secret = secrets.token_urlsafe(32)
    
    # Get user input
    vfs_email = input("VFS Email: ")
    vfs_password = input("VFS Password: ")
    admin_password = input("Admin Password: ")
    
    # Hash admin password
    pwd_context = CryptContext(schemes=["bcrypt"])
    admin_hash = pwd_context.hash(admin_password)
    
    # Write .env
    with open(".env", "w") as f:
        f.write(f"VFS_EMAIL={vfs_email}\n")
        f.write(f"VFS_PASSWORD={vfs_password}\n")
        f.write(f"ENCRYPTION_KEY={encryption_key}\n")
        f.write(f"API_SECRET_KEY={api_secret}\n")
        f.write(f"ADMIN_PASSWORD={admin_hash}\n")
    
    print("\n✅ .env file created")
    print("Run: python main.py")


if __name__ == "__main__":
    main()
