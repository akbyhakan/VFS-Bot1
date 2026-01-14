"""Factory for creating appropriate VFS service based on user type."""

import logging
from typing import Union, Optional, Any, Dict
import asyncio

from src.models.user import User
from src.services.bot_service import VFSBot
from src.services.vfs_api_client import VFSApiClient
from src.services.captcha_solver import CaptchaSolver
from src.models.database import Database
from src.services.notification import NotificationService

logger = logging.getLogger(__name__)


class VFSServiceFactory:
    """
    Factory to create VFS service based on user role.
    
    - Normal users: VFSBot (Playwright browser)
    - Test users: VFSApiClient (Direct API)
    """
    
    @staticmethod
    async def create_service(
        user: User,
        config: dict,
        captcha_solver: CaptchaSolver,
        db: Optional[Database] = None,
        notifier: Optional[NotificationService] = None,
        shutdown_event: Optional[asyncio.Event] = None
    ) -> Union[VFSBot, VFSApiClient]:
        """
        Create appropriate VFS service for user.
        
        Args:
            user: User making the request
            config: Bot configuration
            captcha_solver: Captcha solver instance
            db: Database instance (required for VFSBot)
            notifier: Notification service (required for VFSBot)
            shutdown_event: Shutdown event (optional for VFSBot)
            
        Returns:
            VFSBot for normal users, VFSApiClient for testers
        """
        mission_code = config.get("vfs", {}).get("mission", "nld")
        
        if user.uses_direct_api:
            logger.info(
                f"Creating VFSApiClient for test user: {user.email} "
                f"(role: {user.role.value})"
            )
            return VFSApiClient(
                mission_code=mission_code,
                captcha_solver=captcha_solver,
                timeout=config.get("bot", {}).get("timeout", 30)
            )
        else:
            logger.info(
                f"Creating VFSBot (browser) for user: {user.email} "
                f"(role: {user.role.value})"
            )
            # For browser mode, we need db and notifier
            if db is None:
                raise ValueError("Database instance required for browser mode")
            if notifier is None:
                raise ValueError("Notification service required for browser mode")
                
            return VFSBot(
                config=config,
                db=db,
                notifier=notifier,
                shutdown_event=shutdown_event
            )
    
    @staticmethod
    def get_service_type(user: User) -> str:
        """
        Get service type name for user.
        
        Args:
            user: User to check
            
        Returns:
            "api" for testers, "browser" for normal users
        """
        return "api" if user.uses_direct_api else "browser"
