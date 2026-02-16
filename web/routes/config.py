"""Runtime configuration API routes."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from src.core.config.runtime_config import RuntimeConfig
from web.dependencies import verify_admin_token

router = APIRouter(prefix="/config", tags=["config"])


class ConfigUpdateRequest(BaseModel):
    """Request model for updating runtime configuration."""

    key: str = Field(..., description="Configuration key (e.g., 'retries.max_login')")
    value: Any = Field(..., description="New value for the configuration key")

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        """Validate key format."""
        if not v or "." not in v:
            raise ValueError("Key must be in format 'category.parameter'")
        return v


class ConfigResponse(BaseModel):
    """Response model for configuration operations."""

    success: bool = Field(..., description="Whether operation succeeded")
    message: str = Field(..., description="Status message")
    config: Dict[str, Any] = Field(default_factory=dict, description="Current configuration")


@router.get("/runtime", response_model=ConfigResponse, summary="Get runtime configuration")
async def get_runtime_config(
    _: Dict[str, Any] = Depends(verify_admin_token),
) -> ConfigResponse:
    """
    Get all runtime configuration values.

    Requires admin authentication.

    Returns:
        Current runtime configuration as a dictionary
    """
    try:
        config_dict = RuntimeConfig.to_dict()
        logger.info("Runtime configuration retrieved")
        return ConfigResponse(
            success=True,
            message="Runtime configuration retrieved successfully",
            config=config_dict,
        )
    except Exception as e:
        logger.error(f"Failed to retrieve runtime configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve configuration: {str(e)}")


@router.put("/runtime", response_model=ConfigResponse, summary="Update runtime configuration")
async def update_runtime_config(
    request: ConfigUpdateRequest,
    _: Dict[str, Any] = Depends(verify_admin_token),
) -> ConfigResponse:
    """
    Update a runtime configuration value.

    Requires admin authentication.

    Args:
        request: Configuration update request with key and value

    Returns:
        Updated configuration

    Raises:
        HTTPException: If key is invalid or value is invalid type
    """
    try:
        RuntimeConfig.update(request.key, request.value)
        config_dict = RuntimeConfig.to_dict()

        logger.info(f"Runtime configuration updated: {request.key} = {request.value}")

        return ConfigResponse(
            success=True,
            message=f"Configuration '{request.key}' updated successfully",
            config=config_dict,
        )
    except ValueError as e:
        logger.warning(f"Invalid configuration update attempt: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update runtime configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")


@router.get(
    "/runtime/{key}",
    response_model=Dict[str, Any],
    summary="Get specific runtime configuration value",
)
async def get_runtime_config_value(
    key: str,
    _: Dict[str, Any] = Depends(verify_admin_token),
) -> Dict[str, Any]:
    """
    Get a specific runtime configuration value.

    Requires admin authentication.

    Args:
        key: Configuration key (e.g., 'retries.max_login')

    Returns:
        Dictionary with the key and its value

    Raises:
        HTTPException: If key is not found
    """
    try:
        # Get all config to check if key exists
        config_dict = RuntimeConfig.to_dict()
        if key not in config_dict:
            raise HTTPException(status_code=404, detail=f"Configuration key '{key}' not found")

        value = config_dict[key]
        logger.debug(f"Runtime configuration value retrieved: {key} = {value}")

        return {"key": key, "value": value}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve configuration value: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve configuration value: {str(e)}"
        )
