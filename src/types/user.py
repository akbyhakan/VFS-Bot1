"""Type definitions for user data structures."""

from typing_extensions import TypedDict


class UserDict(TypedDict):
    """Type-safe dictionary for user data from database."""

    id: int
    email: str
    password: str
    centre: str
    category: str
    subcategory: str


class UserDictWithOptionals(UserDict, total=False):
    """Extended user dict with optional fields."""

    country: str
    active: bool
    phone: str
    created_at: str
    updated_at: str
