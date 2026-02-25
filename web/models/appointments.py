"""Appointment models for VFS-Bot web application."""

from typing import List, Optional

from pydantic import BaseModel


class AppointmentPersonRequest(BaseModel):
    """Appointment person request model."""

    first_name: str
    last_name: str
    gender: str  # "female" | "male"
    nationality: str = "Turkey"
    birth_date: str  # Format: DD/MM/YYYY
    passport_number: str
    passport_issue_date: str  # Format: DD/MM/YYYY
    passport_expiry_date: str  # Format: DD/MM/YYYY
    phone_code: str = "90"
    phone_number: str  # Without leading 0
    email: str
    is_child_with_parent: bool = False  # Child checkbox


class AppointmentRequestCreate(BaseModel):
    """Appointment request creation model."""

    country_code: str
    visa_category: str
    visa_subcategory: str
    centres: List[str]
    preferred_dates: List[str]  # Format: DD/MM/YYYY
    person_count: int
    persons: List[AppointmentPersonRequest]


class AppointmentPersonResponse(BaseModel):
    """Appointment person response model."""

    id: int
    first_name: str
    last_name: str
    gender: str
    nationality: str
    birth_date: str
    passport_number: str
    passport_issue_date: str
    passport_expiry_date: str
    phone_code: str
    phone_number: str
    email: str
    is_child_with_parent: bool


class AppointmentRequestResponse(BaseModel):
    """Appointment request response model."""

    id: int
    country_code: str
    visa_category: str
    visa_subcategory: str
    centres: List[str]
    preferred_dates: List[str]
    person_count: int
    status: str
    created_at: str
    completed_at: Optional[str] = None
    booked_date: Optional[str] = None
    persons: List[AppointmentPersonResponse]
