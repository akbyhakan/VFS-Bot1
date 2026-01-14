"""Input validation schemas using Pydantic."""

import re
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator, Field


class UserCreate(BaseModel):
    """User creation validation schema."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    centre: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=100)
    subcategory: str = Field(..., min_length=1, max_length=100)

    @field_validator("centre", "category", "subcategory")
    @classmethod
    def validate_alphanumeric_with_spaces(cls, v):
        """Validate that fields contain only safe characters."""
        if not re.match(r"^[a-zA-Z0-9\s\-\.,]+$", v):
            raise ValueError(
                "Field contains invalid characters. Only alphanumeric, "
                "spaces, hyphens, dots and commas allowed."
            )
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v):
        """Validate password meets minimum requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class PersonalDetailsCreate(BaseModel):
    """Personal details validation schema."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    passport_number: str = Field(..., min_length=5, max_length=20)
    email: EmailStr
    passport_expiry: Optional[str] = None
    gender: Optional[str] = None
    mobile_code: Optional[str] = None
    mobile_number: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    postcode: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v):
        """Validate name contains only valid characters."""
        if not re.match(r"^[a-zA-ZğüşıöçĞÜŞİÖÇ\s\-]+$", v):
            raise ValueError("Name contains invalid characters")
        return v.strip()

    @field_validator("passport_number")
    @classmethod
    def validate_passport(cls, v):
        """Validate passport number format."""
        if not re.match(r"^[A-Z0-9]+$", v.upper()):
            raise ValueError("Invalid passport number format")
        return v.upper()

    @field_validator("mobile_number")
    @classmethod
    def validate_mobile(cls, v):
        """Validate mobile number format."""
        if v and not re.match(r"^[0-9\+\-\s]+$", v):
            raise ValueError("Invalid mobile number format")
        return v
