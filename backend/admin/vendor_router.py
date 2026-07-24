"""
Admin router — Vendor management APIs.
All endpoints are currently unauthenticated.
TODO: Add Depends(get_current_admin_required) in Admin Dashboard iteration.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from vendor import service as vendor_service
from vendor.schemas import (
    PaginatedVendorsOut,
    VendorAdminOut,
    VendorCreateIn,
    VendorUpdateIn,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/vendors", response_model=VendorAdminOut, status_code=201)
async def create_vendor(body: VendorCreateIn):
    """Create a new vendor account. Returns 409 for duplicate email."""
    try:
        return await vendor_service.create_vendor(body)
    except vendor_service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/vendors", response_model=PaginatedVendorsOut)
async def list_vendors(
    status: Optional[str] = Query(default=None),
    isActive: Optional[bool] = Query(default=None),
    includeDeleted: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List vendors with optional filters."""
    return await vendor_service.list_vendors(
        status=status, is_active=isActive,
        include_deleted=includeDeleted, limit=limit, offset=offset,
    )


@router.get("/vendors/{vendorId}", response_model=VendorAdminOut)
async def get_vendor(vendorId: str):
    try:
        return await vendor_service.get_vendor_admin_detail(vendorId)
    except vendor_service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/vendors/{vendorId}", response_model=VendorAdminOut)
async def update_vendor(vendorId: str, body: VendorUpdateIn):
    try:
        return await vendor_service.update_vendor(vendorId, body)
    except vendor_service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/vendors/{vendorId}/activate", response_model=VendorAdminOut)
async def activate_vendor(vendorId: str):
    try:
        return await vendor_service.activate_vendor(vendorId)
    except vendor_service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/vendors/{vendorId}/suspend", response_model=VendorAdminOut)
async def suspend_vendor(vendorId: str):
    try:
        return await vendor_service.suspend_vendor(vendorId)
    except vendor_service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.delete("/vendors/{vendorId}", status_code=204)
async def delete_vendor(vendorId: str):
    try:
        await vendor_service.delete_vendor(vendorId)
    except vendor_service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/vendors/{vendorId}/assign-store/{storeId}", response_model=VendorAdminOut)
async def assign_store(vendorId: str, storeId: str):
    """Link a vendor to a store. Future orders for that store will route to this vendor."""
    try:
        return await vendor_service.assign_store(vendorId, storeId)
    except vendor_service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
