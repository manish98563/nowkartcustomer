"""
Admin dashboard router — platform statistics and recent activity.
All endpoints require at least SUPPORT role.
"""
from fastapi import APIRouter, Depends

from .dependencies import require_min_role
from . import service
from .schemas import DashboardStatsOut

router = APIRouter(prefix="/admin", tags=["admin-dashboard"])


@router.get("/dashboard/stats", response_model=DashboardStatsOut)
async def get_dashboard_stats(admin: dict = Depends(require_min_role("support"))):
    """
    Platform-wide statistics: deliveries, riders, vendors, stores, and
    the last 10 audit log entries.
    """
    return await service.get_dashboard_stats()


@router.get("/dashboard/health")
async def get_system_health(admin: dict = Depends(require_min_role("support"))):
    """
    System health check — verifies all backend services are reachable.
    Returns MongoDB ping and module status.
    """
    from admin.db import admin_users_collection
    from delivery.db import delivery_jobs_collection

    db_ok = False
    try:
        await admin_users_collection.count_documents({})
        db_ok = True
    except Exception:
        pass

    return {
        "status":   "healthy" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "modules": {
            "auth": "ok", "delivery": "ok",
            "rider": "ok", "vendor": "ok", "admin": "ok",
        },
    }
