"""
Admin service — full business logic for the admin platform.

Responsibilities:
  • Admin authentication (login, refresh, logout, seed)
  • Admin user CRUD (super_admin only)
  • Audit logging (fire-and-forget)
  • Dashboard statistics
  • Store management (extends delivery/db.py stores_collection)
  • Extended delivery management queries
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId

from .db import (
    admin_refresh_tokens_collection,
    admin_users_collection,
    audit_logs_collection,
)
from .schemas import (
    ADMIN_ROLES,
    AdminCreateIn,
    AdminOut,
    AdminRole,
    AdminSessionOut,
    AdminUpdateIn,
    AuditLogOut,
    DashboardStatsOut,
    DeliveryStatsOut,
    PaginatedAdminsOut,
    PaginatedAuditLogsOut,
    RiderStatsOut,
    StoreAdminOut,
    StoreCreateIn,
    StoreStatsOut,
    StoreUpdateIn,
    VendorStatsOut,
)
from . import security

logger = logging.getLogger(__name__)

_DUMMY_HASH = security.hash_password("__dummy_admin_password__")


# ─── Custom exception ─────────────────────────────────────────────────────────

class AdminError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


# ─── Serialisation helpers ────────────────────────────────────────────────────

def _dt(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def _to_admin_out(a: dict) -> AdminOut:
    return AdminOut(
        id=str(a["_id"]),
        email=a.get("email", ""),
        firstName=a.get("firstName", ""),
        lastName=a.get("lastName", ""),
        role=a.get("role", AdminRole.SUPPORT),
        isActive=bool(a.get("isActive", True)),
        lastLoginAt=_dt(a.get("lastLoginAt")),
        createdAt=_dt(a.get("createdAt")) or "",
        updatedAt=_dt(a.get("updatedAt")) or "",
    )


def _to_audit_out(log: dict) -> AuditLogOut:
    return AuditLogOut(
        id=str(log["_id"]),
        adminId=log.get("adminId", ""),
        adminEmail=log.get("adminEmail", ""),
        adminRole=log.get("adminRole", ""),
        action=log.get("action", ""),
        resourceType=log.get("resourceType", ""),
        resourceId=log.get("resourceId", ""),
        details=log.get("details") or {},
        timestamp=_dt(log.get("timestamp")) or "",
    )


# ─── Startup seed ─────────────────────────────────────────────────────────────

async def seed_default_admin() -> None:
    """Create admin@nowkart.com (super_admin) if no admin accounts exist."""
    count = await admin_users_collection.count_documents({})
    if count > 0:
        return
    now = datetime.now(timezone.utc)
    await admin_users_collection.insert_one(
        {
            "email":        "admin@nowkart.com",
            "passwordHash": security.hash_password("Admin2026!"),
            "firstName":    "Super",
            "lastName":     "Admin",
            "role":         AdminRole.SUPER_ADMIN,
            "isActive":     True,
            "isDeleted":    False,
            "lastLoginAt":  None,
            "createdAt":    now,
            "updatedAt":    now,
        }
    )
    logger.info("Seeded default super admin: admin@nowkart.com")


# ─── Internal lookup ──────────────────────────────────────────────────────────

async def get_admin_by_id(admin_id: str) -> Optional[dict]:
    try:
        oid = ObjectId(admin_id)
    except InvalidId:
        return None
    return await admin_users_collection.find_one({"_id": oid, "isDeleted": False})


async def _get_admin_by_email(email: str) -> Optional[dict]:
    return await admin_users_collection.find_one(
        {"email": email.strip().lower(), "isDeleted": False}
    )


# ─── Authentication ───────────────────────────────────────────────────────────

async def _issue_session(admin: dict) -> AdminSessionOut:
    admin_id = str(admin["_id"])
    access_token  = security.create_admin_access_token(admin_id, admin["role"])
    refresh_plain = security.generate_refresh_token()
    now = datetime.now(timezone.utc)
    await admin_refresh_tokens_collection.insert_one(
        {
            "adminId":   admin_id,
            "tokenHash": security.hash_refresh_token(refresh_plain),
            "createdAt": now,
            "expiresAt": now.timestamp() + security.ADMIN_REFRESH_TOKEN_EXPIRE_HOURS * 3600,
            "revoked":   False,
        }
    )
    return AdminSessionOut(
        accessToken=access_token,
        refreshToken=refresh_plain,
        expiresIn=security.ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        admin=_to_admin_out(admin),
    )


async def login_admin(email: str, password: str) -> AdminSessionOut:
    admin = await _get_admin_by_email(email)
    if not admin:
        security.verify_password(password, _DUMMY_HASH)   # timing-safe
        raise AdminError("Invalid email or password.", 401)
    if not security.verify_password(password, admin.get("passwordHash", "")):
        raise AdminError("Invalid email or password.", 401)
    if admin.get("isDeleted"):
        raise AdminError("This account has been removed.", 403)
    if not admin.get("isActive", True):
        raise AdminError("This account is suspended.", 403)

    now = datetime.now(timezone.utc)
    await admin_users_collection.update_one(
        {"_id": admin["_id"]}, {"$set": {"lastLoginAt": now, "updatedAt": now}}
    )
    admin["lastLoginAt"] = now
    session = await _issue_session(admin)

    # Audit: log login event
    await log_action(admin, "admin_login", "admin", str(admin["_id"]), {})
    return session


async def refresh_admin_session(refresh_token: str) -> AdminSessionOut:
    token_hash = security.hash_refresh_token(refresh_token)
    record = await admin_refresh_tokens_collection.find_one({"tokenHash": token_hash})
    if not record:
        raise AdminError("Session has expired. Please sign in again.", 401)
    if record["revoked"]:
        # Reuse detection: revoke all sessions for this admin
        await admin_refresh_tokens_collection.update_many(
            {"adminId": record["adminId"], "revoked": False},
            {"$set": {"revoked": True}},
        )
        raise AdminError("Session has expired. Please sign in again.", 401)
    if record["expiresAt"] < datetime.now(timezone.utc).timestamp():
        raise AdminError("Session has expired. Please sign in again.", 401)

    admin = await get_admin_by_id(record["adminId"])
    if not admin or not admin.get("isActive", True):
        raise AdminError("Account is inactive.", 403)

    await admin_refresh_tokens_collection.update_one(
        {"_id": record["_id"]}, {"$set": {"revoked": True}}
    )
    return await _issue_session(admin)


async def logout_admin(refresh_token: str, admin: Optional[dict] = None) -> None:
    token_hash = security.hash_refresh_token(refresh_token)
    await admin_refresh_tokens_collection.update_one(
        {"tokenHash": token_hash}, {"$set": {"revoked": True}}
    )
    if admin:
        await log_action(admin, "admin_logout", "admin", str(admin["_id"]), {})


async def change_password(admin: dict, current_password: str, new_password: str) -> None:
    if not security.verify_password(current_password, admin.get("passwordHash", "")):
        raise AdminError("Current password is incorrect.", 401)
    if len(new_password) < 8:
        raise AdminError("New password must be at least 8 characters.", 400)
    now = datetime.now(timezone.utc)
    await admin_users_collection.update_one(
        {"_id": admin["_id"]},
        {"$set": {"passwordHash": security.hash_password(new_password), "updatedAt": now}},
    )
    # Revoke all refresh tokens — force re-login with new password
    await admin_refresh_tokens_collection.update_many(
        {"adminId": str(admin["_id"]), "revoked": False},
        {"$set": {"revoked": True}},
    )
    await log_action(admin, "admin_password_changed", "admin", str(admin["_id"]), {})


# ─── Admin user CRUD (super_admin only) ───────────────────────────────────────

async def create_admin(data: AdminCreateIn) -> AdminOut:
    if len(data.password) < 8:
        raise AdminError("Password must be at least 8 characters.", 400)
    existing = await admin_users_collection.find_one({"email": data.email.strip().lower()})
    if existing:
        raise AdminError("An admin with this email already exists.", 409)
    now = datetime.now(timezone.utc)
    doc = {
        "email":        data.email.strip().lower(),
        "passwordHash": security.hash_password(data.password),
        "firstName":    data.firstName.strip(),
        "lastName":     data.lastName.strip(),
        "role":         data.role,
        "isActive":     True,
        "isDeleted":    False,
        "lastLoginAt":  None,
        "createdAt":    now,
        "updatedAt":    now,
    }
    result = await admin_users_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _to_admin_out(doc)


async def list_admins(limit: int = 50, offset: int = 0) -> PaginatedAdminsOut:
    query = {"isDeleted": False}
    total = await admin_users_collection.count_documents(query)
    cursor = admin_users_collection.find(query).sort("createdAt", -1).skip(offset).limit(limit)
    admins = await cursor.to_list(limit)
    return PaginatedAdminsOut(
        admins=[_to_admin_out(a) for a in admins],
        total=total, limit=limit, offset=offset,
    )


async def activate_admin(admin_id: str) -> AdminOut:
    try:
        oid = ObjectId(admin_id)
    except InvalidId:
        raise AdminError("Invalid admin ID.", 400)
    now = datetime.now(timezone.utc)
    updated = await admin_users_collection.find_one_and_update(
        {"_id": oid, "isDeleted": False},
        {"$set": {"isActive": True, "updatedAt": now}},
        return_document=True,
    )
    if not updated:
        raise AdminError("Admin not found.", 404)
    return _to_admin_out(updated)


async def suspend_admin(admin_id: str) -> AdminOut:
    try:
        oid = ObjectId(admin_id)
    except InvalidId:
        raise AdminError("Invalid admin ID.", 400)
    now = datetime.now(timezone.utc)
    updated = await admin_users_collection.find_one_and_update(
        {"_id": oid, "isDeleted": False},
        {"$set": {"isActive": False, "updatedAt": now}},
        return_document=True,
    )
    if not updated:
        raise AdminError("Admin not found.", 404)
    # Revoke all sessions
    await admin_refresh_tokens_collection.update_many(
        {"adminId": admin_id, "revoked": False}, {"$set": {"revoked": True}}
    )
    return _to_admin_out(updated)


async def delete_admin(admin_id: str) -> None:
    try:
        oid = ObjectId(admin_id)
    except InvalidId:
        raise AdminError("Invalid admin ID.", 400)
    now = datetime.now(timezone.utc)
    result = await admin_users_collection.update_one(
        {"_id": oid, "isDeleted": False},
        {"$set": {"isDeleted": True, "isActive": False, "updatedAt": now}},
    )
    if result.matched_count == 0:
        raise AdminError("Admin not found.", 404)
    await admin_refresh_tokens_collection.update_many(
        {"adminId": admin_id, "revoked": False}, {"$set": {"revoked": True}}
    )


# ─── Audit logging ─────────────────────────────────────────────────────────────

async def log_action(
    admin: dict,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict,
) -> None:
    """
    Fire-and-forget audit log.  Never raises — a failed log must not break the
    primary admin operation.
    """
    try:
        await audit_logs_collection.insert_one(
            {
                "adminId":      str(admin["_id"]),
                "adminEmail":   admin.get("email", ""),
                "adminRole":    admin.get("role", ""),
                "action":       action,
                "resourceType": resource_type,
                "resourceId":   str(resource_id),
                "details":      details or {},
                "timestamp":    datetime.now(timezone.utc),
            }
        )
    except Exception as exc:
        logger.warning("Audit log write failed: %s", exc)


async def get_audit_logs(
    admin_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedAuditLogsOut:
    query: dict = {}
    if admin_id:
        query["adminId"] = admin_id
    if action:
        query["action"] = action
    if resource_type:
        query["resourceType"] = resource_type
    total = await audit_logs_collection.count_documents(query)
    cursor = (
        audit_logs_collection.find(query)
        .sort("timestamp", -1)
        .skip(offset)
        .limit(limit)
    )
    logs = await cursor.to_list(limit)
    return PaginatedAuditLogsOut(
        logs=[_to_audit_out(l) for l in logs],
        total=total, limit=limit, offset=offset,
    )


# ─── Dashboard statistics ──────────────────────────────────────────────────────

async def get_dashboard_stats() -> DashboardStatsOut:
    """Aggregate platform statistics for the admin dashboard."""
    from delivery.db import delivery_jobs_collection, stores_collection
    from delivery.service import TERMINAL_STATES
    from rider.db import riders_collection
    from vendor.db import vendors_collection

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Delivery
    status_agg = await delivery_jobs_collection.aggregate([
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]).to_list(20)
    status_map = {d["_id"]: d["count"] for d in status_agg}
    today_count = await delivery_jobs_collection.count_documents(
        {"createdAt": {"$gte": today_start}}
    )
    active_count = await delivery_jobs_collection.count_documents(
        {"status": {"$nin": list(TERMINAL_STATES)}}
    )

    # Riders
    rider_agg = await riders_collection.aggregate([
        {"$match": {"isDeleted": False}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]).to_list(10)
    rider_map = {r["_id"]: r["count"] for r in rider_agg}
    total_riders = sum(rider_map.values())
    active_riders = await riders_collection.count_documents({"isDeleted": False, "isActive": True})

    # Vendors
    vendor_agg = await vendors_collection.aggregate([
        {"$match": {"isDeleted": False}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]).to_list(10)
    vendor_map = {v["_id"]: v["count"] for v in vendor_agg}
    total_vendors = sum(vendor_map.values())
    active_vendors = await vendors_collection.count_documents({"isDeleted": False, "isActive": True})

    # Stores
    total_stores = await stores_collection.count_documents({})
    active_stores = await stores_collection.count_documents({"isActive": True})

    # Recent audit activity
    recent_logs = await audit_logs_collection.find(
        {}, sort=[("timestamp", -1)]
    ).limit(10).to_list(10)

    return DashboardStatsOut(
        deliveries=DeliveryStatsOut(
            total=sum(status_map.values()),
            todayCount=today_count,
            activeCount=active_count,
            byStatus=status_map,
        ),
        riders=RiderStatsOut(
            total=total_riders,
            active=active_riders,
            byStatus=rider_map,
        ),
        vendors=VendorStatsOut(
            total=total_vendors,
            active=active_vendors,
            byStatus=vendor_map,
        ),
        stores=StoreStatsOut(total=total_stores, active=active_stores),
        recentActivity=[_to_audit_out(l) for l in recent_logs],
    )


# ─── Store management ──────────────────────────────────────────────────────────

def _to_store_admin_out(store: dict) -> StoreAdminOut:
    return StoreAdminOut(
        id=str(store["_id"]),
        name=store.get("name", ""),
        shopifyDomain=store.get("shopifyDomain", ""),
        isDefault=bool(store.get("isDefault", False)),
        isActive=bool(store.get("isActive", True)),
        address=store.get("address") or {},
        settings=store.get("settings") or {},
        phone=store.get("phone"),
        operatingHours=store.get("operatingHours"),
        deliveryRadiusKm=store.get("deliveryRadiusKm"),
        createdAt=_dt(store.get("createdAt")) or "",
        updatedAt=_dt(store.get("updatedAt")) or "",
    )


async def list_stores_admin() -> list[StoreAdminOut]:
    from delivery.db import stores_collection
    stores = await stores_collection.find({}).sort("createdAt", -1).to_list(200)
    return [_to_store_admin_out(s) for s in stores]


async def get_store_admin(store_id: str) -> StoreAdminOut:
    from delivery.db import stores_collection
    try:
        oid = ObjectId(store_id)
    except InvalidId:
        raise AdminError("Invalid store ID.", 400)
    store = await stores_collection.find_one({"_id": oid})
    if not store:
        raise AdminError("Store not found.", 404)
    return _to_store_admin_out(store)


async def create_store(data: StoreCreateIn) -> StoreAdminOut:
    from delivery.db import stores_collection
    now = datetime.now(timezone.utc)
    default_settings = {
        "defaultEtaMinutes": 30, "prepTimeMinutes": 10,
        "maxConcurrentJobs": 10, "autoAssignment": False,
    }
    if data.settings:
        default_settings.update(data.settings)
    doc = {
        "name":             data.name.strip(),
        "shopifyDomain":    data.shopifyDomain or "",
        "isDefault":        False,
        "isActive":         True,
        "address":          data.address.model_dump() if data.address else {},
        "settings":         default_settings,
        "phone":            data.phone,
        "operatingHours":   data.operatingHours,
        "deliveryRadiusKm": data.deliveryRadiusKm,
        "createdAt":        now,
        "updatedAt":        now,
    }
    result = await stores_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _to_store_admin_out(doc)


async def update_store(store_id: str, data: StoreUpdateIn) -> StoreAdminOut:
    from delivery.db import stores_collection
    try:
        oid = ObjectId(store_id)
    except InvalidId:
        raise AdminError("Invalid store ID.", 400)
    now = datetime.now(timezone.utc)
    fields: dict = {"updatedAt": now}
    if data.name is not None:
        fields["name"] = data.name.strip()
    if data.phone is not None:
        fields["phone"] = data.phone
    if data.address is not None:
        fields["address"] = data.address.model_dump()
    if data.operatingHours is not None:
        fields["operatingHours"] = data.operatingHours
    if data.deliveryRadiusKm is not None:
        fields["deliveryRadiusKm"] = data.deliveryRadiusKm
    if data.settings is not None:
        # Merge settings (patch)
        for k, v in data.settings.items():
            fields[f"settings.{k}"] = v
    updated = await stores_collection.find_one_and_update(
        {"_id": oid}, {"$set": fields}, return_document=True
    )
    if not updated:
        raise AdminError("Store not found.", 404)
    return _to_store_admin_out(updated)


async def activate_store(store_id: str) -> StoreAdminOut:
    from delivery.db import stores_collection
    try:
        oid = ObjectId(store_id)
    except InvalidId:
        raise AdminError("Invalid store ID.", 400)
    updated = await stores_collection.find_one_and_update(
        {"_id": oid},
        {"$set": {"isActive": True, "updatedAt": datetime.now(timezone.utc)}},
        return_document=True,
    )
    if not updated:
        raise AdminError("Store not found.", 404)
    return _to_store_admin_out(updated)


async def suspend_store(store_id: str) -> StoreAdminOut:
    from delivery.db import stores_collection
    try:
        oid = ObjectId(store_id)
    except InvalidId:
        raise AdminError("Invalid store ID.", 400)
    updated = await stores_collection.find_one_and_update(
        {"_id": oid},
        {"$set": {"isActive": False, "updatedAt": datetime.now(timezone.utc)}},
        return_document=True,
    )
    if not updated:
        raise AdminError("Store not found.", 404)
    return _to_store_admin_out(updated)


# ─── Admin delivery queries ────────────────────────────────────────────────────

async def list_delivery_jobs_admin(
    status: Optional[str] = None,
    store_id: Optional[str] = None,
    vendor_id: Optional[str] = None,
    rider_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Extended delivery job list with vendor and rider filters for admin use."""
    from delivery.db import delivery_jobs_collection
    from delivery.service import _to_full

    query: dict = {}
    if status:
        query["status"] = status
    if store_id:
        try:
            query["storeId"] = ObjectId(store_id)
        except InvalidId:
            pass
    if vendor_id:
        try:
            query["vendorId"] = ObjectId(vendor_id)
        except InvalidId:
            pass
    if rider_id:
        try:
            query["assignedRiderId"] = ObjectId(rider_id)
        except InvalidId:
            pass

    total = await delivery_jobs_collection.count_documents(query)
    cursor = delivery_jobs_collection.find(query).sort("createdAt", -1).skip(offset).limit(limit)
    jobs = await cursor.to_list(limit)
    from delivery.schemas import PaginatedJobsOut
    return PaginatedJobsOut(
        jobs=[_to_full(j) for j in jobs],
        total=total, limit=limit, offset=offset,
    )


async def reassign_vendor_to_job(job_id: str, vendor_id: str, actor: str) -> Any:
    """Reassign a delivery job to a different vendor. Resets to WAITING_VENDOR."""
    from delivery.db import delivery_jobs_collection
    from delivery.service import (
        DeliveryError, DeliveryJobStatus, TERMINAL_STATES, _to_full, _get_raw_by_id
    )
    from delivery.schemas import DeliveryJobOut

    job = await _get_raw_by_id(job_id)
    if not job:
        raise AdminError("Delivery job not found.", 404)

    current = job.get("status")
    if current in TERMINAL_STATES:
        raise AdminError(f"Cannot reassign vendor for a {current} job.", 409)
    if current not in {DeliveryJobStatus.WAITING_VENDOR, DeliveryJobStatus.VENDOR_ACCEPTED}:
        raise AdminError(
            f"Can only reassign vendor in waiting_vendor or vendor_accepted status (current: {current}).", 409
        )

    from vendor.db import vendors_collection as _vendors_col
    try:
        vendor_oid = ObjectId(vendor_id)
    except InvalidId:
        raise AdminError("Invalid vendor ID.", 400)
    vendor = await _vendors_col.find_one({"_id": vendor_oid, "isDeleted": False, "isActive": True})
    if not vendor:
        raise AdminError("Vendor not found or not active.", 404)

    now = datetime.now(timezone.utc)
    vendor_name = vendor.get("businessName", "")
    try:
        oid = ObjectId(job_id)
    except InvalidId:
        raise AdminError("Invalid job ID.", 400)

    updated = await delivery_jobs_collection.find_one_and_update(
        {"_id": oid},
        {
            "$set": {
                "vendorId":         vendor_oid,
                "status":           DeliveryJobStatus.WAITING_VENDOR,
                "vendorAcceptedAt": None,
                "preparingAt":      None,
                "readyForPickupAt": None,
                "updatedAt":        now,
            },
            "$push": {
                "recentEvents": {
                    "$each": [{
                        "status": DeliveryJobStatus.WAITING_VENDOR,
                        "timestamp": now.isoformat(),
                        "actor": actor,
                        "note": f"Vendor reassigned to {vendor_name}",
                        "location": None,
                    }],
                    "$slice": -50,
                }
            },
        },
        return_document=True,
    )
    if not updated:
        raise AdminError("Failed to reassign vendor.", 500)
    return _to_full(updated)
