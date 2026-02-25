"""Tests for VFS account type definitions."""

import pytest

from src.types.user import VFSAccountDict, VFSAccountDictWithOptionals, UserDict, UserDictWithOptionals


def test_vfs_account_dict_basic():
    """Test that VFSAccountDict can be instantiated with required fields."""
    account: VFSAccountDict = {
        "id": 1,
        "email": "test@example.com",
        "password": "secret",
        "phone": "+905551234567",
    }

    assert account["id"] == 1
    assert account["email"] == "test@example.com"
    assert account["phone"] == "+905551234567"


def test_vfs_account_dict_with_optionals():
    """Test that VFSAccountDictWithOptionals can include optional fields."""
    account: VFSAccountDictWithOptionals = {
        "id": 2,
        "email": "user@example.com",
        "password": "secret123",
        "phone": "+905559876543",
        "status": "available",
        "is_active": True,
    }

    assert account["id"] == 2
    assert account.get("status") == "available"
    assert account.get("is_active") is True


def test_vfs_account_dict_with_optionals_partial():
    """Test that VFSAccountDictWithOptionals works with only some optional fields."""
    account: VFSAccountDictWithOptionals = {
        "id": 3,
        "email": "partial@example.com",
        "password": "pass",
        "phone": "+905554567890",
        "is_active": True,
    }

    assert account["id"] == 3
    assert account.get("is_active") is True
    assert account.get("status") is None


def test_vfs_account_dict_structure_compatibility():
    """Test that dict literals are structurally compatible with VFSAccountDict."""
    from typing import cast

    db_row = {
        "id": 4,
        "email": "db@example.com",
        "password": "dbpass",
        "phone": "+905551111111",
    }

    account: VFSAccountDict = cast(VFSAccountDict, db_row)

    assert account["id"] == 4
    assert account["email"] == "db@example.com"


def test_user_dict_backward_compat():
    """Test that UserDict is a backward-compatible alias for VFSAccountDict."""
    assert UserDict is VFSAccountDict
    assert UserDictWithOptionals is VFSAccountDictWithOptionals
