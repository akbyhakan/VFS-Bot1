"""VFS Global Direct API Client for Turkey."""

import asyncio
import base64
import logging
import secrets
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

import aiohttp
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from ..core.countries import (
    SOURCE_COUNTRY_CODE,
    get_route,
    validate_mission_code,
    get_country_info,
)

logger = logging.getLogger(__name__)


# VFS Global API Base URLs
VFS_API_BASE = "https://lift-api.vfsglobal.com"
VFS_ASSETS_BASE = "https://liftassets.vfsglobal.com"
CONTENTFUL_BASE = "https://d2ab400qlgxn2g.cloudfront.net/dev/spaces"


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


class VFSPasswordEncryption:
    """VFS Global password encryption (AES-256-CBC)."""
    
    # VFS uses a specific encryption key derivation
    ENCRYPTION_KEY = b"vfs_global_lift_encryption_key!!"[:32]  # 32 bytes for AES-256
    
    @classmethod
    def encrypt(cls, password: str) -> str:
        """
        Encrypt password for VFS API.
        
        Args:
            password: Plain text password
            
        Returns:
            Base64 encoded encrypted password
        """
        iv = secrets.token_bytes(16)
        cipher = AES.new(cls.ENCRYPTION_KEY, AES.MODE_CBC, iv)
        padded_data = pad(password.encode('utf-8'), AES.block_size)
        encrypted = cipher.encrypt(padded_data)
        
        # VFS expects IV + encrypted data, base64 encoded
        return base64.b64encode(iv + encrypted).decode('utf-8')


class VFSApiClient:
    """
    Direct API client for VFS Global Turkey.
    
    Supports all 21 Schengen countries that can be applied from Turkey.
    """
    
    def __init__(
        self,
        mission_code: str,
        captcha_solver: Any,
        timeout: int = 30
    ):
        """
        Initialize VFS API client.
        
        Args:
            mission_code: Target country code (fra, nld, hrv, etc.)
            captcha_solver: CaptchaSolver instance for Turnstile
            timeout: Request timeout in seconds
        """
        validate_mission_code(mission_code)
        
        self.mission_code = mission_code
        self.route = get_route(mission_code)
        self.country_info = get_country_info(mission_code)
        self.captcha_solver = captcha_solver
        self.timeout = timeout
        
        self.session: Optional[VFSSession] = None
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._client_source: Optional[str] = None
        
        logger.info(
            f"VFSApiClient initialized for {self.country_info.name_en} "
            f"({self.mission_code}) - Route: {self.route}"
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._init_http_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def _init_http_session(self) -> None:
        """Initialize HTTP session with proper headers."""
        if self._http_session is None:
            self._client_source = self._generate_client_source()
            
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Origin": "https://visa.vfsglobal.com",
                "Referer": f"https://visa.vfsglobal.com/{self.route}/",
                "route": self.route,
                "clientsource": self._client_source,
            }
            
            self._http_session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
    
    def _generate_client_source(self) -> str:
        """Generate clientsource header value."""
        timestamp = int(time.time() * 1000)
        random_part = secrets.token_hex(16)
        return f"{timestamp}-{random_part}-vfs-turkey"
    
    async def close(self) -> None:
        """Close HTTP session."""
        if self._http_session:
            await self._http_session.close()
            self._http_session = None
    
    async def login(
        self,
        email: str,
        password: str,
        turnstile_token: str
    ) -> VFSSession:
        """
        Login to VFS Global.
        
        Args:
            email: User email
            password: User password (plain text, will be encrypted)
            turnstile_token: Solved Cloudflare Turnstile token
            
        Returns:
            VFSSession with tokens
        """
        await self._init_http_session()
        
        encrypted_password = VFSPasswordEncryption.encrypt(password)
        
        payload = {
            "username": email,
            "password": encrypted_password,
            "missioncode": self.mission_code,
            "countrycode": SOURCE_COUNTRY_CODE,
            "captcha_version": "cloudflare-v1",
            "captcha_api_key": turnstile_token,
        }
        
        logger.info(f"Logging in to VFS for mission: {self.mission_code}")
        
        async with self._http_session.post(
            f"{VFS_API_BASE}/user/login",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        ) as response:
            
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"Login failed: {response.status} - {error_text}")
                raise Exception(f"Login failed: {response.status}")
            
            data = await response.json()
            
            self.session = VFSSession(
                access_token=data["accessToken"],
                refresh_token=data.get("refreshToken", ""),
                expires_at=datetime.now(),  # Parse from response
                user_id=data.get("userId", ""),
                email=email
            )
            
            # Update session headers with auth token
            self._http_session.headers.update({
                "Authorization": f"Bearer {self.session.access_token}"
            })
            
            logger.info(f"Login successful for {email[:3]}***")
            return self.session
    
    async def get_centres(self) -> List[Dict[str, Any]]:
        """
        Get available VFS centres.
        
        Returns:
            List of centre information
        """
        await self._ensure_authenticated()
        
        async with self._http_session.get(
            f"{VFS_API_BASE}/master/center"
        ) as response:
            data = await response.json()
            logger.info(f"Retrieved {len(data)} centres")
            return data
    
    async def get_visa_categories(self, centre_id: str) -> List[Dict[str, Any]]:
        """
        Get visa categories for a centre.
        
        Args:
            centre_id: VFS centre ID
            
        Returns:
            List of visa categories
        """
        await self._ensure_authenticated()
        
        async with self._http_session.get(
            f"{VFS_API_BASE}/master/visacategory",
            params={"centerId": centre_id}
        ) as response:
            data = await response.json()
            return data
    
    async def get_visa_subcategories(
        self,
        centre_id: str,
        category_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get visa subcategories.
        
        Args:
            centre_id: VFS centre ID
            category_id: Visa category ID
            
        Returns:
            List of visa subcategories
        """
        await self._ensure_authenticated()
        
        async with self._http_session.get(
            f"{VFS_API_BASE}/master/subvisacategory",
            params={
                "centerId": centre_id,
                "visaCategoryId": category_id
            }
        ) as response:
            data = await response.json()
            return data
    
    async def check_slot_availability(
        self,
        centre_id: str,
        category_id: str,
        subcategory_id: str
    ) -> SlotAvailability:
        """
        Check appointment slot availability.
        
        Args:
            centre_id: VFS centre ID
            category_id: Visa category ID
            subcategory_id: Visa subcategory ID
            
        Returns:
            SlotAvailability with dates if available
        """
        await self._ensure_authenticated()
        
        params = {
            "centerId": centre_id,
            "visaCategoryId": category_id,
            "subVisaCategoryId": subcategory_id,
        }
        
        async with self._http_session.get(
            f"{VFS_API_BASE}/appointment/slots",
            params=params
        ) as response:
            
            if response.status != 200:
                return SlotAvailability(
                    available=False,
                    dates=[],
                    centre_id=centre_id,
                    category_id=category_id,
                    message=f"API error: {response.status}"
                )
            
            data = await response.json()
            
            available_dates = data.get("availableDates", [])
            
            return SlotAvailability(
                available=len(available_dates) > 0,
                dates=available_dates,
                centre_id=centre_id,
                category_id=category_id,
                message=data.get("message")
            )
    
    async def book_appointment(
        self,
        slot_date: str,
        slot_time: str,
        applicant_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Book an appointment.
        
        Args:
            slot_date: Appointment date (YYYY-MM-DD)
            slot_time: Appointment time (HH:MM)
            applicant_data: Applicant information
            
        Returns:
            Booking confirmation
        """
        await self._ensure_authenticated()
        
        payload = {
            "appointmentDate": slot_date,
            "appointmentTime": slot_time,
            **applicant_data
        }
        
        async with self._http_session.post(
            f"{VFS_API_BASE}/appointment/applicants",
            json=payload
        ) as response:
            data = await response.json()
            
            if response.status == 200:
                logger.info(f"Appointment booked: {slot_date} {slot_time}")
            else:
                logger.error(f"Booking failed: {data}")
            
            return data
    
    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid session."""
        if not self.session:
            raise RuntimeError(
                "Not authenticated. Call login() first."
            )
        
        # TODO: Check token expiration and refresh if needed
    
    async def solve_turnstile(self, page_url: str, site_key: str) -> str:
        """
        Solve Cloudflare Turnstile captcha.
        
        Args:
            page_url: Page URL where Turnstile is displayed
            site_key: Turnstile site key
            
        Returns:
            Turnstile token
        """
        return await self.captcha_solver.solve_turnstile(
            page_url=page_url,
            site_key=site_key
        )
