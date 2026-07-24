"""
Admin FastAPI dependencies — authentication and RBAC guards.

get_current_admin_required  — any authenticated admin (support+)
require_min_role(role)       — returns a dependency that enforces minimum role level

Usage:
  @router.get("/...", dependencies=[Depends(get_current_admin_required)])
  @router.post("/...", dependencies=[Depends(require_min_role("admin"))])

  Or as a parameter to get the admin object:
  async def endpoint(admin: dict = Depends(require_min_role("operations_manager"))):
"""
from typing import Optional

from fastapi import Depends, Header, HTTPException

from . import security
from .service import get_admin_by_id


async def get_current_admin_optional(
    authorization: Optional[str] = Header(default=None),
) -> Optional[dict]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    payload = security.decode_admin_access_token(token)
    if not payload:
        return None
    return await get_admin_by_id(payload["sub"])


async def get_current_admin_required(
    admin: Optional[dict] = Depends(get_current_admin_optional),
) -> dict:
    if not admin:
        raise HTTPException(status_code=401, detail="Admin authentication required.")
    if admin.get("isDeleted", False):
        raise HTTPException(status_code=403, detail="This admin account has been removed.")
    if not admin.get("isActive", True):
        raise HTTPException(status_code=403, detail="This admin account is suspended.")
    return admin


def require_min_role(min_role: str):
    """
    Returns a FastAPI dependency that ensures the authenticated admin
    has at least `min_role` in the RBAC hierarchy.

    Example:
        @router.delete("/...", dependencies=[Depends(require_min_role("super_admin"))])
    """
    async def _check(admin: dict = Depends(get_current_admin_required)) -> dict:
        if not security.has_min_role(admin.get("role", ""), min_role):
            raise HTTPException(
                status_code=403,
                detail=f"This action requires '{min_role}' role or higher.",
            )
        return admin
    return _check
