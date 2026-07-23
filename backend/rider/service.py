"""
Rider service — all business logic for rider lifecycle.

ARCHITECTURE:
  • rider → delivery (one-directional, approved): queries delivery_jobs for
    current job and history; imported lazily inside functions.
  • rider → auth (none): rider module is completely independent of customer auth.
  • All MongoDB operations go through rider/db.py collections only.

SESSION PATTERN:
  Mirrors auth/service.py exactly:
    • Access token:  JWT, 4 hours (RIDER_JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    • Refresh token: opaque 48-byte random, stored as SHA-256 hash
    • Rotation:      single-use — old token revoked on each refresh
    • Reuse detect:  reuse of a revoked token → revoke ALL tokens for this rider

PASSWORD:
  bcrypt via passlib.  A timing-safe dummy verify runs even when a rider
  is not found to prevent user-enumeration.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId

from .db import rider_refresh_tokens_collection, riders_collection
from .schemas import (
    DeliveryJobBriefOut,
    PaginatedRidersOut,
    RiderAdminOut,
    RiderCreateIn,
    RiderOut,
    RiderSessionOut,
    RiderStatsOut,
    RiderStatus,
    RiderUpdateIn,
    RiderVehicleType,
)
from . import security

logger = logging.getLogger(__name__)

_DUMMY_HASH = security.hash_password("__dummy_password_for_timing__")


# ─── Custom exception ─────────────────────────────────────────────────────────

class RiderError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


# ─── Serialisation helpers ────────────────────────────────────────────────────

def _dt(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _oid(value: Any) -> Optional[str]:
    return str(value) if value is not None else None


def _oid_list(values: list) -> list[str]:
    return [str(v) for v in (values or [])]


def _to_stats(embedded: dict) -> RiderStatsOut:
    """Deserialise embedded stats sub-document."""
    return RiderStatsOut(
        totalDeliveries=int(embedded.get("totalDeliveries", 0)),
        completedDeliveries=int(embedded.get("completedDeliveries", 0)),
        failedDeliveries=int(embedded.get("failedDeliveries", 0)),
        cancelledDeliveries=int(embedded.get("cancelledDeliveries", 0)),
        successRate=float(embedded.get("successRate", 0.0)),
    )


def _to_rider_out(rider: dict) -> RiderOut:
    return RiderOut(
        id=str(rider["_id"]),
        email=rider.get("email", ""),
        phone=rider.get("phone", ""),
        firstName=rider.get("firstName", ""),
        lastName=rider.get("lastName", ""),
        status=rider.get("status", RiderStatus.OFFLINE),
        vehicleType=rider.get("vehicleType", RiderVehicleType.BICYCLE),
        vehicleNumber=rider.get("vehicleNumber"),
        storeIds=_oid_list(rider.get("storeIds", [])),
        stats=_to_stats(rider.get("stats") or {}),
        isActive=bool(rider.get("isActive", True)),
        lastSeenAt=_dt(rider.get("lastSeenAt")),
        createdAt=_dt(rider.get("createdAt")) or "",
        updatedAt=_dt(rider.get("updatedAt")) or "",
    )


def _to_rider_admin_out(rider: dict) -> RiderAdminOut:
    return RiderAdminOut(
        id=str(rider["_id"]),
        email=rider.get("email", ""),
        phone=rider.get("phone", ""),
        firstName=rider.get("firstName", ""),
        lastName=rider.get("lastName", ""),
        status=rider.get("status", RiderStatus.OFFLINE),
        vehicleType=rider.get("vehicleType", RiderVehicleType.BICYCLE),
        vehicleNumber=rider.get("vehicleNumber"),
        storeIds=_oid_list(rider.get("storeIds", [])),
        devicePushToken=rider.get("devicePushToken"),
        platformOS=rider.get("platformOS"),
        stats=_to_stats(rider.get("stats") or {}),
        isActive=bool(rider.get("isActive", True)),
        isDeleted=bool(rider.get("isDeleted", False)),
        lastSeenAt=_dt(rider.get("lastSeenAt")),
        createdAt=_dt(rider.get("createdAt")) or "",
        updatedAt=_dt(rider.get("updatedAt")) or "",
    )


# ─── Internal lookups ─────────────────────────────────────────────────────────

async def get_rider_by_id(rider_id: str) -> Optional[dict]:
    """Return raw rider document or None. Used by dependency injection."""
    try:
        oid = ObjectId(rider_id)
    except InvalidId:
        return None
    return await riders_collection.find_one({"_id": oid, "isDeleted": False})


async def _get_rider_by_email(email: str) -> Optional[dict]:
    return await riders_collection.find_one(
        {"email": email.strip().lower(), "isDeleted": False}
    )


async def _get_raw_by_id(rider_id: str) -> Optional[dict]:
    """Like get_rider_by_id but raises RiderError 404 instead of returning None."""
    doc = await get_rider_by_id(rider_id)
    if not doc:
        raise RiderError("Rider not found.", 404)
    return doc


# ─── Session helpers ──────────────────────────────────────────────────────────

async def _issue_session(rider: dict) -> RiderSessionOut:
    rider_id = str(rider["_id"])
    access_token  = security.create_rider_access_token(rider_id)
    refresh_plain = security.generate_refresh_token()
    now = datetime.now(timezone.utc)

    await rider_refresh_tokens_collection.insert_one(
        {
            "riderId":    rider_id,
            "tokenHash":  security.hash_refresh_token(refresh_plain),
            "createdAt":  now,
            "expiresAt":  now.timestamp() + security.RIDER_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            "revoked":    False,
        }
    )
    return RiderSessionOut(
        accessToken=access_token,
        refreshToken=refresh_plain,
        expiresIn=security.RIDER_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        rider=_to_rider_out(rider),
    )


# ─── Authentication ───────────────────────────────────────────────────────────

async def login_rider(email: str, password: str) -> RiderSessionOut:
    """
    Authenticate a rider with email + password.
    Always runs a bcrypt verify (even when rider not found) to prevent
    user-enumeration via timing side-channels.
    """
    rider = await _get_rider_by_email(email)

    if not rider:
        security.verify_password(password, _DUMMY_HASH)  # timing-safe dummy
        raise RiderError("Invalid email or password.", 401)

    if not security.verify_password(password, rider.get("passwordHash", "")):
        raise RiderError("Invalid email or password.", 401)

    if rider.get("isDeleted"):
        raise RiderError("This account has been removed.", 403)
    if not rider.get("isActive", True):
        raise RiderError("This account is suspended. Please contact support.", 403)

    # Update lastSeenAt on login
    now = datetime.now(timezone.utc)
    await riders_collection.update_one(
        {"_id": rider["_id"]},
        {"$set": {"lastSeenAt": now, "updatedAt": now}},
    )
    rider["lastSeenAt"] = now
    return await _issue_session(rider)


async def refresh_rider_session(refresh_token: str) -> RiderSessionOut:
    """
    Rotate a rider refresh token.
    Single-use: the presented token is revoked, a new pair is issued.
    Reuse of a revoked token triggers family-wide revocation (compromise signal).
    """
    token_hash = security.hash_refresh_token(refresh_token)
    record = await rider_refresh_tokens_collection.find_one({"tokenHash": token_hash})

    if not record:
        raise RiderError("Session has expired. Please sign in again.", 401)

    if record["revoked"]:
        # Refresh token reuse detected — revoke all sessions for this rider
        await rider_refresh_tokens_collection.update_many(
            {"riderId": record["riderId"], "revoked": False},
            {"$set": {"revoked": True}},
        )
        raise RiderError("Session has expired. Please sign in again.", 401)

    if record["expiresAt"] < datetime.now(timezone.utc).timestamp():
        raise RiderError("Session has expired. Please sign in again.", 401)

    rider = await get_rider_by_id(record["riderId"])
    if not rider:
        raise RiderError("Rider account not found.", 404)
    if not rider.get("isActive", True) or rider.get("isDeleted"):
        raise RiderError("Account is inactive.", 403)

    # Revoke the old token
    await rider_refresh_tokens_collection.update_one(
        {"_id": record["_id"]}, {"$set": {"revoked": True}}
    )
    return await _issue_session(rider)


async def logout_rider(refresh_token: str) -> None:
    """Revoke a rider refresh token server-side. Best-effort: never raises."""
    token_hash = security.hash_refresh_token(refresh_token)
    await rider_refresh_tokens_collection.update_one(
        {"tokenHash": token_hash}, {"$set": {"revoked": True}}
    )


# ─── Admin: Create / Update / Delete ─────────────────────────────────────────

async def create_rider(data: RiderCreateIn) -> RiderAdminOut:
    """
    Create a new rider account.  Raises 409 if the email already exists.
    Password validation: minimum 8 characters.
    """
    if len(data.password) < 8:
        raise RiderError("Password must be at least 8 characters.", 400)

    # Check email uniqueness
    existing = await riders_collection.find_one({"email": data.email.strip().lower()})
    if existing:
        raise RiderError("A rider with this email already exists.", 409)

    now = datetime.now(timezone.utc)

    # Convert storeIds strings to ObjectIds where valid, skip invalid ones
    store_oids: list = []
    for sid in (data.storeIds or []):
        try:
            store_oids.append(ObjectId(sid))
        except InvalidId:
            pass

    doc = {
        "email":        data.email.strip().lower(),
        "phone":        data.phone.strip(),
        "passwordHash": security.hash_password(data.password),
        "firstName":    data.firstName.strip(),
        "lastName":     data.lastName.strip(),
        "status":       RiderStatus.OFFLINE,
        "vehicleType":  data.vehicleType,
        "vehicleNumber": data.vehicleNumber,
        "storeIds":     store_oids,
        "devicePushToken": None,
        "platformOS":   None,
        "stats": {
            "totalDeliveries":     0,
            "completedDeliveries": 0,
            "failedDeliveries":    0,
            "cancelledDeliveries": 0,
            "successRate":         0.0,
        },
        "isActive":  True,
        "isDeleted": False,
        "lastSeenAt": None,
        "createdAt": now,
        "updatedAt": now,
    }
    result = await riders_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    logger.info("Created rider %s (%s %s)", doc["_id"], data.firstName, data.lastName)
    return _to_rider_admin_out(doc)


async def update_rider(rider_id: str, data: RiderUpdateIn) -> RiderAdminOut:
    """Admin update — patch semantics; only provided fields are changed."""
    await _get_raw_by_id(rider_id)   # raises 404 if not found

    now = datetime.now(timezone.utc)
    fields: dict = {"updatedAt": now}

    if data.phone is not None:
        fields["phone"] = data.phone.strip()
    if data.firstName is not None:
        fields["firstName"] = data.firstName.strip()
    if data.lastName is not None:
        fields["lastName"] = data.lastName.strip()
    if data.vehicleType is not None:
        fields["vehicleType"] = data.vehicleType
    if data.vehicleNumber is not None:
        fields["vehicleNumber"] = data.vehicleNumber
    if data.storeIds is not None:
        store_oids = []
        for sid in data.storeIds:
            try:
                store_oids.append(ObjectId(sid))
            except InvalidId:
                pass
        fields["storeIds"] = store_oids

    try:
        oid = ObjectId(rider_id)
    except InvalidId:
        raise RiderError("Invalid rider ID.", 400)

    updated = await riders_collection.find_one_and_update(
        {"_id": oid, "isDeleted": False},
        {"$set": fields},
        return_document=True,
    )
    if not updated:
        raise RiderError("Rider not found.", 404)
    return _to_rider_admin_out(updated)


async def activate_rider(rider_id: str) -> RiderAdminOut:
    """Admin: re-activate a suspended rider."""
    try:
        oid = ObjectId(rider_id)
    except InvalidId:
        raise RiderError("Invalid rider ID.", 400)

    now = datetime.now(timezone.utc)
    updated = await riders_collection.find_one_and_update(
        {"_id": oid, "isDeleted": False},
        {"$set": {"isActive": True, "updatedAt": now}},
        return_document=True,
    )
    if not updated:
        raise RiderError("Rider not found.", 404)
    logger.info("Rider %s activated", rider_id)
    return _to_rider_admin_out(updated)


async def suspend_rider(rider_id: str) -> RiderAdminOut:
    """
    Admin: suspend a rider — sets isActive=False and forces offline status.
    All active refresh tokens are revoked so the rider is signed out immediately.
    """
    try:
        oid = ObjectId(rider_id)
    except InvalidId:
        raise RiderError("Invalid rider ID.", 400)

    now = datetime.now(timezone.utc)
    updated = await riders_collection.find_one_and_update(
        {"_id": oid, "isDeleted": False},
        {"$set": {"isActive": False, "status": RiderStatus.OFFLINE, "updatedAt": now}},
        return_document=True,
    )
    if not updated:
        raise RiderError("Rider not found.", 404)

    # Revoke all active sessions — suspended rider cannot use existing tokens
    await rider_refresh_tokens_collection.update_many(
        {"riderId": rider_id, "revoked": False},
        {"$set": {"revoked": True}},
    )
    logger.info("Rider %s suspended — all sessions revoked", rider_id)
    return _to_rider_admin_out(updated)


async def delete_rider(rider_id: str) -> None:
    """
    Admin: soft-delete a rider.
    Sets isDeleted=True, forces offline, revokes all sessions.
    The document is retained for audit / delivery history purposes.
    """
    try:
        oid = ObjectId(rider_id)
    except InvalidId:
        raise RiderError("Invalid rider ID.", 400)

    now = datetime.now(timezone.utc)
    result = await riders_collection.update_one(
        {"_id": oid, "isDeleted": False},
        {"$set": {"isDeleted": True, "isActive": False, "status": RiderStatus.OFFLINE, "updatedAt": now}},
    )
    if result.matched_count == 0:
        raise RiderError("Rider not found.", 404)

    await rider_refresh_tokens_collection.update_many(
        {"riderId": rider_id, "revoked": False},
        {"$set": {"revoked": True}},
    )
    logger.info("Rider %s soft-deleted", rider_id)


# ─── Admin: List ──────────────────────────────────────────────────────────────

async def list_riders(
    status: Optional[str] = None,
    is_active: Optional[bool] = None,
    store_id: Optional[str] = None,
    include_deleted: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedRidersOut:
    """Paginated rider list with optional filters. Designed for Admin Dashboard."""
    query: dict = {}
    if not include_deleted:
        query["isDeleted"] = False
    if status:
        query["status"] = status
    if is_active is not None:
        query["isActive"] = is_active
    if store_id:
        try:
            query["storeIds"] = ObjectId(store_id)
        except InvalidId:
            pass

    total = await riders_collection.count_documents(query)
    cursor = riders_collection.find(query).sort("createdAt", -1).skip(offset).limit(limit)
    riders = await cursor.to_list(limit)
    return PaginatedRidersOut(
        riders=[_to_rider_admin_out(r) for r in riders],
        total=total,
        limit=limit,
        offset=offset,
    )


async def get_rider_admin_detail(rider_id: str) -> RiderAdminOut:
    """Admin view of a single rider."""
    rider = await _get_raw_by_id(rider_id)
    return _to_rider_admin_out(rider)


# ─── Rider: Profile & status ──────────────────────────────────────────────────

async def get_rider_profile(rider: dict) -> RiderOut:
    """Return the rider's own profile view."""
    return _to_rider_out(rider)


async def update_rider_status(rider_id: str, new_status: RiderStatus) -> RiderOut:
    """
    Update a rider's availability status.
    BUSY is set automatically by the delivery assignment system;
    riders can only toggle between ONLINE and OFFLINE themselves.
    (Admin can force any status.)
    """
    try:
        oid = ObjectId(rider_id)
    except InvalidId:
        raise RiderError("Invalid rider ID.", 400)

    now = datetime.now(timezone.utc)
    updated = await riders_collection.find_one_and_update(
        {"_id": oid, "isDeleted": False, "isActive": True},
        {"$set": {"status": new_status, "lastSeenAt": now, "updatedAt": now}},
        return_document=True,
    )
    if not updated:
        raise RiderError("Rider not found or account inactive.", 404)
    return _to_rider_out(updated)


async def update_push_token(rider_id: str, token: str, platform: str) -> None:
    """
    Store / update the rider's push notification device token.
    Token is stored but NOT used for sending notifications in this iteration
    (push notification dispatch is implemented in a future iteration).
    """
    try:
        oid = ObjectId(rider_id)
    except InvalidId:
        raise RiderError("Invalid rider ID.", 400)

    now = datetime.now(timezone.utc)
    await riders_collection.update_one(
        {"_id": oid},
        {"$set": {"devicePushToken": token, "platformOS": platform, "updatedAt": now}},
    )
    logger.info("Rider %s push token updated (platform=%s)", rider_id, platform)


# ─── Rider: Current job & history ────────────────────────────────────────────

async def get_rider_current_job(rider_id: str) -> Optional[dict]:
    """
    Return the rider's currently active delivery job, or None.
    'Active' means assigned and not in a terminal state (DELIVERED or CANCELLED).

    Imports delivery_jobs_collection lazily to avoid circular module imports
    at Python startup time. The dependency direction (rider → delivery) is
    approved in the architecture document.
    """
    from delivery.db import delivery_jobs_collection
    from delivery.service import TERMINAL_STATES

    try:
        oid = ObjectId(rider_id)
    except InvalidId:
        return None

    return await delivery_jobs_collection.find_one(
        {
            "assignedRiderId": oid,
            "status": {"$nin": list(TERMINAL_STATES)},
        }
    )


async def get_rider_job_history(
    rider_id: str, limit: int = 20, offset: int = 0
) -> tuple[list[DeliveryJobBriefOut], int]:
    """
    Return the rider's completed/cancelled delivery jobs (terminal states).
    Returns (jobs, total_count) for pagination.
    """
    from delivery.db import delivery_jobs_collection
    from delivery.service import TERMINAL_STATES, STATUS_LABELS

    try:
        oid = ObjectId(rider_id)
    except InvalidId:
        return [], 0

    query = {
        "assignedRiderId": oid,
        "status": {"$in": list(TERMINAL_STATES)},
    }
    total = await delivery_jobs_collection.count_documents(query)
    cursor = (
        delivery_jobs_collection.find(query)
        .sort("updatedAt", -1)
        .skip(offset)
        .limit(limit)
    )
    docs = await cursor.to_list(limit)

    jobs = [
        DeliveryJobBriefOut(
            id=str(d["_id"]),
            shopifyOrderName=d.get("shopifyOrderName", ""),
            status=d.get("status", ""),
            statusLabel=STATUS_LABELS.get(d.get("status", ""), d.get("status", "")),
            orderTotal=float(d.get("orderTotal", 0)),
            currencyCode=d.get("currencyCode", "GBP"),
            deliveryCity=(d.get("deliveryAddress") or {}).get("city"),
            completedAt=(
                d["completedAt"].isoformat() if isinstance(d.get("completedAt"), datetime)
                else d.get("completedAt")
            ),
            createdAt=(
                d["createdAt"].isoformat() if isinstance(d.get("createdAt"), datetime)
                else d.get("createdAt", "")
            ),
        )
        for d in docs
    ]
    return jobs, total


# ─── Rider: Live statistics ───────────────────────────────────────────────────

async def get_rider_live_stats(rider_id: str) -> RiderStatsOut:
    """
    Compute rider delivery statistics live from the delivery_jobs collection.
    More accurate than the embedded stats (which will be updated incrementally
    by the Rider App in a future iteration).
    """
    from delivery.db import delivery_jobs_collection
    from delivery.schemas import DeliveryJobStatus

    try:
        oid = ObjectId(rider_id)
    except InvalidId:
        return RiderStatsOut()

    pipeline = [
        {"$match": {"assignedRiderId": oid}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    results = await delivery_jobs_collection.aggregate(pipeline).to_list(20)
    stats_map = {r["_id"]: r["count"] for r in results}

    total     = sum(stats_map.values())
    completed = stats_map.get(DeliveryJobStatus.DELIVERED, 0)
    failed    = stats_map.get(DeliveryJobStatus.FAILED_DELIVERY, 0)
    cancelled = stats_map.get(DeliveryJobStatus.CANCELLED, 0)

    return RiderStatsOut(
        totalDeliveries=total,
        completedDeliveries=completed,
        failedDeliveries=failed,
        cancelledDeliveries=cancelled,
        successRate=round(completed / total * 100 if total > 0 else 0.0, 1),
    )
