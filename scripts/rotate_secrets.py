#!/usr/bin/env python3
"""Secret rotation management script for VFS-Bot.

This script helps manage API key rotation and cleanup.
Usage:
    python scripts/rotate_secrets.py --check
    python scripts/rotate_secrets.py --cleanup-expired-keys
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.security import APIKeyManager
from loguru import logger


# Configuration constants
ROTATION_WARNING_THRESHOLD_DAYS = 60


def check_key_ages():
    """Check and report the age of API keys."""
    print("\n=== API Key Age Check ===\n")
    
    manager = APIKeyManager()
    manager.load_keys()
    
    # Access internal keys dict (this is for admin script)
    if not manager._keys:
        print("No API keys found in the system.")
        return
    
    current_time = datetime.now(timezone.utc)
    warnings = []
    
    for key_hash, metadata in manager._keys.items():
        name = metadata.get("name", "unknown")
        created_str = metadata.get("created")
        rotated_str = metadata.get("rotated_at")
        grace_until_str = metadata.get("rotation_grace_until")
        
        print(f"Key: {name}")
        
        if created_str:
            try:
                created = datetime.fromisoformat(created_str)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                age_days = (current_time - created).days
                print(f"  Created: {created_str} ({age_days} days ago)")
                
                if age_days > ROTATION_WARNING_THRESHOLD_DAYS:
                    warnings.append(f"⚠️  Key '{name}' is {age_days} days old (consider rotation)")
            except (ValueError, TypeError):
                print(f"  Created: {created_str} (invalid format)")
        
        if rotated_str:
            print(f"  Last Rotated: {rotated_str}")
        
        if grace_until_str:
            try:
                grace_until = datetime.fromisoformat(grace_until_str)
                if grace_until.tzinfo is None:
                    grace_until = grace_until.replace(tzinfo=timezone.utc)
                
                if current_time > grace_until:
                    print(f"  Grace Period: Expired at {grace_until_str}")
                    warnings.append(f"⚠️  Key '{name}' grace period has expired")
                else:
                    hours_left = (grace_until - current_time).total_seconds() / 3600
                    print(f"  Grace Period: Until {grace_until_str} ({hours_left:.1f} hours left)")
            except (ValueError, TypeError):
                print(f"  Grace Period: {grace_until_str} (invalid format)")
        
        print()
    
    if warnings:
        print("\n=== Warnings ===\n")
        for warning in warnings:
            print(warning)
        print()
        return 1
    else:
        print("✓ All keys are within acceptable age limits\n")
        return 0


def cleanup_expired_keys():
    """Clean up expired API keys."""
    print("\n=== Cleaning up expired API keys ===\n")
    
    manager = APIKeyManager()
    manager.load_keys()
    
    count = manager.cleanup_expired_keys()
    
    if count > 0:
        print(f"✓ Removed {count} expired API key(s)\n")
    else:
        print("✓ No expired keys to remove\n")
    
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Secret rotation management for VFS-Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check API key ages and rotation status
  python scripts/rotate_secrets.py --check
  
  # Clean up expired API keys
  python scripts/rotate_secrets.py --cleanup-expired-keys
        """
    )
    
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check API key ages and rotation status"
    )
    
    parser.add_argument(
        "--cleanup-expired-keys",
        action="store_true",
        help="Remove expired API keys"
    )
    
    args = parser.parse_args()
    
    # Ensure at least one action is specified
    if not (args.check or args.cleanup_expired_keys):
        parser.print_help()
        return 1
    
    exit_code = 0
    
    if args.check:
        exit_code = check_key_ages()
    
    if args.cleanup_expired_keys:
        cleanup_exit = cleanup_expired_keys()
        exit_code = max(exit_code, cleanup_exit)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
