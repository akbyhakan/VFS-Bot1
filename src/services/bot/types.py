"""Type definitions for VFS booking services."""

from typing import List, Optional, TypedDict

from ...core.sensitive import SensitiveDict


class PersonDict(TypedDict, total=False):
    """Person information for visa application.
    
    Attributes:
        first_name: Person's first name
        last_name: Person's last name
        gender: Gender (male/female)
        birth_date: Date of birth in DD/MM/YYYY format
        passport_number: Passport number
        passport_expiry_date: Passport expiry date in DD/MM/YYYY format
        phone_code: Phone country code (e.g., "90")
        phone_number: Phone number without country code
        email: Email address
        is_child_with_parent: Whether child is traveling with parent
    """

    first_name: str
    last_name: str
    gender: str
    birth_date: str
    passport_number: str
    passport_expiry_date: str
    phone_code: str
    phone_number: str
    email: str
    is_child_with_parent: bool


class ReservationDict(TypedDict, total=False):
    """Reservation data for appointment booking.
    
    Attributes:
        person_count: Number of persons in the booking
        preferred_dates: List of preferred appointment dates in DD/MM/YYYY format
        persons: List of person information dictionaries
        payment_card: Payment card information (wrapped in SensitiveDict)
    """

    person_count: int
    preferred_dates: List[str]
    persons: List[PersonDict]
    payment_card: Optional[SensitiveDict]
