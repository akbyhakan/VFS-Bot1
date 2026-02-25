"""Backward compatibility stub for user_repository.

UserRepository has been renamed to AccountPoolRepository.
This module provides compatibility aliases for existing code.
"""

from src.repositories.account_pool_repository import AccountPoolRepository

# Backward compatibility alias
UserRepository = AccountPoolRepository


class User:
    """Stub User entity for backward compatibility."""

    def __init__(self, **kwargs):
        """Initialize with any kwargs."""
        for k, v in kwargs.items():
            setattr(self, k, v)
