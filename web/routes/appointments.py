"""Appointment-related routes for VFS-Bot web application."""

import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request

from src.core.enums import AppointmentRequestStatus
from src.core.exceptions import ValidationError
from src.repositories import AppointmentRequestRepository
from web.dependencies import (
    AppointmentRequestCreate,
    AppointmentRequestResponse,
    CountryResponse,
    WebhookUrlsResponse,
    get_appointment_request_repository,
    verify_jwt_token,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/appointments", tags=["appointments"])


@lru_cache(maxsize=1)
def _load_countries_from_yaml() -> Tuple[Dict[str, str], ...]:
    """
    Load countries data from country_profiles.yaml.

    This replaces hardcoded COUNTRIES_DATA to follow DRY principle.

    Returns:
        Tuple of country dictionaries with code, name_en, and name_tr
    """
    yaml_path = Path("config/country_profiles.yaml")
    if not yaml_path.exists():
        logger.warning("country_profiles.yaml not found, returning empty country list")
        return tuple()

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        countries = []
        for code, profile in data.get("country_profiles", {}).items():
            countries.append(
                {
                    "code": code,
                    "name_en": profile.get("name_en", ""),
                    "name_tr": profile.get("name", ""),
                }
            )

        logger.info(f"Loaded {len(countries)} countries from YAML")
        return tuple(countries)
    except Exception as e:
        logger.error(f"Failed to load countries from YAML: {e}")
        return tuple()


# Load countries data from YAML (replaces hardcoded list)
COUNTRIES_DATA = list(_load_countries_from_yaml())


@router.get("/countries", response_model=List[CountryResponse])
async def get_countries():
    """
    Get list of available countries.

    Returns:
        List of countries with codes and names
    """
    return COUNTRIES_DATA


@router.get("/countries/{country_code}/centres")
async def get_country_centres(country_code: str):
    """
    Get list of centres for a specific country.

    Args:
        country_code: Country code (e.g., 'nld', 'aut')

    Returns:
        List of centre names

    Note:
        Currently returns Turkish VFS centres regardless of country_code.
        This is because appointments are made at Turkish VFS centres for
        all destination countries. In the future, this could be dynamically
        fetched from VFS or cached.
    """
    # Turkish VFS centres (same for all countries as applications are made in Turkey)
    centres = ["Istanbul", "Ankara", "Izmir", "Antalya", "Bursa"]
    return centres


@router.post("/appointment-requests", status_code=201)
async def create_appointment_request(
    request_data: AppointmentRequestCreate,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    appt_req_repo: AppointmentRequestRepository = Depends(get_appointment_request_repository),
):
    """
    Create a new appointment request.

    Args:
        request_data: Appointment request data
        token_data: Verified token data
        appt_req_repo: AppointmentRequestRepository instance

    Returns:
        Created appointment request info
    """
    try:
        # Validate person count matches persons list
        if request_data.person_count != len(request_data.persons):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Person count ({request_data.person_count}) does not match "
                    f"number of persons provided ({len(request_data.persons)})"
                ),
            )

        # Build request data dictionary
        appointment_data = {
            "country_code": request_data.country_code,
            "visa_category": request_data.visa_category,
            "visa_subcategory": request_data.visa_subcategory,
            "centres": request_data.centres,
            "preferred_dates": request_data.preferred_dates,
            "person_count": request_data.person_count,
            "persons": [person.dict() for person in request_data.persons],
        }

        # Create request in database
        request_id = await appt_req_repo.create(appointment_data)

        logger.info(
            f"Appointment request {request_id} created by {token_data.get('sub', 'unknown')}"
        )

        return {"id": request_id, "status": "pending", "message": "Talep oluşturuldu"}
    except HTTPException:
        raise
    except ValidationError as e:
        logger.error(f"Validation error creating appointment request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create appointment request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create appointment request")


@router.get("/appointment-requests", response_model=List[AppointmentRequestResponse])
async def get_appointment_requests(
    status: Optional[str] = None,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    appt_req_repo: AppointmentRequestRepository = Depends(get_appointment_request_repository),
):
    """
    Get all appointment requests.

    Args:
        status: Optional status filter
        token_data: Verified token data
        appt_req_repo: AppointmentRequestRepository instance

    Returns:
        List of appointment requests
    """
    try:
        requests = await appt_req_repo.get_all(status=status)

        # Convert to response model
        response_requests = []
        for req in requests:
            # Remove internal fields from persons
            persons = [
                {k: v for k, v in person.items() if k != "request_id" and k != "created_at"}
                for person in req["persons"]
            ]

            response_requests.append(
                AppointmentRequestResponse(
                    id=req["id"],
                    country_code=req["country_code"],
                    visa_category=req["visa_category"],
                    visa_subcategory=req["visa_subcategory"],
                    centres=req["centres"],
                    preferred_dates=req["preferred_dates"],
                    person_count=req["person_count"],
                    status=req["status"],
                    created_at=req["created_at"],
                    completed_at=req.get("completed_at"),
                    persons=persons,
                )
            )

        return response_requests
    except Exception as e:
        logger.error(f"Failed to get appointment requests: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get appointment requests")


@router.get("/appointment-requests/{request_id}", response_model=AppointmentRequestResponse)
async def get_appointment_request(
    request_id: int,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    appt_req_repo: AppointmentRequestRepository = Depends(get_appointment_request_repository),
):
    """
    Get a specific appointment request.

    Args:
        request_id: Request ID
        token_data: Verified token data
        appt_req_repo: AppointmentRequestRepository instance

    Returns:
        Appointment request details
    """
    try:
        req = await appt_req_repo.get_by_id(request_id)

        if not req:
            raise HTTPException(status_code=404, detail="Appointment request not found")

        # Remove internal fields from persons
        persons = [
            {k: v for k, v in person.items() if k != "request_id" and k != "created_at"}
            for person in req["persons"]
        ]

        return AppointmentRequestResponse(
            id=req["id"],
            country_code=req["country_code"],
            visa_category=req["visa_category"],
            visa_subcategory=req["visa_subcategory"],
            centres=req["centres"],
            preferred_dates=req["preferred_dates"],
            person_count=req["person_count"],
            status=req["status"],
            created_at=req["created_at"],
            completed_at=req.get("completed_at"),
            persons=persons,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get appointment request {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get appointment request")


@router.delete("/appointment-requests/{request_id}")
async def delete_appointment_request(
    request_id: int,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    appt_req_repo: AppointmentRequestRepository = Depends(get_appointment_request_repository),
):
    """
    Delete an appointment request.

    Args:
        request_id: Request ID
        token_data: Verified token data
        appt_req_repo: AppointmentRequestRepository instance

    Returns:
        Success message
    """
    try:
        deleted = await appt_req_repo.delete(request_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Appointment request not found")

        logger.info(
            f"Appointment request {request_id} deleted by {token_data.get('sub', 'unknown')}"
        )

        return {"success": True, "message": "Appointment request deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete appointment request {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete appointment request")


@router.patch("/appointment-requests/{request_id}/status")
async def update_appointment_request_status(
    request_id: int,
    status_update: Dict[str, str],
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    appt_req_repo: AppointmentRequestRepository = Depends(get_appointment_request_repository),
):
    """
    Update appointment request status.

    Args:
        request_id: Request ID
        status_update: Dict with 'status' key
        token_data: Verified token data
        appt_req_repo: AppointmentRequestRepository instance

    Returns:
        Success message

    Note:
        When status is set to 'completed', completed_at timestamp is set.
        When status changes from 'completed' to another status, completed_at
        is not cleared as it represents historical data.
    """
    try:
        status = status_update.get("status")
        if not status:
            raise HTTPException(status_code=400, detail="Status is required")

        if status not in AppointmentRequestStatus.values():
            raise HTTPException(status_code=400, detail="Invalid status value")

        # Set completed_at timestamp only when status becomes 'completed'
        completed_at = (
            datetime.now(timezone.utc) if status == AppointmentRequestStatus.COMPLETED else None
        )

        updated = await appt_req_repo.update_status(
            request_id=request_id, status=status, completed_at=completed_at
        )

        if not updated:
            raise HTTPException(status_code=404, detail="Appointment request not found")

        logger.info(
            f"Appointment request {request_id} status updated to {status} "
            f"by {token_data.get('sub', 'unknown')}"
        )

        return {"success": True, "message": f"Status updated to {status}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to update appointment request {request_id} status: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to update status")


@router.get("/settings/webhook-urls", response_model=WebhookUrlsResponse)
async def get_webhook_urls(request: Request):
    """
    Get webhook URLs for SMS forwarding.

    Args:
        request: FastAPI request object

    Returns:
        Webhook URLs with base URL
    """
    # Get base URL from request
    base_url = str(request.base_url).rstrip("/")

    return WebhookUrlsResponse(
        appointment_webhook=f"{base_url}/api/webhook/sms/appointment",
        payment_webhook=f"{base_url}/api/webhook/sms/payment",
        base_url=base_url,
    )
