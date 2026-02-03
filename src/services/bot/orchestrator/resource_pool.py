"""Generic round-robin resource pool for country-based resource rotation."""

from typing import TypeVar, Generic, List, Dict, Any, Optional
import asyncio
import logging

T = TypeVar('T')
logger = logging.getLogger(__name__)


class ResourcePool(Generic[T]):
    """
    Generic round-robin resource pool.
    Her ülke için bağımsız index tutarak rotasyon yapar.
    
    Kullanım:
        account_pool = ResourcePool[Account](accounts)
        proxy_pool = ResourcePool[Proxy](proxies)
        
        # Her ülke için bağımsız rotasyon
        fra_account = await account_pool.get_next("fra")  # A1
        nld_account = await account_pool.get_next("nld")  # A2
        bel_account = await account_pool.get_next("bel")  # A3
        
        # Sonraki döngüde
        fra_account = await account_pool.get_next("fra")  # A4 (devam ediyor)
        nld_account = await account_pool.get_next("nld")  # A1 (devam ediyor)
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
        Round-robin ile ülkeye özel sıradaki kaynağı döndür.
        Her ülke farklı offset ile başlar.
        
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
            
            # İlk kez bu ülke için istek geliyorsa, offset hesapla
            if country not in self.country_indices:
                # Her ülke için farklı başlangıç noktası
                countries_count = len(self.country_indices)
                initial_offset = countries_count % len(self.resources)
                self.country_indices[country] = initial_offset
                logger.debug(
                    f"ResourcePool[{self.name}] initialized country '{country}' "
                    f"with offset {initial_offset}"
                )
            
            # Mevcut index'teki kaynağı al
            idx = self.country_indices[country]
            resource = self.resources[idx]
            
            # Sonraki döngü için index'i güncelle
            self.country_indices[country] = (idx + 1) % len(self.resources)
            
            logger.debug(
                f"ResourcePool[{self.name}] returned index {idx} for country '{country}'"
            )
            
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
