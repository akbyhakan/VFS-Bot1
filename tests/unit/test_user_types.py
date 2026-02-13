"""Tests for user type definitions."""

import pytest

from src.types.user import UserDict, UserDictWithOptionals


def test_user_dict_basic():
    """Test that UserDict can be instantiated with required fields."""
    user: UserDict = {
        "id": 1,
        "email": "test@example.com",
        "password": "secret",
        "centre": "Istanbul",
        "category": "Tourist",
        "subcategory": "Tourist Visa",
    }

    assert user["id"] == 1
    assert user["email"] == "test@example.com"
    assert user["centre"] == "Istanbul"


def test_user_dict_with_optionals():
    """Test that UserDictWithOptionals can include optional fields."""
    user: UserDictWithOptionals = {
        "id": 2,
        "email": "user@example.com",
        "password": "secret123",
        "centre": "Ankara",
        "category": "Business",
        "subcategory": "Business Visa",
        "country": "Turkey",
        "active": True,
        "phone": "+905551234567",
    }

    assert user["id"] == 2
    assert user.get("country") == "Turkey"
    assert user.get("active") is True
    assert user.get("phone") == "+905551234567"


def test_user_dict_with_optionals_partial():
    """Test that UserDictWithOptionals works with only some optional fields."""
    user: UserDictWithOptionals = {
        "id": 3,
        "email": "partial@example.com",
        "password": "pass",
        "centre": "Izmir",
        "category": "Student",
        "subcategory": "Student Visa",
        "country": "Turkey",  # Only one optional field
    }

    assert user["id"] == 3
    assert user.get("country") == "Turkey"
    assert user.get("active") is None  # Not set
    assert user.get("phone") is None  # Not set


def test_user_dict_structure_compatibility():
    """Test that dict literals are structurally compatible with UserDict."""
    from typing import cast

    # This is how user dicts are created from database queries
    db_row = {
        "id": 4,
        "email": "db@example.com",
        "password": "dbpass",
        "centre": "Bursa",
        "category": "Work",
        "subcategory": "Work Permit",
    }

    # Cast demonstrates runtime compatibility - dict from DB can be used as UserDict
    user: UserDict = cast(UserDict, db_row)

    assert user["id"] == 4
    assert user["category"] == "Work"
