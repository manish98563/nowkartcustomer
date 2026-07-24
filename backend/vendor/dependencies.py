"""
Vendor FastAPI dependency — authentication guard.
Identical pattern to rider/dependencies.py with role="vendor".
"""
from typing import Optional

from fastapi import Depends, Header, HTTPException

from . import security
from .service import get_vendor_by_id


async def get_current_vendor_optional(
    authorization: Optional[str] = Header(default=None),
) -> Optional[dict]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    payload = security.decode_vendor_access_token(token)
    if not payload:
        return None
    return await get_vendor_by_id(payload["sub"])


async def get_current_vendor_required(
    vendor: Optional[dict] = Depends(get_current_vendor_optional),
) -> dict:
    if not vendor:
        raise HTTPException(status_code=401, detail="Vendor authentication required.")
    if vendor.get("isDeleted", False):
        raise HTTPException(status_code=403, detail="This vendor account has been removed.")
    if not vendor.get("isActive", True):
        raise HTTPException(status_code=403, detail="This vendor account is suspended.")
    return vendor
