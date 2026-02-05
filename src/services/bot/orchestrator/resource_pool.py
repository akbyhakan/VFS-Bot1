"""Generic round-robin resource pool for country-based resource rotation."""

import asyncio
import logging
from typing import Any, Dict, Generic, List, Optional, TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)


class ResourcePool(Generic[T]):
    """
    Generic round-robin resource pool.
    Maintains independent rotation index for each country.

    Usage:
        account_pool = ResourcePool[Account](accounts)
        proxy_pool = ResourcePool[Proxy](proxies)

        # Independent rotation for each country
        fra_account = await account_pool.get_next("fra")  # A1
        nld_account = await account_pool.get_next("nld")  # A2
        bel_account = await account_pool.get_next("bel")  # A3

        # Next cycle
        fra_account = await account_pool.get_next("fra")  # A4 (continues)
        nld_account = await account_pool.get_next("nld")  # A1 (continues)
    """

    def __init__(self, resources: List[T], name: str = "resource"):
        """
        Initialize resource pool.

        Args:
            resources: List of resources to pool
            name: Pool name for logging
        """
        self.resources = list(resources)
        self.name = name
        self.country_indices: Dict[str, int] = {}
        self.lock = asyncio.Lock()
        logger.info(f"ResourcePool[{name}] initialized with {len(resources)} items")

    async def get_next(self, country: str) -> T:
        """
        Return the next resource in the country-specific round-robin sequence.
        Each country starts with a different offset.

        Args:
            country: Country code (fra, nld, bel, etc.)

        Returns:
            Next resource for this country

        Raises:
            ValueError: If pool is empty
        """
        async with self.lock:
            if not self.resources:
                raise ValueError(f"ResourcePool[{self.name}] is empty")

            # If this is the first request for this country, calculate offset
            if country not in self.country_indices:
                # Different starting point for each country
                countries_count = len(self.country_indices)
                initial_offset = countries_count % len(self.resources)
                self.country_indices[country] = initial_offset
                logger.debug(
                    f"ResourcePool[{self.name}] initialized country '{country}' "
                    f"with offset {initial_offset}"
                )

            # Get resource at current index
            idx = self.country_indices[country]
            resource = self.resources[idx]

            # Update index for next cycle
            self.country_indices[country] = (idx + 1) % len(self.resources)

            logger.debug(f"ResourcePool[{self.name}] returned index {idx} for country '{country}'")

            return resource

    async def get_current(self, country: str) -> Optional[T]:
        """Get current resource for country without advancing."""
        async with self.lock:
            if not self.resources or country not in self.country_indices:
                return None
            idx = self.country_indices[country]
            return self.resources[idx]

    def add_resource(self, resource: T) -> None:
        """Add a new resource to the pool."""
        self.resources.append(resource)
        logger.info(f"ResourcePool[{self.name}] added resource, total: {len(self.resources)}")

    def remove_resource(self, resource: T) -> bool:
        """Remove a resource from the pool."""
        if resource in self.resources:
            self.resources.remove(resource)
            logger.info(f"ResourcePool[{self.name}] removed resource, total: {len(self.resources)}")
            return True
        return False

    def update_resources(self, resources: List[T]) -> None:
        """Replace all resources in the pool."""
        self.resources = list(resources)
        self.country_indices.clear()  # Reset indices
        logger.info(f"ResourcePool[{self.name}] updated with {len(resources)} items")

    def get_all(self) -> List[T]:
        """Get all resources."""
        return self.resources.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "name": self.name,
            "total_resources": len(self.resources),
            "active_countries": list(self.country_indices.keys()),
            "country_indices": dict(self.country_indices),
        }

    def __len__(self) -> int:
        return len(self.resources)
