"""
Vendor router — REST API for vendor-facing operations.
All endpoints require Vendor JWT except /auth/* endpoints.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from . import service
from .dependencies import get_current_vendor_required
from .schemas import (
    MarkUnavailableItemsIn,
    VendorLoginIn,
    VendorLogoutIn,
    VendorOrderAcceptIn,
    VendorOrderOut,
    VendorOrderRejectIn,
    VendorOut,
    VendorPushTokenIn,
    VendorRefreshIn,
    VendorSessionOut,
    VendorStatsOut,
    VendorStatusUpdateIn,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vendor", tags=["vendor"])


# ─── Authentication ───────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=VendorSessionOut)
async def vendor_login(body: VendorLoginIn):
    """Vendor login with email + password. Returns JWT (8h) and refresh token (30d)."""
    try:
        return await service.login_vendor(body.email, body.password)
    except service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/auth/refresh", response_model=VendorSessionOut)
async def vendor_refresh(body: VendorRefreshIn):
    """Rotate vendor refresh token. Old token is immediately invalidated."""
    try:
        return await service.refresh_vendor_session(body.refreshToken)
    except service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/auth/logout", status_code=204)
async def vendor_logout(body: VendorLogoutIn):
    """Revoke vendor refresh token server-side."""
    await service.logout_vendor(body.refreshToken)


# ─── Profile & status ─────────────────────────────────────────────────────────

@router.get("/profile", response_model=VendorOut)
async def get_profile(vendor: dict = Depends(get_current_vendor_required)):
    return await service.get_vendor_profile(vendor)


@router.put("/status", response_model=VendorOut)
async def update_status(
    body: VendorStatusUpdateIn,
    vendor: dict = Depends(get_current_vendor_required),
):
    """Update vendor store status: OPEN | CLOSED | BUSY."""
    try:
        return await service.update_vendor_status(str(vendor["_id"]), body.status)
    except service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/push-token", status_code=204)
async def register_push_token(
    body: VendorPushTokenIn,
    vendor: dict = Depends(get_current_vendor_required),
):
    """Register or update the vendor's device push token (stored for future use)."""
    await service.update_push_token(str(vendor["_id"]), body.token, body.platform)


# ─── Order queue ──────────────────────────────────────────────────────────────

@router.get("/orders", response_model=List[VendorOrderOut])
async def get_order_queue(vendor: dict = Depends(get_current_vendor_required)):
    """
    Returns all active (non-terminal) delivery jobs assigned to this vendor's store.
    This is the vendor's incoming order queue.
    """
    return await service.get_vendor_order_queue(vendor)


@router.get("/orders/history")
async def get_order_history(
    limit:  int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    vendor: dict = Depends(get_current_vendor_required),
):
    """Completed/terminal orders for the vendor history screen."""
    orders, total = await service.get_vendor_order_history(vendor, limit, offset)
    return {"orders": [o.model_dump() for o in orders], "total": total, "limit": limit, "offset": offset}


@router.get("/orders/{jobId}", response_model=VendorOrderOut)
async def get_order_detail(
    jobId: str,
    vendor: dict = Depends(get_current_vendor_required),
):
    """Full detail for a single delivery job (must belong to this vendor's store)."""
    try:
        return await service.get_vendor_order_detail(jobId, vendor)
    except service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


# ─── Order lifecycle actions ──────────────────────────────────────────────────

@router.post("/orders/{jobId}/accept", response_model=VendorOrderOut)
async def accept_order(
    jobId: str,
    body: VendorOrderAcceptIn,
    vendor: dict = Depends(get_current_vendor_required),
):
    """
    Vendor accepts an incoming order.
    Transition: WAITING_VENDOR → VENDOR_ACCEPTED
    """
    try:
        return await service.accept_order(jobId, vendor, body.note)
    except service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/orders/{jobId}/reject", response_model=VendorOrderOut)
async def reject_order(
    jobId: str,
    body: VendorOrderRejectIn,
    vendor: dict = Depends(get_current_vendor_required),
):
    """
    Vendor rejects an incoming order (terminal).
    Transition: WAITING_VENDOR → REJECTED
    Admin will need to handle the resulting refund.
    """
    try:
        return await service.reject_order(jobId, vendor, body.reason)
    except service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/orders/{jobId}/unavailable-items", response_model=VendorOrderOut)
async def mark_unavailable_items(
    jobId: str,
    body: MarkUnavailableItemsIn,
    vendor: dict = Depends(get_current_vendor_required),
):
    """
    Mark items the vendor cannot fulfil (e.g. out of stock).
    Not a state transition — can be updated multiple times during VENDOR_ACCEPTED or PREPARING.
    """
    try:
        items = [i.model_dump() for i in body.items]
        return await service.set_unavailable_items_vendor(jobId, vendor, items, body.vendorNote)
    except service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/orders/{jobId}/preparing", response_model=VendorOrderOut)
async def start_preparing(
    jobId: str,
    vendor: dict = Depends(get_current_vendor_required),
):
    """
    Vendor starts preparing the order.
    Transition: VENDOR_ACCEPTED → PREPARING
    """
    try:
        return await service.start_preparing(jobId, vendor)
    except service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/orders/{jobId}/ready", response_model=VendorOrderOut)
async def mark_ready(
    jobId: str,
    vendor: dict = Depends(get_current_vendor_required),
):
    """
    Vendor marks the order ready for rider pickup.
    Transition: PREPARING → READY_FOR_PICKUP
    This is the gate that unlocks rider assignment.
    """
    try:
        return await service.mark_ready_for_pickup(jobId, vendor)
    except service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


# ─── Stats ────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=VendorStatsOut)
async def get_stats(vendor: dict = Depends(get_current_vendor_required)):
    """Live vendor statistics from the delivery_jobs collection."""
    return await service.get_vendor_live_stats(vendor)
