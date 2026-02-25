"""Type definitions for VFS account data structures.

Note: UserDict and UserDictWithOptionals are kept for backward compatibility
with bot services that use them internally. New code should use VFSAccountDict.
"""

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


# Backward compatibility aliases for bot services
UserDict = VFSAccountDict
UserDictWithOptionals = VFSAccountDictWithOptionals
