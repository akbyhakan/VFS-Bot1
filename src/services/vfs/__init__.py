"""VFS API Client - Modular package for VFS Global API integration."""

from src.services.vfs.client import VFSApiClient
from src.services.vfs.encryption import (
    VFSPasswordEncryption,
    get_contentful_base,
    get_vfs_api_base,
    get_vfs_assets_base,
)
from src.services.vfs.models import (
    BookingResponse,
    CentreInfo,
    SlotAvailability,
    VFSSession,
    VisaCategoryInfo,
    VisaSubcategoryInfo,
)

__all__ = [
    "VFSApiClient",
    "VFSPasswordEncryption",
    "VFSSession",
    "SlotAvailability",
    "CentreInfo",
    "VisaCategoryInfo",
    "VisaSubcategoryInfo",
    "BookingResponse",
    "get_vfs_api_base",
    "get_vfs_assets_base",
    "get_contentful_base",
]
