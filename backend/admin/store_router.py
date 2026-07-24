"""
Admin store router — store creation and management.
All endpoints require at least ADMIN role.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException

from .dependencies import require_min_role
from . import service
from .schemas import StoreAdminOut, StoreCreateIn, StoreUpdateIn

router = APIRouter(prefix="/admin", tags=["admin-stores"])


@router.get("/stores", response_model=List[StoreAdminOut])
async def list_stores(admin: dict = Depends(require_min_role("support"))):
    """List all stores with full admin detail."""
    return await service.list_stores_admin()


@router.post("/stores", response_model=StoreAdminOut, status_code=201)
async def create_store(body: StoreCreateIn, admin: dict = Depends(require_min_role("admin"))):
    """Create a new store."""
    try:
        result = await service.create_store(body)
        await service.log_action(admin, "store_created", "store", result.id, {"name": result.name})
        return result
    except service.AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/stores/{storeId}", response_model=StoreAdminOut)
async def get_store(storeId: str, admin: dict = Depends(require_min_role("support"))):
    try:
        return await service.get_store_admin(storeId)
    except service.AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/stores/{storeId}", response_model=StoreAdminOut)
async def update_store(storeId: str, body: StoreUpdateIn, admin: dict = Depends(require_min_role("admin"))):
    try:
        result = await service.update_store(storeId, body)
        await service.log_action(admin, "store_updated", "store", storeId, {})
        return result
    except service.AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/stores/{storeId}/activate", response_model=StoreAdminOut)
async def activate_store(storeId: str, admin: dict = Depends(require_min_role("admin"))):
    try:
        result = await service.activate_store(storeId)
        await service.log_action(admin, "store_activated", "store", storeId, {})
        return result
    except service.AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/stores/{storeId}/suspend", response_model=StoreAdminOut)
async def suspend_store(storeId: str, admin: dict = Depends(require_min_role("admin"))):
    try:
        result = await service.suspend_store(storeId)
        await service.log_action(admin, "store_suspended", "store", storeId, {})
        return result
    except service.AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
