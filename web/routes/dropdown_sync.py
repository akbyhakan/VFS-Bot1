"""Dropdown sync routes for VFS-Bot web application."""

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from loguru import logger

from src.constants.countries import SUPPORTED_COUNTRIES
from src.repositories.dropdown_cache_repository import DropdownCacheRepository
from web.dependencies import get_db, verify_jwt_token

router = APIRouter(prefix="/dropdown-sync", tags=["dropdown-sync"])


@router.get("/status")
async def get_all_dropdown_sync_statuses(
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db=Depends(get_db),
):
    """
    Get sync statuses for all countries.

    Returns:
        List of sync statuses for all countries
    """
    try:
        dropdown_cache_repo = DropdownCacheRepository(db)
        
        # Get all sync statuses from database
        db_statuses = await dropdown_cache_repo.get_all_sync_statuses()
        
        # Create a map for quick lookup
        status_map = {status["country_code"]: status for status in db_statuses}
        
        # Build complete list for all supported countries
        all_statuses = []
        for country_code in SUPPORTED_COUNTRIES.keys():
            if country_code in status_map:
                all_statuses.append(status_map[country_code])
            else:
                # Country not yet synced
                all_statuses.append({
                    "country_code": country_code,
                    "sync_status": "pending",
                    "last_synced_at": None,
                    "error_message": None,
                })
        
        return all_statuses
    except Exception as e:
        logger.error(f"Failed to get dropdown sync statuses: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get sync statuses")


@router.get("/{country_code}/status")
async def get_dropdown_sync_status(
    country_code: str,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db=Depends(get_db),
):
    """
    Get sync status for a specific country.

    Args:
        country_code: Country code (e.g., 'fra', 'nld')

    Returns:
        Sync status information
    """
    try:
        # Validate country code
        if country_code not in SUPPORTED_COUNTRIES:
            raise HTTPException(status_code=404, detail="Country not found")
        
        dropdown_cache_repo = DropdownCacheRepository(db)
        status = await dropdown_cache_repo.get_sync_status(country_code)
        
        if status is None:
            # Country not yet synced
            return {
                "country_code": country_code,
                "sync_status": "pending",
                "last_synced_at": None,
                "error_message": None,
            }
        
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sync status for {country_code}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get sync status")


@router.post("/{country_code}")
async def trigger_dropdown_sync(
    country_code: str,
    background_tasks: BackgroundTasks,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db=Depends(get_db),
):
    """
    Trigger dropdown sync for a specific country.

    Args:
        country_code: Country code (e.g., 'fra', 'nld')
        background_tasks: FastAPI background tasks
        token_data: Verified token data
        db: Database instance

    Returns:
        Message indicating sync has been triggered
    """
    try:
        # Validate country code
        if country_code not in SUPPORTED_COUNTRIES:
            raise HTTPException(status_code=404, detail="Country not found")
        
        dropdown_cache_repo = DropdownCacheRepository(db)
        
        # Check if sync is already in progress
        status = await dropdown_cache_repo.get_sync_status(country_code)
        if status and status["sync_status"] == "syncing":
            return {
                "status": "syncing",
                "message": f"Sync already in progress for {country_code}",
            }
        
        # Update status to 'pending' to indicate sync will start
        await dropdown_cache_repo.update_sync_status(country_code, "pending")
        
        # Note: Actual sync implementation would be added here as a background task
        # For now, we'll just update the status
        logger.info(f"Dropdown sync triggered for {country_code} by {token_data.get('sub', 'unknown')}")
        
        return {
            "status": "pending",
            "message": f"Dropdown sync queued for {country_code}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger sync for {country_code}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to trigger sync")


@router.post("/all")
async def trigger_all_dropdown_sync(
    background_tasks: BackgroundTasks,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db=Depends(get_db),
):
    """
    Trigger dropdown sync for all supported countries.

    Args:
        background_tasks: FastAPI background tasks
        token_data: Verified token data
        db: Database instance

    Returns:
        Message indicating sync has been triggered
    """
    try:
        dropdown_cache_repo = DropdownCacheRepository(db)
        
        # Update status to 'pending' for all countries
        pending_count = 0
        for country_code in SUPPORTED_COUNTRIES.keys():
            status = await dropdown_cache_repo.get_sync_status(country_code)
            if not status or status["sync_status"] != "syncing":
                await dropdown_cache_repo.update_sync_status(country_code, "pending")
                pending_count += 1
        
        # Note: Actual sync implementation would be added here as a background task
        logger.info(f"Dropdown sync triggered for all countries by {token_data.get('sub', 'unknown')}")
        
        return {
            "status": "pending",
            "message": f"Dropdown sync queued for {pending_count} countries",
            "total_countries": len(SUPPORTED_COUNTRIES),
        }
    except Exception as e:
        logger.error(f"Failed to trigger sync for all countries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to trigger sync")
