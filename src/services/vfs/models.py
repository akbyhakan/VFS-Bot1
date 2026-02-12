"""VFS API Models - TypedDict and dataclass definitions."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, TypedDict


class CentreInfo(TypedDict):
    """Type definition for VFS Centre information."""

    id: str
    name: str
    code: str
    address: str


class VisaCategoryInfo(TypedDict):
    """Type definition for Visa Category information."""

    id: str
    name: str
    code: str


class VisaSubcategoryInfo(TypedDict):
    """Type definition for Visa Subcategory information."""

    id: str
    name: str
    code: str
    visaCategoryId: str


class BookingResponse(TypedDict):
    """Type definition for Appointment Booking response."""

    bookingId: str
    status: str
    message: str


@dataclass
class VFSSession:
    """VFS authenticated session."""

    access_token: str
    refresh_token: str
    expires_at: datetime
    user_id: str
    email: str


@dataclass
class SlotAvailability:
    """Appointment slot availability."""

    available: bool
    dates: List[str]
    centre_id: str
    category_id: str
    message: Optional[str] = None
