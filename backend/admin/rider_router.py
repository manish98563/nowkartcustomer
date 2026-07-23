"""
Admin router — Rider management APIs for the future Admin Dashboard.

All endpoints operate on the riders collection via rider.service.

AUTHENTICATION:
  No auth enforcement in this iteration — these endpoints are intentionally
  unauthenticated to allow Admin Dashboard prototyping and Postman/Swagger testing
  before the Admin JWT system is built.

  TODO (Admin Dashboard iteration):
    - Create backend/admin/security.py with admin JWT (role="admin"/"super_admin")
    - Create backend/admin/dependencies.py with get_current_admin_required
    - Add Depends(get_current_admin_required) to every endpoint below
    - Apply store-scoped RBAC so "admin" role only sees their storeIds

  SECURITY NOTE: These endpoints MUST be protected before production deployment.

ASSIGNMENT:
  POST /api/admin/riders/{riderId}/assign-job/{jobId}
  Allows an admin to manually assign a rider to a pending delivery job.
  This is the primary assignment mechanism in MVP (before auto-assignment).
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from rider import service as rider_service
from rider.schemas import (
    PaginatedRidersOut,
    RiderAdminOut,
    RiderCreateIn,
    RiderUpdateIn,
)
from delivery import service as delivery_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


# ─── Rider CRUD ───────────────────────────────────────────────────────────────

@router.post("/riders", response_model=RiderAdminOut, status_code=201)
async def create_rider(body: RiderCreateIn):
    """
    Create a new rider account.
    Admin use only.  Returns the full rider detail including internal fields.
    Returns 409 if the email already exists.
    """
    try:
        return await rider_service.create_rider(body)
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/riders", response_model=PaginatedRidersOut)
async def list_riders(
    status: Optional[str] = Query(default=None, description="Filter by status: online|offline|busy"),
    isActive: Optional[bool] = Query(default=None, description="Filter by active/suspended"),
    storeId: Optional[str] = Query(default=None, description="Filter by store ObjectId"),
    includeDeleted: bool = Query(default=False, description="Include soft-deleted riders"),
    limit:  int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    Paginated list of all riders with optional filters.
    TODO: Restrict to admin JWT when Admin Dashboard is implemented.
    """
    return await rider_service.list_riders(
        status=status,
        is_active=isActive,
        store_id=storeId,
        include_deleted=includeDeleted,
        limit=limit,
        offset=offset,
    )


@router.get("/riders/{riderId}", response_model=RiderAdminOut)
async def get_rider(riderId: str):
    """
    Full rider detail including internal fields (push token, platform OS, etc.).
    TODO: Restrict to admin JWT when Admin Dashboard is implemented.
    """
    try:
        return await rider_service.get_rider_admin_detail(riderId)
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/riders/{riderId}", response_model=RiderAdminOut)
async def update_rider(riderId: str, body: RiderUpdateIn):
    """
    Update rider fields — patch semantics (only provided fields are changed).
    TODO: Restrict to admin JWT when Admin Dashboard is implemented.
    """
    try:
        return await rider_service.update_rider(riderId, body)
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/riders/{riderId}/activate", response_model=RiderAdminOut)
async def activate_rider(riderId: str):
    """
    Re-activate a suspended rider account.
    TODO: Restrict to admin JWT when Admin Dashboard is implemented.
    """
    try:
        return await rider_service.activate_rider(riderId)
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/riders/{riderId}/suspend", response_model=RiderAdminOut)
async def suspend_rider(riderId: str):
    """
    Suspend a rider account.
    Sets isActive=False, forces OFFLINE status, and revokes all active sessions
    so the rider is immediately signed out.
    TODO: Restrict to admin JWT when Admin Dashboard is implemented.
    """
    try:
        return await rider_service.suspend_rider(riderId)
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.delete("/riders/{riderId}", status_code=204)
async def delete_rider(riderId: str):
    """
    Soft-delete a rider account.
    The document is retained for audit / delivery history.
    Revokes all active sessions.
    TODO: Restrict to admin JWT when Admin Dashboard is implemented.
    """
    try:
        await rider_service.delete_rider(riderId)
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


# ─── Rider history ────────────────────────────────────────────────────────────

@router.get("/riders/{riderId}/history")
async def get_rider_history(
    riderId: str,
    limit:  int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    Admin view of a rider's delivery history (terminal jobs only).
    TODO: Restrict to admin JWT when Admin Dashboard is implemented.
    """
    # Validate rider exists
    try:
        await rider_service.get_rider_admin_detail(riderId)
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    jobs, total = await rider_service.get_rider_job_history(riderId, limit, offset)
    return {"jobs": [j.model_dump() for j in jobs], "total": total, "limit": limit, "offset": offset}


@router.get("/riders/{riderId}/stats")
async def get_rider_stats(riderId: str):
    """
    Live delivery statistics for a specific rider.
    TODO: Restrict to admin JWT when Admin Dashboard is implemented.
    """
    try:
        await rider_service.get_rider_admin_detail(riderId)  # validate rider exists
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    stats = await rider_service.get_rider_live_stats(riderId)
    return stats.model_dump()


# ─── Rider assignment ─────────────────────────────────────────────────────────

@router.post("/riders/{riderId}/assign-job/{jobId}")
async def assign_job_to_rider(riderId: str, jobId: str):
    """
    Manually assign a rider to a delivery job.
    The job must be in PENDING_ASSIGNMENT status.
    Transitions the job to ASSIGNED and sets the rider to BUSY.

    This is the primary assignment mechanism for MVP (before auto-assignment
    based on GPS proximity is implemented in a future iteration).

    TODO: Restrict to admin JWT when Admin Dashboard is implemented.
    """
    try:
        job = await delivery_service.assign_rider_to_job(
            job_id=jobId,
            rider_id=riderId,
            actor="admin",
        )
        return {"message": "Rider assigned successfully.", "job": job.model_dump()}
    except delivery_service.DeliveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except rider_service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
