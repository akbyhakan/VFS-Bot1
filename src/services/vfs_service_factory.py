"""Factory for creating appropriate VFS service based on user type."""

import logging
from typing import Union

from src.models.user import User
from src.services.bot_service import VFSBot
from src.services.vfs_api_client import VFSApiClient
from src.services.captcha_solver import CaptchaSolver

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
        captcha_solver: CaptchaSolver
    ) -> Union[VFSBot, VFSApiClient]:
        """
        Create appropriate VFS service for user.
        
        Args:
            user: User making the request
            config: Bot configuration
            captcha_solver: Captcha solver instance
            
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
            return VFSBot(config=config)
    
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
