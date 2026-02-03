"""Main orchestrator for managing country-based reservation workers."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .resource_pool import ResourcePool
from .reservation_worker import ReservationWorker

logger = logging.getLogger(__name__)


class ReservationOrchestrator:
    """
    Ana koordinatör sınıfı.
    
    - Aktif rezervasyonları yönetir
    - Her rezervasyon için ayrı worker başlatır
    - Hesap ve proxy pool'larını paylaştırır
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        db: Any,
        notifier: Any,
    ):
        """
        Initialize orchestrator.
        
        Args:
            config: Bot configuration
            db: Database instance
            notifier: Notification service
        """
        self.config = config
        self.db = db
        self.notifier = notifier
        
        # Resource pools
        self.account_pool: Optional[ResourcePool] = None
        self.proxy_pool: Optional[ResourcePool] = None
        
        # Active workers
        self.workers: Dict[str, ReservationWorker] = {}  # country -> worker
        self.worker_tasks: Dict[str, asyncio.Task] = {}  # country -> task
        
        self.running = False
        
        logger.info("ReservationOrchestrator initialized")
    
    async def start(self) -> None:
        """Start the orchestrator."""
        self.running = True
        logger.info("Orchestrator starting...")
        
        # Initialize pools
        await self._initialize_pools()
        
        # Start monitoring loop
        await self._run_monitoring_loop()
    
    async def stop(self) -> None:
        """Stop all workers and cleanup."""
        self.running = False
        logger.info("Orchestrator stopping...")
        
        # Stop all workers
        for country, worker in self.workers.items():
            await worker.stop()
        
        # Cancel all tasks
        for country, task in self.worker_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.workers.clear()
        self.worker_tasks.clear()
        
        logger.info("Orchestrator stopped")
    
    async def _initialize_pools(self) -> None:
        """Initialize account and proxy pools from database."""
        # Load accounts
        accounts = await self.db.get_active_users_with_decrypted_passwords()
        self.account_pool = ResourcePool(accounts, name="accounts")
        
        # Load proxies
        proxies = await self._load_proxies()
        self.proxy_pool = ResourcePool(proxies, name="proxies")
        
        logger.info(
            f"Pools initialized: {len(accounts)} accounts, {len(proxies)} proxies"
        )
    
    async def _load_proxies(self) -> List[Dict[str, Any]]:
        """Load proxies from database or file."""
        # Önce DB'den dene
        try:
            proxies = await self.db.get_active_proxies()
            if proxies:
                return proxies
        except Exception:
            pass
        
        # Fallback: ProxyManager'dan yükle
        from ...utils.security.proxy_manager import ProxyManager
        proxy_manager = ProxyManager(self.config.get("proxy", {}))
        return proxy_manager.proxies if proxy_manager.proxies else [{}]  # Empty dict = no proxy
    
    async def _run_monitoring_loop(self) -> None:
        """Monitor reservations and manage workers."""
        while self.running:
            try:
                # Get active reservations from database
                reservations = await self._get_active_reservations()
                
                # Start workers for new reservations
                active_countries = set()
                for reservation in reservations:
                    country = reservation.get("mission_code") or reservation.get("country")
                    if not country:
                        continue
                    
                    active_countries.add(country)
                    
                    if country not in self.workers:
                        await self._start_worker(reservation)
                
                # Stop workers for removed reservations
                for country in list(self.workers.keys()):
                    if country not in active_countries:
                        await self._stop_worker(country)
                
                # Refresh pools periodically
                await self._refresh_pools()
                
                # Wait before next check
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _get_active_reservations(self) -> List[Dict[str, Any]]:
        """Get active reservations from database."""
        # Try to get from database if method exists
        try:
            if hasattr(self.db, 'get_active_reservations'):
                return await self.db.get_active_reservations()
        except Exception as e:
            logger.warning(f"Could not get active reservations: {e}")
        
        # Fallback: Return empty list or use config
        # This can be extended to read from config file
        return []
    
    async def _start_worker(self, reservation: Dict[str, Any]) -> None:
        """Start a worker for a reservation."""
        country = reservation.get("mission_code") or reservation.get("country")
        reservation_id = reservation.get("id")
        
        if country in self.workers:
            logger.warning(f"Worker for {country} already exists")
            return
        
        worker = ReservationWorker(
            reservation_id=reservation_id,
            country=country,
            config=self.config,
            account_pool=self.account_pool,
            proxy_pool=self.proxy_pool,
            db=self.db,
            notifier=self.notifier,
        )
        
        self.workers[country] = worker
        self.worker_tasks[country] = asyncio.create_task(worker.start())
        
        logger.info(f"Started worker for {country}")
    
    async def _stop_worker(self, country: str) -> None:
        """Stop a worker."""
        if country not in self.workers:
            return
        
        worker = self.workers[country]
        await worker.stop()
        
        if country in self.worker_tasks:
            self.worker_tasks[country].cancel()
            try:
                await self.worker_tasks[country]
            except asyncio.CancelledError:
                pass
            del self.worker_tasks[country]
        
        del self.workers[country]
        logger.info(f"Stopped worker for {country}")
    
    async def _refresh_pools(self) -> None:
        """Refresh account and proxy pools from database."""
        try:
            # Refresh accounts
            accounts = await self.db.get_active_users_with_decrypted_passwords()
            if accounts and self.account_pool:
                self.account_pool.update_resources(accounts)
            
            # Refresh proxies
            proxies = await self._load_proxies()
            if proxies and self.proxy_pool:
                self.proxy_pool.update_resources(proxies)
                
        except Exception as e:
            logger.warning(f"Failed to refresh pools: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            "running": self.running,
            "active_workers": len(self.workers),
            "workers": {
                country: worker.get_stats()
                for country, worker in self.workers.items()
            },
            "account_pool": self.account_pool.get_stats() if self.account_pool else None,
            "proxy_pool": self.proxy_pool.get_stats() if self.proxy_pool else None,
        }
