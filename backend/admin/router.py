"""
Admin auth router — login, refresh, logout, profile, admin CRUD, audit logs.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from . import service
from .dependencies import get_current_admin_required, require_min_role
from .schemas import (
    AdminCreateIn,
    AdminLoginIn,
    AdminLogoutIn,
    AdminOut,
    AdminRefreshIn,
    AdminSessionOut,
    AdminUpdateIn,
    AuditLogOut,
    ChangePasswordIn,
    PaginatedAdminsOut,
    PaginatedAuditLogsOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin-auth"])


# ─── Auth ─────────────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=AdminSessionOut)
async def admin_login(body: AdminLoginIn):
    """
    Admin login with email + password.
    Returns a JWT access token (1h) and a rotating refresh token (8h).
    """
    try:
        return await service.login_admin(body.email, body.password)
    except service.AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/auth/refresh", response_model=AdminSessionOut)
async def admin_refresh(body: AdminRefreshIn):
    """Rotate admin refresh token. Old token is immediately invalidated."""
    try:
        return await service.refresh_admin_session(body.refreshToken)
    except service.AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/auth/logout", status_code=204)
async def admin_logout(
    body: AdminLogoutIn,
    admin: dict = Depends(get_current_admin_required),
):
    """Revoke admin refresh token server-side."""
    await service.logout_admin(body.refreshToken, admin)


# ─── Profile ──────────────────────────────────────────────────────────────────

@router.get("/profile", response_model=AdminOut)
async def get_profile(admin: dict = Depends(get_current_admin_required)):
    """Return the authenticated admin's own profile."""
    from .schemas import AdminOut
    return service._to_admin_out(admin)


@router.post("/change-password", status_code=204)
async def change_password(
    body: ChangePasswordIn,
    admin: dict = Depends(get_current_admin_required),
):
    """Change the authenticated admin's own password. Revokes all active sessions."""
    try:
        await service.change_password(admin, body.currentPassword, body.newPassword)
    except service.AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


# ─── Admin user management (super_admin only) ─────────────────────────────────

@router.post("/admins", response_model=AdminOut, status_code=201)
async def create_admin(
    body: AdminCreateIn,
    admin: dict = Depends(require_min_role("super_admin")),
):
    """Create a new admin account. Only super_admin can do this."""
    try:
        result = await service.create_admin(body)
        await service.log_action(
            admin, "admin_created", "admin", result.id,
            {"newAdminEmail": result.email, "role": result.role}
        )
        return result
    except service.AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/admins", response_model=PaginatedAdminsOut)
async def list_admins(
    limit:  int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: dict = Depends(require_min_role("super_admin")),
):
    """List all admin accounts. Super admin only."""
    return await service.list_admins(limit=limit, offset=offset)


@router.put("/admins/{adminId}/activate", response_model=AdminOut)
async def activate_admin(
    adminId: str,
    admin: dict = Depends(require_min_role("super_admin")),
):
    """Re-activate a suspended admin. Super admin only."""
    try:
        result = await service.activate_admin(adminId)
        await service.log_action(admin, "admin_activated", "admin", adminId, {})
        return result
    except service.AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/admins/{adminId}/suspend", response_model=AdminOut)
async def suspend_admin(
    adminId: str,
    admin: dict = Depends(require_min_role("super_admin")),
):
    """Suspend an admin account. Super admin only."""
    try:
        result = await service.suspend_admin(adminId)
        await service.log_action(admin, "admin_suspended", "admin", adminId, {})
        return result
    except service.AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.delete("/admins/{adminId}", status_code=204)
async def delete_admin(
    adminId: str,
    admin: dict = Depends(require_min_role("super_admin")),
):
    """Soft-delete an admin account. Super admin only."""
    try:
        await service.delete_admin(adminId)
        await service.log_action(admin, "admin_deleted", "admin", adminId, {})
    except service.AdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


# ─── Audit logs ───────────────────────────────────────────────────────────────

@router.get("/audit-logs", response_model=PaginatedAuditLogsOut)
async def get_audit_logs(
    adminId:      Optional[str] = Query(default=None),
    action:       Optional[str] = Query(default=None),
    resourceType: Optional[str] = Query(default=None),
    limit:        int = Query(default=50, ge=1, le=200),
    offset:       int = Query(default=0, ge=0),
    admin: dict = Depends(require_min_role("admin")),
):
    """
    Paginated audit log viewer.
    Requires admin role or higher (support cannot view all audit logs).
    """
    return await service.get_audit_logs(
        admin_id=adminId, action=action,
        resource_type=resourceType, limit=limit, offset=offset,
    )
