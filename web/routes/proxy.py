"""Proxy management routes for VFS-Bot web application."""

import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from src.models.database import Database
from src.utils.security.netnut_proxy import NetNutProxyManager
from web.dependencies import (
    verify_jwt_token,
    ProxyCreateRequest,
    ProxyUpdateRequest,
    ProxyResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/proxy", tags=["proxy"])

# Global proxy manager instance
# Note: This is safe for concurrent access as FastAPI handles requests
# independently. For production use with multiple worker processes,
# consider using a shared cache (Redis) or database backend.
proxy_manager = NetNutProxyManager()


# Response models
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


# Helper to get database instance
async def get_db() -> Database:
    """Get database instance for dependency injection."""
    db = Database()
    await db.connect()
    try:
        yield db
    finally:
        await db.close()


# ================================================================================
# CRUD Endpoints
# ================================================================================


@router.post("/add", response_model=ProxyResponse)
async def add_proxy(
    proxy: ProxyCreateRequest,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db: Database = Depends(get_db),
):
    """
    Add a single proxy endpoint.

    Args:
        proxy: Proxy details
        token_data: Verified token data
        db: Database instance

    Returns:
        Created proxy details (password excluded)
    """
    try:
        # Validate port range
        if not (1 <= proxy.port <= 65535):
            raise HTTPException(
                status_code=400, detail="Port must be between 1 and 65535"
            )

        # Add to database
        proxy_id = await db.add_proxy(
            server=proxy.server,
            port=proxy.port,
            username=proxy.username,
            password=proxy.password,
        )

        # Fetch the created proxy
        created_proxy = await db.get_proxy_by_id(proxy_id)
        if not created_proxy:
            raise HTTPException(status_code=500, detail="Failed to retrieve created proxy")

        logger.info(f"Proxy added: {proxy.server}:{proxy.port} (ID: {proxy_id})")

        # Return without password
        return ProxyResponse(
            id=created_proxy["id"],
            server=created_proxy["server"],
            port=created_proxy["port"],
            username=created_proxy["username"],
            is_active=bool(created_proxy["is_active"]),
            failure_count=created_proxy["failure_count"],
            last_used=created_proxy.get("last_used"),
            created_at=created_proxy["created_at"],
            updated_at=created_proxy["updated_at"],
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add proxy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add proxy: {str(e)}")


@router.get("/list")
async def list_proxies(
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db: Database = Depends(get_db),
):
    """
    Get list of all proxies (passwords excluded).

    Args:
        token_data: Verified token data
        db: Database instance

    Returns:
        List of all proxies with metadata
    """
    try:
        # Get all active proxies
        proxies = await db.get_active_proxies()

        # Convert to response format (exclude passwords)
        proxy_list = [
            ProxyResponse(
                id=p["id"],
                server=p["server"],
                port=p["port"],
                username=p["username"],
                is_active=bool(p["is_active"]),
                failure_count=p["failure_count"],
                last_used=p.get("last_used"),
                created_at=p["created_at"],
                updated_at=p["updated_at"],
            )
            for p in proxies
        ]

        # Get stats
        stats = await db.get_proxy_stats()

        return {
            "proxies": proxy_list,
            "stats": stats,
        }

    except Exception as e:
        logger.error(f"Failed to list proxies: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve proxy list")


@router.get("/{proxy_id}", response_model=ProxyResponse)
async def get_proxy(
    proxy_id: int,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db: Database = Depends(get_db),
):
    """
    Get a single proxy by ID (password excluded).

    Args:
        proxy_id: Proxy ID
        token_data: Verified token data
        db: Database instance

    Returns:
        Proxy details
    """
    try:
        proxy = await db.get_proxy_by_id(proxy_id)

        if not proxy:
            raise HTTPException(status_code=404, detail=f"Proxy {proxy_id} not found")

        return ProxyResponse(
            id=proxy["id"],
            server=proxy["server"],
            port=proxy["port"],
            username=proxy["username"],
            is_active=bool(proxy["is_active"]),
            failure_count=proxy["failure_count"],
            last_used=proxy.get("last_used"),
            created_at=proxy["created_at"],
            updated_at=proxy["updated_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get proxy {proxy_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve proxy")


@router.put("/{proxy_id}", response_model=ProxyResponse)
async def update_proxy(
    proxy_id: int,
    proxy: ProxyUpdateRequest,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db: Database = Depends(get_db),
):
    """
    Update a proxy endpoint.

    Args:
        proxy_id: Proxy ID
        proxy: Update data
        token_data: Verified token data
        db: Database instance

    Returns:
        Updated proxy details
    """
    try:
        # Validate port if provided
        if proxy.port is not None and not (1 <= proxy.port <= 65535):
            raise HTTPException(
                status_code=400, detail="Port must be between 1 and 65535"
            )

        # Update proxy
        updated = await db.update_proxy(
            proxy_id=proxy_id,
            server=proxy.server,
            port=proxy.port,
            username=proxy.username,
            password=proxy.password,
            is_active=proxy.is_active,
        )

        if not updated:
            raise HTTPException(status_code=404, detail=f"Proxy {proxy_id} not found")

        # Fetch updated proxy
        updated_proxy = await db.get_proxy_by_id(proxy_id)
        if not updated_proxy:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated proxy")

        logger.info(f"Proxy {proxy_id} updated")

        return ProxyResponse(
            id=updated_proxy["id"],
            server=updated_proxy["server"],
            port=updated_proxy["port"],
            username=updated_proxy["username"],
            is_active=bool(updated_proxy["is_active"]),
            failure_count=updated_proxy["failure_count"],
            last_used=updated_proxy.get("last_used"),
            created_at=updated_proxy["created_at"],
            updated_at=updated_proxy["updated_at"],
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update proxy {proxy_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update proxy: {str(e)}")


@router.delete("/{proxy_id}")
async def delete_proxy(
    proxy_id: int,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db: Database = Depends(get_db),
):
    """
    Delete a proxy endpoint.

    Args:
        proxy_id: Proxy ID
        token_data: Verified token data
        db: Database instance

    Returns:
        Success message
    """
    try:
        deleted = await db.delete_proxy(proxy_id)

        if not deleted:
            raise HTTPException(status_code=404, detail=f"Proxy {proxy_id} not found")

        logger.info(f"Proxy {proxy_id} deleted")

        return {"message": f"Proxy {proxy_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete proxy {proxy_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete proxy")


@router.delete("/clear-all")
async def clear_all_proxies(
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db: Database = Depends(get_db),
):
    """
    Delete all proxy endpoints.

    Args:
        token_data: Verified token data
        db: Database instance

    Returns:
        Success message with count
    """
    try:
        count = await db.clear_all_proxies()

        logger.info(f"Cleared all {count} proxies")

        return {
            "message": f"Successfully deleted {count} proxies",
            "count": count,
        }

    except Exception as e:
        logger.error(f"Failed to clear all proxies: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear proxies")


@router.post("/reset-failures")
async def reset_proxy_failures(
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db: Database = Depends(get_db),
):
    """
    Reset failure count for all proxies.

    Args:
        token_data: Verified token data
        db: Database instance

    Returns:
        Success message with count
    """
    try:
        count = await db.reset_proxy_failures()

        logger.info(f"Reset failures for {count} proxies")

        return {
            "message": f"Reset failure count for {count} proxies",
            "count": count,
        }

    except Exception as e:
        logger.error(f"Failed to reset proxy failures: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset proxy failures")


# ================================================================================
# Legacy CSV Upload Endpoint (Updated for DB Integration)
# ================================================================================

@router.post("/upload")
async def upload_proxy_csv(
    file: UploadFile = File(...),
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db: Database = Depends(get_db),
):
    """
    Upload proxy CSV file and store in database.

    Expected CSV format:
    endpoint
    server:port:username:password

    Args:
        file: CSV file upload
        token_data: Verified token data
        db: Database instance

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

        # Parse CSV and add to database
        lines = csv_content.strip().split("\n")
        
        # Check if first line is header
        if lines and lines[0].strip().lower() == "endpoint":
            lines = lines[1:]  # Skip header
        
        count = 0
        errors = []
        
        for line_num, line in enumerate(lines, start=2):  # Start at 2 since we skipped header
            endpoint = line.strip()
            if not endpoint or endpoint.startswith("#"):
                continue

            # Parse endpoint: server:port:username:password
            parts = endpoint.split(":")
            if len(parts) != 4:
                errors.append(f"Line {line_num}: Invalid format (expected server:port:username:password)")
                continue

            server, port_str, username, password = parts

            try:
                port = int(port_str)
                if not (1 <= port <= 65535):
                    errors.append(f"Line {line_num}: Port must be between 1 and 65535")
                    continue
            except ValueError:
                errors.append(f"Line {line_num}: Invalid port number '{port_str}'")
                continue

            # Add to database
            try:
                await db.add_proxy(
                    server=server,
                    port=port,
                    username=username,
                    password=password,
                )
                count += 1
            except ValueError as e:
                # Proxy already exists - log but continue
                logger.warning(f"Line {line_num}: {e}")
                errors.append(f"Line {line_num}: {str(e)}")
                continue

        if count == 0 and not errors:
            raise HTTPException(
                status_code=400,
                detail="No valid proxies found in CSV file. "
                "Check format: server:port:username:password",
            )

        logger.info(f"Uploaded {count} proxies from {file.filename}")

        response_data = {
            "message": f"Successfully uploaded {count} proxies",
            "count": count,
            "filename": file.filename,
        }

        if errors:
            response_data["warnings"] = errors[:10]  # Limit to first 10 errors
            if len(errors) > 10:
                response_data["warnings"].append(f"... and {len(errors) - 10} more errors")

        return response_data

    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Use UTF-8.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload proxy CSV: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload proxy file: {str(e)}")


# ================================================================================
# Legacy In-Memory Manager Endpoints (Kept for backwards compatibility)
# ================================================================================


@router.get("/memory/list", response_model=ProxyListResponse)
async def get_memory_proxy_list(token_data: Dict[str, Any] = Depends(verify_jwt_token)):
    """
    Get list of all proxies from in-memory manager (legacy).

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


@router.get("/memory/stats", response_model=ProxyStats)
async def get_memory_proxy_stats(token_data: Dict[str, Any] = Depends(verify_jwt_token)):
    """
    Get proxy statistics from in-memory manager (legacy).

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


@router.delete("/memory/clear")
async def clear_memory_proxies(token_data: Dict[str, Any] = Depends(verify_jwt_token)):
    """
    Clear all proxies from in-memory manager (legacy).

    Args:
        token_data: Verified token data

    Returns:
        Success message
    """
    try:
        proxy_manager.clear_all()
        logger.info("Cleared all in-memory proxies via API")

        return {"message": "All in-memory proxies cleared successfully"}

    except Exception as e:
        logger.error(f"Failed to clear proxies: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear proxies")


@router.get("/stats", response_model=Dict[str, Any])
async def get_combined_stats(
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db: Database = Depends(get_db),
):
    """
    Get combined proxy statistics from both database and in-memory manager.

    Args:
        token_data: Verified token data
        db: Database instance

    Returns:
        Combined statistics
    """
    try:
        db_stats = await db.get_proxy_stats()
        memory_stats = proxy_manager.get_stats()

        return {
            "database": db_stats,
            "memory": memory_stats,
        }

    except Exception as e:
        logger.error(f"Failed to get combined stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")

