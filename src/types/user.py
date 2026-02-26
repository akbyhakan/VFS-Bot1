"""Type definitions for VFS account data structures."""

from typing_extensions import TypedDict


class VFSAccountDict(TypedDict):
    """Type-safe dictionary for VFS account data from vfs_account_pool table."""

    id: int
    email: str
    password: str
    phone: str


class VFSAccountDictWithOptionals(VFSAccountDict, total=False):
    """Extended VFS account dict with optional fields."""

    status: str
    is_active: bool
    created_at: str
    updated_at: str
