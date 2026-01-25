"""Proxy management routes for VFS-Bot web application."""

import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.utils.security.netnut_proxy import NetNutProxyManager
from web.dependencies import verify_jwt_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/proxy", tags=["proxy"])

# Global proxy manager instance
# Note: This is safe for concurrent access as FastAPI handles requests
# independently. For production use with multiple worker processes,
# consider using a shared cache (Redis) or database backend.
proxy_manager = NetNutProxyManager()


class ProxyStats(BaseModel):
    """Proxy statistics response model."""

    total: int
    active: int
    failed: int


class ProxyInfo(BaseModel):
    """Proxy information response model."""

    endpoint: str
    host: str
    port: int
    username: str
    status: str


class ProxyListResponse(BaseModel):
    """Proxy list response model."""

    proxies: List[ProxyInfo]
    stats: ProxyStats


@router.post("/upload")
async def upload_proxy_csv(
    file: UploadFile = File(...),
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
):
    """
    Upload proxy CSV file.

    Expected CSV format:
    endpoint
    server:port:username:password

    Args:
        file: CSV file upload
        token_data: Verified token data

    Returns:
        Success message with number of proxies loaded
    """
    try:
        # Validate file type
        if not file.filename or not file.filename.endswith(".csv"):
            raise HTTPException(
                status_code=400, detail="Invalid file type. Only CSV files are allowed."
            )

        # Read file content
        content = await file.read()
        
        # Validate file size (max 10MB)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB",
            )
        
        csv_content = content.decode("utf-8")

        # Clear existing proxies before loading new ones
        proxy_manager.clear_all()

        # Load proxies from CSV content
        count = proxy_manager.load_from_csv_content(csv_content)

        if count == 0:
            raise HTTPException(
                status_code=400,
                detail="No valid proxies found in CSV file. "
                "Check format: server:port:username:password",
            )

        logger.info(f"Uploaded {count} proxies from {file.filename}")

        return {
            "message": f"Successfully uploaded {count} proxies",
            "count": count,
            "filename": file.filename,
        }

    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Use UTF-8.")
    except Exception as e:
        logger.error(f"Failed to upload proxy CSV: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload proxy file: {str(e)}")


@router.get("/list", response_model=ProxyListResponse)
async def get_proxy_list(token_data: Dict[str, Any] = Depends(verify_jwt_token)):
    """
    Get list of all proxies with their status.

    Args:
        token_data: Verified token data

    Returns:
        List of proxies with statistics
    """
    try:
        proxies = proxy_manager.get_proxy_list()
        stats = proxy_manager.get_stats()

        return ProxyListResponse(
            proxies=[ProxyInfo(**p) for p in proxies],
            stats=ProxyStats(**stats),
        )

    except Exception as e:
        logger.error(f"Failed to get proxy list: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve proxy list")


@router.get("/stats", response_model=ProxyStats)
async def get_proxy_stats(token_data: Dict[str, Any] = Depends(verify_jwt_token)):
    """
    Get proxy statistics.

    Args:
        token_data: Verified token data

    Returns:
        Proxy statistics (total, active, failed)
    """
    try:
        stats = proxy_manager.get_stats()
        return ProxyStats(**stats)

    except Exception as e:
        logger.error(f"Failed to get proxy stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve proxy statistics")


@router.delete("/clear")
async def clear_proxies(token_data: Dict[str, Any] = Depends(verify_jwt_token)):
    """
    Clear all proxies.

    Args:
        token_data: Verified token data

    Returns:
        Success message
    """
    try:
        proxy_manager.clear_all()
        logger.info("Cleared all proxies via API")

        return {"message": "All proxies cleared successfully"}

    except Exception as e:
        logger.error(f"Failed to clear proxies: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear proxies")
