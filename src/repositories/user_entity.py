"""User entity model."""

from typing import Any, Dict


class User:
    """User entity model."""

    def __init__(
        self,
        id: int,
        email: str,
        phone: str,
        first_name: str,
        last_name: str,
        center_name: str,
        visa_category: str,
        visa_subcategory: str,
        is_active: bool,
        created_at: str,
        updated_at: str,
    ):
        """Initialize user entity."""
        self.id = id
        self.email = email
        self.phone = phone
        self.first_name = first_name
        self.last_name = last_name
        self.center_name = center_name
        self.visa_category = visa_category
        self.visa_subcategory = visa_subcategory
        self.is_active = is_active
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary."""
        return {
            "id": self.id,
            "email": self.email,
            "phone": self.phone,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "center_name": self.center_name,
            "visa_category": self.visa_category,
            "visa_subcategory": self.visa_subcategory,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
