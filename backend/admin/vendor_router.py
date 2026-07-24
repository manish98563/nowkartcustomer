"""
Admin Vendor router — SECURED vendor management.
All endpoints require admin JWT authentication with appropriate RBAC.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from vendor import service as vendor_service
from vendor.schemas import (
    PaginatedVendorsOut,
    VendorAdminOut,
    VendorCreateIn,
    VendorUpdateIn,
)
from admin.dependencies import require_min_role
from admin import service as admin_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin-vendors"])


@router.post("/vendors", response_model=VendorAdminOut, status_code=201)
async def create_vendor(
    body: VendorCreateIn,
    admin: dict = Depends(require_min_role("admin")),
):
    """Create a new vendor account. Requires admin role or higher."""
    try:
        result = await vendor_service.create_vendor(body)
        await admin_service.log_action(
            admin, "vendor_created", "vendor", result.id,
            {"email": result.email, "businessName": result.businessName},
        )
        return result
    except vendor_service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/vendors", response_model=PaginatedVendorsOut)
async def list_vendors(
    status:         Optional[str]  = Query(default=None),
    isActive:       Optional[bool] = Query(default=None),
    includeDeleted: bool           = Query(default=False),
    limit:  int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: dict = Depends(require_min_role("support")),
):
    """List vendors. Requires support role or higher."""
    return await vendor_service.list_vendors(
        status=status, is_active=isActive,
        include_deleted=includeDeleted, limit=limit, offset=offset,
    )


@router.get("/vendors/{vendorId}", response_model=VendorAdminOut)
async def get_vendor(vendorId: str, admin: dict = Depends(require_min_role("support"))):
    """Full vendor detail. Requires support role or higher."""
    try:
        return await vendor_service.get_vendor_admin_detail(vendorId)
    except vendor_service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/vendors/{vendorId}", response_model=VendorAdminOut)
async def update_vendor(
    vendorId: str, body: VendorUpdateIn,
    admin: dict = Depends(require_min_role("admin")),
):
    """Update vendor fields. Requires admin role or higher."""
    try:
        result = await vendor_service.update_vendor(vendorId, body)
        await admin_service.log_action(admin, "vendor_updated", "vendor", vendorId, {})
        return result
    except vendor_service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/vendors/{vendorId}/activate", response_model=VendorAdminOut)
async def activate_vendor(vendorId: str, admin: dict = Depends(require_min_role("admin"))):
    """Re-activate a suspended vendor. Requires admin role or higher."""
    try:
        result = await vendor_service.activate_vendor(vendorId)
        await admin_service.log_action(admin, "vendor_activated", "vendor", vendorId, {})
        return result
    except vendor_service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/vendors/{vendorId}/suspend", response_model=VendorAdminOut)
async def suspend_vendor(vendorId: str, admin: dict = Depends(require_min_role("admin"))):
    """
    Suspend a vendor. Sets isActive=False, forces CLOSED, revokes all sessions.
    Requires admin role or higher.
    """
    try:
        result = await vendor_service.suspend_vendor(vendorId)
        await admin_service.log_action(admin, "vendor_suspended", "vendor", vendorId, {})
        return result
    except vendor_service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.delete("/vendors/{vendorId}", status_code=204)
async def delete_vendor(vendorId: str, admin: dict = Depends(require_min_role("admin"))):
    """Soft-delete a vendor. Requires admin role or higher."""
    try:
        await vendor_service.delete_vendor(vendorId)
        await admin_service.log_action(admin, "vendor_deleted", "vendor", vendorId, {})
    except vendor_service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/vendors/{vendorId}/assign-store/{storeId}", response_model=VendorAdminOut)
async def assign_store(
    vendorId: str, storeId: str,
    admin: dict = Depends(require_min_role("admin")),
):
    """Link a vendor to a store. Requires admin role or higher."""
    try:
        result = await vendor_service.assign_store(vendorId, storeId)
        await admin_service.log_action(
            admin, "vendor_store_assigned", "vendor", vendorId, {"storeId": storeId}
        )
        return result
    except vendor_service.VendorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
