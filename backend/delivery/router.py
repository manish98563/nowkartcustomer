"""
Delivery router — REST API for delivery job operations.

AUTHENTICATION MODEL (current iteration):
  GET /api/delivery/job           customer JWT required   (existing auth system)
  GET /api/delivery/jobs          no auth                 TODO: admin JWT (Admin Dashboard iteration)
  GET /api/delivery/jobs/{id}     no auth                 TODO: admin JWT
  PUT /api/delivery/jobs/{id}/status  no auth             TODO: admin + rider JWT
  POST /api/delivery/jobs/{id}/cancel no auth             TODO: admin JWT
  GET /api/delivery/stores        no auth                 TODO: admin JWT

The unauthenticated admin endpoints are intentional for this iteration:
they allow the testing agent and future Admin Dashboard prototype to work
without a full auth stack, and will be locked down when the Admin module
is implemented.  Each is marked with a clear TODO comment.

GID QUERY PARAM RULE:
  All Shopify GID parameters use ?param= (not path segments) to avoid
  NGINX Kubernetes double-decoding slashes in %2F path segments.
  Same convention as /api/tracking/order and /api/auth/orders.
"""
import logging
from typing import List, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query

from auth.dependencies import get_current_user_required

from . import service
from .schemas import (
    DeliveryJobCustomerOut,
    DeliveryJobOut,
    DeliveryJobStatus,
    DeliveryJobStatusUpdateIn,
    PaginatedJobsOut,
    StoreOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/delivery", tags=["delivery"])


# ─── Customer-facing ──────────────────────────────────────────────────────────

@router.get("/job", response_model=DeliveryJobCustomerOut)
async def get_my_delivery_job(
    orderId: str = Query(..., description="Shopify order GID (URL-encoded)"),
    user: dict = Depends(get_current_user_required),
):
    """
    Returns the delivery job status for the authenticated customer's order.

    Returns a limited view — no internal operational fields, no rider
    contact details (those will be added in the Rider App iteration).

    The ?orderId= query param (not a path segment) safely carries Shopify
    GIDs that contain slashes — same pattern as /api/tracking/order.

    Returns 404 if no delivery job has been created yet for this order
    (e.g. the Shopify payment webhook hasn't been received yet).
    """
    decoded_id = unquote(orderId)
    job = await service.get_delivery_job_for_customer(decoded_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=(
                "No delivery job found for this order. "
                "It may still be processing — please try again shortly."
            ),
        )
    return job


# ─── Admin / internal ─────────────────────────────────────────────────────────

@router.get("/jobs", response_model=PaginatedJobsOut)
async def list_jobs(
    status: Optional[str] = Query(
        default=None, description=f"Filter by status. Values: {[s.value for s in DeliveryJobStatus]}"
    ),
    storeId: Optional[str] = Query(default=None, description="Filter by store ObjectId"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    Paginated list of all delivery jobs.
    Sorted newest-first.
    TODO: Restrict to admin JWT when Admin Dashboard module is implemented.
    """
    return await service.list_delivery_jobs(
        status=status, store_id=storeId, limit=limit, offset=offset
    )


@router.get("/jobs/{jobId}", response_model=DeliveryJobOut)
async def get_job(jobId: str):
    """
    Full delivery job detail with all operational fields.
    TODO: Restrict to admin JWT when Admin Dashboard module is implemented.
    """
    job = await service.get_delivery_job_detail(jobId)
    if not job:
        raise HTTPException(status_code=404, detail="Delivery job not found.")
    return job


@router.put("/jobs/{jobId}/status", response_model=DeliveryJobOut)
async def update_job_status(jobId: str, body: DeliveryJobStatusUpdateIn):
    """
    Transition a delivery job to a new status via the state machine.
    Returns 409 for invalid transitions.

    This endpoint will be called by:
      - Admin Dashboard (actor: "admin")
      - Rider App (actor: "rider:{riderId}")
    Both will require appropriate JWT auth in their respective iterations.

    TODO: Restrict to admin JWT + rider JWT when those modules are implemented.
    """
    try:
        return await service.update_job_status(
            job_id=jobId,
            new_status=body.status,
            actor=body.actor or "admin",
            note=body.note,
        )
    except service.DeliveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/jobs/{jobId}/cancel", response_model=DeliveryJobOut)
async def cancel_job(
    jobId: str,
    reason: Optional[str] = Query(default=None, description="Cancellation reason"),
):
    """
    Cancel a delivery job.
    Enforces state machine — cannot cancel IN_TRANSIT, DELIVERED, or already CANCELLED jobs.
    TODO: Restrict to admin JWT when Admin Dashboard module is implemented.
    """
    try:
        return await service.update_job_status(
            job_id=jobId,
            new_status=DeliveryJobStatus.CANCELLED,
            actor="admin",
            note=reason or "Manually cancelled via API",
        )
    except service.DeliveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


# ─── Stores ───────────────────────────────────────────────────────────────────

@router.get("/stores", response_model=List[StoreOut])
async def get_stores():
    """
    List all configured stores.
    TODO: Restrict to admin JWT when Admin Dashboard module is implemented.
    """
    return await service.get_all_stores()
