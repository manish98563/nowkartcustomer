"""
Admin delivery router — full delivery management with RBAC.
These are the admin-authenticated versions of delivery operations.
The existing unauthenticated delivery/router.py endpoints remain for
backward compatibility but are deprecated for admin use.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from delivery.schemas import DeliveryJobOut, DeliveryJobStatus, PaginatedJobsOut
from delivery import service as delivery_service
from .dependencies import require_min_role
from . import service as admin_service
from .schemas import AdminDeliveryStatusUpdateIn, AdminReassignVendorIn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin-delivery"])


@router.get("/delivery/jobs", response_model=PaginatedJobsOut)
async def list_delivery_jobs(
    status:   Optional[str] = Query(default=None),
    storeId:  Optional[str] = Query(default=None),
    vendorId: Optional[str] = Query(default=None),
    riderId:  Optional[str] = Query(default=None),
    limit:    int = Query(default=50, ge=1, le=200),
    offset:   int = Query(default=0, ge=0),
    admin: dict = Depends(require_min_role("support")),
):
    """List delivery jobs with extended admin filters (vendor, rider)."""
    return await admin_service.list_delivery_jobs_admin(
        status=status, store_id=storeId, vendor_id=vendorId,
        rider_id=riderId, limit=limit, offset=offset,
    )


@router.get("/delivery/jobs/{jobId}", response_model=DeliveryJobOut)
async def get_delivery_job(
    jobId: str,
    admin: dict = Depends(require_min_role("support")),
):
    """Full delivery job detail with all operational and vendor fields."""
    job = await delivery_service.get_delivery_job_detail(jobId)
    if not job:
        raise HTTPException(status_code=404, detail="Delivery job not found.")
    return job


@router.put("/delivery/jobs/{jobId}/status", response_model=DeliveryJobOut)
async def override_job_status(
    jobId: str,
    body:  AdminDeliveryStatusUpdateIn,
    admin: dict = Depends(require_min_role("operations_manager")),
):
    """
    Force a delivery job status transition.
    Enforces the state machine — invalid transitions still return 409.
    """
    try:
        actor = f"admin:{admin['_id']}"
        result = await delivery_service.update_job_status(
            job_id=jobId,
            new_status=DeliveryJobStatus(body.status),
            actor=actor,
            note=body.note or f"Status overridden by admin {admin.get('email','')}",
        )
        await admin_service.log_action(
            admin, "delivery_status_overridden", "delivery_job", jobId,
            {"newStatus": body.status, "note": body.note},
        )
        return result
    except delivery_service.DeliveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/delivery/jobs/{jobId}/cancel", response_model=DeliveryJobOut)
async def cancel_delivery_job(
    jobId: str,
    reason: Optional[str] = Query(default=None),
    admin: dict = Depends(require_min_role("operations_manager")),
):
    """Cancel a delivery job. Cannot cancel IN_TRANSIT jobs directly."""
    try:
        result = await delivery_service.update_job_status(
            job_id=jobId,
            new_status=DeliveryJobStatus.CANCELLED,
            actor=f"admin:{admin['_id']}",
            note=reason or f"Cancelled by admin {admin.get('email','')}",
        )
        await admin_service.log_action(
            admin, "delivery_cancelled", "delivery_job", jobId, {"reason": reason}
        )
        return result
    except delivery_service.DeliveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/delivery/jobs/{jobId}/force-complete", response_model=DeliveryJobOut)
async def force_complete_job(
    jobId: str,
    admin: dict = Depends(require_min_role("admin")),
):
    """
    Force-mark a delivery job as DELIVERED.
    For use when physical delivery occurred but the system wasn't updated.
    Requires admin role or higher.
    """
    try:
        job = await delivery_service.get_delivery_job_detail(jobId)
        if not job:
            raise HTTPException(status_code=404, detail="Delivery job not found.")
        result = await delivery_service.update_job_status(
            job_id=jobId,
            new_status=DeliveryJobStatus.DELIVERED,
            actor=f"admin:{admin['_id']}",
            note=f"Force-completed by admin {admin.get('email','')}",
        )
        await admin_service.log_action(
            admin, "delivery_force_completed", "delivery_job", jobId, {}
        )
        return result
    except delivery_service.DeliveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/delivery/jobs/{jobId}/assign-rider/{riderId}", response_model=DeliveryJobOut)
async def assign_rider(
    jobId: str,
    riderId: str,
    admin: dict = Depends(require_min_role("operations_manager")),
):
    """Assign a rider to a delivery job (PENDING_ASSIGNMENT or READY_FOR_PICKUP)."""
    try:
        result = await delivery_service.assign_rider_to_job(
            job_id=jobId, rider_id=riderId, actor=f"admin:{admin['_id']}"
        )
        await admin_service.log_action(
            admin, "rider_assigned_to_delivery", "delivery_job", jobId,
            {"riderId": riderId},
        )
        return result
    except delivery_service.DeliveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/delivery/jobs/{jobId}/reassign-vendor", response_model=DeliveryJobOut)
async def reassign_vendor(
    jobId: str,
    body:  AdminReassignVendorIn,
    admin: dict = Depends(require_min_role("admin")),
):
    """
    Reassign a delivery job to a different vendor.
    Only possible in WAITING_VENDOR or VENDOR_ACCEPTED status.
    """
    try:
        result = await admin_service.reassign_vendor_to_job(
            job_id=jobId,
            vendor_id=body.vendorId,
            actor=f"admin:{admin['_id']}",
        )
        await admin_service.log_action(
            admin, "delivery_vendor_reassigned", "delivery_job", jobId,
            {"vendorId": body.vendorId, "note": body.note},
        )
        return result
    except admin_service.AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
