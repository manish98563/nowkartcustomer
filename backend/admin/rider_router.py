"""
Admin Rider router — SECURED rider management.
All endpoints require admin JWT authentication with appropriate RBAC.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from rider import service as rider_service
from rider.schemas import (
    PaginatedRidersOut,
    RiderAdminOut,
    RiderCreateIn,
    RiderUpdateIn,
)
from delivery import service as delivery_service
from admin.dependencies import require_min_role
from admin import service as admin_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin-riders"])


@router.post("/riders", response_model=RiderAdminOut, status_code=201)
async def create_rider(
    body: RiderCreateIn,
    admin: dict = Depends(require_min_role("admin")),
):
    """Create a new rider account. Requires admin role or higher."""
    try:
        result = await rider_service.create_rider(body)
        await admin_service.log_action(
            admin, "rider_created", "rider", result.id,
            {"email": result.email, "name": f"{result.firstName} {result.lastName}"},
        )
        return result
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/riders", response_model=PaginatedRidersOut)
async def list_riders(
    status:         Optional[str]  = Query(default=None),
    isActive:       Optional[bool] = Query(default=None),
    storeId:        Optional[str]  = Query(default=None),
    includeDeleted: bool           = Query(default=False),
    limit:  int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: dict = Depends(require_min_role("support")),
):
    """List riders with optional filters. Requires support role or higher."""
    return await rider_service.list_riders(
        status=status, is_active=isActive, store_id=storeId,
        include_deleted=includeDeleted, limit=limit, offset=offset,
    )


@router.get("/riders/{riderId}", response_model=RiderAdminOut)
async def get_rider(riderId: str, admin: dict = Depends(require_min_role("support"))):
    """Full rider detail. Requires support role or higher."""
    try:
        return await rider_service.get_rider_admin_detail(riderId)
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/riders/{riderId}", response_model=RiderAdminOut)
async def update_rider(
    riderId: str, body: RiderUpdateIn,
    admin: dict = Depends(require_min_role("admin")),
):
    """Update rider fields. Requires admin role or higher."""
    try:
        result = await rider_service.update_rider(riderId, body)
        await admin_service.log_action(admin, "rider_updated", "rider", riderId, {})
        return result
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/riders/{riderId}/activate", response_model=RiderAdminOut)
async def activate_rider(riderId: str, admin: dict = Depends(require_min_role("admin"))):
    """Re-activate a suspended rider. Requires admin role or higher."""
    try:
        result = await rider_service.activate_rider(riderId)
        await admin_service.log_action(admin, "rider_activated", "rider", riderId, {})
        return result
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/riders/{riderId}/suspend", response_model=RiderAdminOut)
async def suspend_rider(riderId: str, admin: dict = Depends(require_min_role("admin"))):
    """
    Suspend a rider. Sets isActive=False, forces OFFLINE, revokes all sessions.
    Requires admin role or higher.
    """
    try:
        result = await rider_service.suspend_rider(riderId)
        await admin_service.log_action(admin, "rider_suspended", "rider", riderId, {})
        return result
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.delete("/riders/{riderId}", status_code=204)
async def delete_rider(riderId: str, admin: dict = Depends(require_min_role("admin"))):
    """Soft-delete a rider. Requires admin role or higher."""
    try:
        await rider_service.delete_rider(riderId)
        await admin_service.log_action(admin, "rider_deleted", "rider", riderId, {})
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/riders/{riderId}/history")
async def get_rider_history(
    riderId: str,
    limit:  int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: dict = Depends(require_min_role("support")),
):
    """Rider delivery history. Requires support role or higher."""
    try:
        await rider_service.get_rider_admin_detail(riderId)
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    jobs, total = await rider_service.get_rider_job_history(riderId, limit, offset)
    return {"jobs": [j.model_dump() for j in jobs], "total": total, "limit": limit, "offset": offset}


@router.get("/riders/{riderId}/stats")
async def get_rider_stats(riderId: str, admin: dict = Depends(require_min_role("support"))):
    """Live rider delivery statistics. Requires support role or higher."""
    try:
        await rider_service.get_rider_admin_detail(riderId)
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return (await rider_service.get_rider_live_stats(riderId)).model_dump()


@router.post("/riders/{riderId}/assign-job/{jobId}")
async def assign_job_to_rider(
    riderId: str, jobId: str,
    admin: dict = Depends(require_min_role("operations_manager")),
):
    """
    Manually assign a rider to a delivery job.
    Job must be in PENDING_ASSIGNMENT or READY_FOR_PICKUP status.
    Requires operations_manager role or higher.
    """
    try:
        job = await delivery_service.assign_rider_to_job(
            job_id=jobId, rider_id=riderId, actor=f"admin:{admin['_id']}"
        )
        await admin_service.log_action(
            admin, "rider_assigned_to_delivery", "delivery_job", jobId,
            {"riderId": riderId},
        )
        return {"message": "Rider assigned successfully.", "job": job.model_dump()}
    except delivery_service.DeliveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
