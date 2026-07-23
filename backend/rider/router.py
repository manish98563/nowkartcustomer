"""
Rider router — REST API for rider-facing operations.

All endpoints require Rider JWT authentication (get_current_rider_required)
except the three /auth/* endpoints.

Authentication model:
  POST /api/rider/auth/login    — public (issues session)
  POST /api/rider/auth/refresh  — public with refresh token in body
  POST /api/rider/auth/logout   — public with refresh token in body
  Everything else               — Rider JWT required (Bearer header)
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from . import service
from .dependencies import get_current_rider_required
from .schemas import (
    DeliveryJobBriefOut,
    PushTokenIn,
    RiderLoginIn,
    RiderLogoutIn,
    RiderOut,
    RiderRefreshIn,
    RiderSessionOut,
    RiderStatsOut,
    RiderStatusUpdateIn,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rider", tags=["rider"])


# ─── Authentication ───────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=RiderSessionOut)
async def rider_login(body: RiderLoginIn):
    """
    Rider login with email + password.
    Returns a JWT access token (4 h) and a rotating opaque refresh token (30 d).
    """
    try:
        return await service.login_rider(body.email, body.password)
    except service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/auth/refresh", response_model=RiderSessionOut)
async def rider_refresh(body: RiderRefreshIn):
    """
    Rotate a rider refresh token.
    The old token is immediately invalidated.  Replaying a revoked token triggers
    family-wide session revocation (compromise detection).
    """
    try:
        return await service.refresh_rider_session(body.refreshToken)
    except service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/auth/logout", status_code=204)
async def rider_logout(body: RiderLogoutIn):
    """
    Revoke a rider refresh token server-side.
    Best-effort — local state should be cleared by the client regardless.
    """
    await service.logout_rider(body.refreshToken)


# ─── Profile & status ─────────────────────────────────────────────────────────

@router.get("/profile", response_model=RiderOut)
async def get_profile(rider: dict = Depends(get_current_rider_required)):
    """Return the authenticated rider's own profile."""
    return await service.get_rider_profile(rider)


@router.put("/status", response_model=RiderOut)
async def update_status(
    body: RiderStatusUpdateIn,
    rider: dict = Depends(get_current_rider_required),
):
    """
    Update rider availability status (ONLINE / OFFLINE / BUSY).
    Riders toggle between ONLINE and OFFLINE at shift start/end.
    BUSY is also set automatically by the delivery assignment system.
    """
    try:
        return await service.update_rider_status(str(rider["_id"]), body.status)
    except service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/push-token", status_code=204)
async def register_push_token(
    body: PushTokenIn,
    rider: dict = Depends(get_current_rider_required),
):
    """
    Register or update the rider's device push notification token.
    The token is stored for future use — notification dispatch is added in
    the Push Notifications iteration.
    """
    try:
        await service.update_push_token(str(rider["_id"]), body.token, body.platform)
    except service.RiderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


# ─── Delivery job ─────────────────────────────────────────────────────────────

@router.get("/job/current")
async def get_current_job(rider: dict = Depends(get_current_rider_required)):
    """
    Returns the rider's currently active delivery job (not in a terminal state),
    or {"job": null} if none is assigned.

    The Rider App calls this on startup to restore in-progress deliveries.
    Returns the full DeliveryJobOut shape for maximum context.
    """
    raw = await service.get_rider_current_job(str(rider["_id"]))
    if not raw:
        return {"job": None}

    # Import the canonical formatter from delivery.service.
    # delivery → rider is in the approved dependency direction; this import
    # is in the reverse direction (rider → delivery) which is also approved
    # by the architecture document.
    from delivery.service import _to_full
    return {"job": _to_full(raw).model_dump()}


@router.get("/job/history")
async def get_job_history(
    limit:  int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    rider: dict = Depends(get_current_rider_required),
):
    """
    Returns the rider's completed delivery history (terminal states only).
    Sorted newest-first. Returns a brief summary per job.
    """
    jobs, total = await service.get_rider_job_history(str(rider["_id"]), limit, offset)
    return {"jobs": [j.model_dump() for j in jobs], "total": total, "limit": limit, "offset": offset}


@router.get("/stats", response_model=RiderStatsOut)
async def get_stats(rider: dict = Depends(get_current_rider_required)):
    """
    Returns live delivery statistics aggregated from the delivery_jobs collection.
    More accurate than the embedded stats on the rider document.
    """
    return await service.get_rider_live_stats(str(rider["_id"]))
