"""
Vendor service — full business logic for the vendor lifecycle.

VENDOR WORKFLOW:
  1. Admin creates vendor, links to a store (via storeId)
  2. Vendor logs in, sets status OPEN when shift starts
  3. When an order arrives, vendor's order queue is updated
  4. Vendor accepts or rejects the order
  5. Vendor marks unavailable items (if any)
  6. Vendor starts preparing
  7. Vendor marks Ready for Pickup
  8. Admin assigns a rider (unlock triggered by READY_FOR_PICKUP state)

All delivery job state transitions go through delivery.service (keeping
the delivery module as the single source of truth for delivery state).
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId

from .db import vendor_refresh_tokens_collection, vendors_collection
from .schemas import (
    PaginatedVendorsOut,
    VendorAdminOut,
    VendorCreateIn,
    VendorOrderItemOut,
    VendorOrderOut,
    VendorOut,
    VendorSessionOut,
    VendorStatsOut,
    VendorStatus,
    VendorUpdateIn,
)
from . import security

logger = logging.getLogger(__name__)

_DUMMY_HASH = security.hash_password("__dummy_vendor_password__")


# ─── Custom exception ─────────────────────────────────────────────────────────

class VendorError(Exception):
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


def _to_stats(raw: dict) -> VendorStatsOut:
    return VendorStatsOut(
        totalOrders=int(raw.get("totalOrders", 0)),
        acceptedOrders=int(raw.get("acceptedOrders", 0)),
        rejectedOrders=int(raw.get("rejectedOrders", 0)),
        completedOrders=int(raw.get("completedOrders", 0)),
        averagePreparationMinutes=float(raw.get("averagePreparationMinutes", 0.0)),
    )


def _to_vendor_out(v: dict) -> VendorOut:
    return VendorOut(
        id=str(v["_id"]),
        email=v.get("email", ""),
        phone=v.get("phone", ""),
        businessName=v.get("businessName", ""),
        firstName=v.get("firstName", ""),
        lastName=v.get("lastName", ""),
        status=v.get("status", VendorStatus.CLOSED),
        storeId=_oid(v.get("storeId")),
        stats=_to_stats(v.get("stats") or {}),
        isActive=bool(v.get("isActive", True)),
        lastSeenAt=_dt(v.get("lastSeenAt")),
        createdAt=_dt(v.get("createdAt")) or "",
        updatedAt=_dt(v.get("updatedAt")) or "",
    )


def _to_vendor_admin_out(v: dict) -> VendorAdminOut:
    return VendorAdminOut(
        id=str(v["_id"]),
        email=v.get("email", ""),
        phone=v.get("phone", ""),
        businessName=v.get("businessName", ""),
        firstName=v.get("firstName", ""),
        lastName=v.get("lastName", ""),
        status=v.get("status", VendorStatus.CLOSED),
        storeId=_oid(v.get("storeId")),
        devicePushToken=v.get("devicePushToken"),
        platformOS=v.get("platformOS"),
        stats=_to_stats(v.get("stats") or {}),
        isActive=bool(v.get("isActive", True)),
        isDeleted=bool(v.get("isDeleted", False)),
        lastSeenAt=_dt(v.get("lastSeenAt")),
        createdAt=_dt(v.get("createdAt")) or "",
        updatedAt=_dt(v.get("updatedAt")) or "",
    )


def _job_to_vendor_order_out(job: dict, status_labels: dict) -> VendorOrderOut:
    """Convert a raw delivery_job document to the vendor order view."""
    # Build item list with unavailability flag
    unavailable_titles = {
        i.get("itemTitle", "").lower()
        for i in (job.get("unavailableItems") or [])
    }
    items = [
        VendorOrderItemOut(
            title=item.get("title", ""),
            variantTitle=item.get("variantTitle"),
            quantity=int(item.get("quantity", 1)),
            price=float(item.get("price", 0)),
            isUnavailable=item.get("title", "").lower() in unavailable_titles,
        )
        for item in (job.get("orderItems") or [])
    ]
    status = job.get("status", "waiting_vendor")
    return VendorOrderOut(
        id=str(job["_id"]),
        shopifyOrderName=job.get("shopifyOrderName", ""),
        status=status,
        statusLabel=status_labels.get(status, status),
        orderItems=items,
        unavailableItems=job.get("unavailableItems") or [],
        deliveryInstructions=job.get("deliveryInstructions"),
        vendorNote=job.get("vendorNote"),
        orderTotal=float(job.get("orderTotal", 0)),
        currencyCode=job.get("currencyCode", "GBP"),
        vendorAcceptedAt=_dt(job.get("vendorAcceptedAt")),
        preparingAt=_dt(job.get("preparingAt")),
        readyForPickupAt=_dt(job.get("readyForPickupAt")),
        createdAt=_dt(job.get("createdAt")) or "",
        updatedAt=_dt(job.get("updatedAt")) or "",
    )


# ─── Internal lookups ─────────────────────────────────────────────────────────

async def get_vendor_by_id(vendor_id: str) -> Optional[dict]:
    try:
        oid = ObjectId(vendor_id)
    except InvalidId:
        return None
    return await vendors_collection.find_one({"_id": oid, "isDeleted": False})


async def _get_vendor_by_email(email: str) -> Optional[dict]:
    return await vendors_collection.find_one(
        {"email": email.strip().lower(), "isDeleted": False}
    )


async def _get_raw_by_id(vendor_id: str) -> dict:
    doc = await get_vendor_by_id(vendor_id)
    if not doc:
        raise VendorError("Vendor not found.", 404)
    return doc


# ─── Session ──────────────────────────────────────────────────────────────────

async def _issue_session(vendor: dict) -> VendorSessionOut:
    vendor_id = str(vendor["_id"])
    access_token  = security.create_vendor_access_token(vendor_id)
    refresh_plain = security.generate_refresh_token()
    now = datetime.now(timezone.utc)
    await vendor_refresh_tokens_collection.insert_one(
        {
            "vendorId":  vendor_id,
            "tokenHash": security.hash_refresh_token(refresh_plain),
            "createdAt": now,
            "expiresAt": now.timestamp() + security.VENDOR_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            "revoked":   False,
        }
    )
    return VendorSessionOut(
        accessToken=access_token,
        refreshToken=refresh_plain,
        expiresIn=security.VENDOR_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        vendor=_to_vendor_out(vendor),
    )


# ─── Authentication ───────────────────────────────────────────────────────────

async def login_vendor(email: str, password: str) -> VendorSessionOut:
    vendor = await _get_vendor_by_email(email)
    if not vendor:
        security.verify_password(password, _DUMMY_HASH)   # timing-safe dummy
        raise VendorError("Invalid email or password.", 401)
    if not security.verify_password(password, vendor.get("passwordHash", "")):
        raise VendorError("Invalid email or password.", 401)
    if vendor.get("isDeleted"):
        raise VendorError("This account has been removed.", 403)
    if not vendor.get("isActive", True):
        raise VendorError("This account is suspended. Please contact support.", 403)
    now = datetime.now(timezone.utc)
    await vendors_collection.update_one(
        {"_id": vendor["_id"]},
        {"$set": {"lastSeenAt": now, "updatedAt": now}},
    )
    vendor["lastSeenAt"] = now
    return await _issue_session(vendor)


async def refresh_vendor_session(refresh_token: str) -> VendorSessionOut:
    token_hash = security.hash_refresh_token(refresh_token)
    record = await vendor_refresh_tokens_collection.find_one({"tokenHash": token_hash})
    if not record:
        raise VendorError("Session has expired. Please sign in again.", 401)
    if record["revoked"]:
        await vendor_refresh_tokens_collection.update_many(
            {"vendorId": record["vendorId"], "revoked": False},
            {"$set": {"revoked": True}},
        )
        raise VendorError("Session has expired. Please sign in again.", 401)
    if record["expiresAt"] < datetime.now(timezone.utc).timestamp():
        raise VendorError("Session has expired. Please sign in again.", 401)
    vendor = await get_vendor_by_id(record["vendorId"])
    if not vendor or not vendor.get("isActive", True):
        raise VendorError("Account is inactive.", 403)
    await vendor_refresh_tokens_collection.update_one(
        {"_id": record["_id"]}, {"$set": {"revoked": True}}
    )
    return await _issue_session(vendor)


async def logout_vendor(refresh_token: str) -> None:
    token_hash = security.hash_refresh_token(refresh_token)
    await vendor_refresh_tokens_collection.update_one(
        {"tokenHash": token_hash}, {"$set": {"revoked": True}}
    )


# ─── Admin: Create / CRUD ─────────────────────────────────────────────────────

async def create_vendor(data: VendorCreateIn) -> VendorAdminOut:
    if len(data.password) < 8:
        raise VendorError("Password must be at least 8 characters.", 400)
    existing = await vendors_collection.find_one({"email": data.email.strip().lower()})
    if existing:
        raise VendorError("A vendor with this email already exists.", 409)

    now = datetime.now(timezone.utc)
    store_oid: Optional[ObjectId] = None
    if data.storeId:
        try:
            store_oid = ObjectId(data.storeId)
        except InvalidId:
            raise VendorError("Invalid storeId.", 400)

    doc = {
        "email":        data.email.strip().lower(),
        "phone":        data.phone.strip(),
        "passwordHash": security.hash_password(data.password),
        "businessName": data.businessName.strip(),
        "firstName":    data.firstName.strip(),
        "lastName":     data.lastName.strip(),
        "status":       VendorStatus.CLOSED,
        "storeId":      store_oid,
        "devicePushToken": None,
        "platformOS":   None,
        "stats": {
            "totalOrders": 0, "acceptedOrders": 0, "rejectedOrders": 0,
            "completedOrders": 0, "averagePreparationMinutes": 0.0,
        },
        "isActive":  True,
        "isDeleted": False,
        "lastSeenAt": None,
        "createdAt": now,
        "updatedAt": now,
    }
    result = await vendors_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    logger.info("Created vendor %s (%s)", doc["_id"], data.businessName)
    return _to_vendor_admin_out(doc)


async def update_vendor(vendor_id: str, data: VendorUpdateIn) -> VendorAdminOut:
    await _get_raw_by_id(vendor_id)
    now = datetime.now(timezone.utc)
    fields: dict = {"updatedAt": now}
    if data.phone is not None:
        fields["phone"] = data.phone.strip()
    if data.businessName is not None:
        fields["businessName"] = data.businessName.strip()
    if data.firstName is not None:
        fields["firstName"] = data.firstName.strip()
    if data.lastName is not None:
        fields["lastName"] = data.lastName.strip()
    if data.storeId is not None:
        try:
            fields["storeId"] = ObjectId(data.storeId) if data.storeId else None
        except InvalidId:
            raise VendorError("Invalid storeId.", 400)

    try:
        oid = ObjectId(vendor_id)
    except InvalidId:
        raise VendorError("Invalid vendor ID.", 400)

    updated = await vendors_collection.find_one_and_update(
        {"_id": oid, "isDeleted": False}, {"$set": fields}, return_document=True
    )
    if not updated:
        raise VendorError("Vendor not found.", 404)
    return _to_vendor_admin_out(updated)


async def activate_vendor(vendor_id: str) -> VendorAdminOut:
    try:
        oid = ObjectId(vendor_id)
    except InvalidId:
        raise VendorError("Invalid vendor ID.", 400)
    now = datetime.now(timezone.utc)
    updated = await vendors_collection.find_one_and_update(
        {"_id": oid, "isDeleted": False},
        {"$set": {"isActive": True, "updatedAt": now}},
        return_document=True,
    )
    if not updated:
        raise VendorError("Vendor not found.", 404)
    return _to_vendor_admin_out(updated)


async def suspend_vendor(vendor_id: str) -> VendorAdminOut:
    try:
        oid = ObjectId(vendor_id)
    except InvalidId:
        raise VendorError("Invalid vendor ID.", 400)
    now = datetime.now(timezone.utc)
    updated = await vendors_collection.find_one_and_update(
        {"_id": oid, "isDeleted": False},
        {"$set": {"isActive": False, "status": VendorStatus.CLOSED, "updatedAt": now}},
        return_document=True,
    )
    if not updated:
        raise VendorError("Vendor not found.", 404)
    await vendor_refresh_tokens_collection.update_many(
        {"vendorId": vendor_id, "revoked": False}, {"$set": {"revoked": True}}
    )
    return _to_vendor_admin_out(updated)


async def delete_vendor(vendor_id: str) -> None:
    try:
        oid = ObjectId(vendor_id)
    except InvalidId:
        raise VendorError("Invalid vendor ID.", 400)
    now = datetime.now(timezone.utc)
    result = await vendors_collection.update_one(
        {"_id": oid, "isDeleted": False},
        {"$set": {"isDeleted": True, "isActive": False, "status": VendorStatus.CLOSED, "updatedAt": now}},
    )
    if result.matched_count == 0:
        raise VendorError("Vendor not found.", 404)
    await vendor_refresh_tokens_collection.update_many(
        {"vendorId": vendor_id, "revoked": False}, {"$set": {"revoked": True}}
    )


async def list_vendors(
    status: Optional[str] = None,
    is_active: Optional[bool] = None,
    include_deleted: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedVendorsOut:
    query: dict = {}
    if not include_deleted:
        query["isDeleted"] = False
    if status:
        query["status"] = status
    if is_active is not None:
        query["isActive"] = is_active
    total = await vendors_collection.count_documents(query)
    cursor = vendors_collection.find(query).sort("createdAt", -1).skip(offset).limit(limit)
    vendors = await cursor.to_list(limit)
    return PaginatedVendorsOut(
        vendors=[_to_vendor_admin_out(v) for v in vendors],
        total=total, limit=limit, offset=offset,
    )


async def get_vendor_admin_detail(vendor_id: str) -> VendorAdminOut:
    v = await _get_raw_by_id(vendor_id)
    return _to_vendor_admin_out(v)


async def assign_store(vendor_id: str, store_id: str) -> VendorAdminOut:
    try:
        oid = ObjectId(vendor_id)
        store_oid = ObjectId(store_id)
    except InvalidId:
        raise VendorError("Invalid ID.", 400)
    now = datetime.now(timezone.utc)
    updated = await vendors_collection.find_one_and_update(
        {"_id": oid, "isDeleted": False},
        {"$set": {"storeId": store_oid, "updatedAt": now}},
        return_document=True,
    )
    if not updated:
        raise VendorError("Vendor not found.", 404)
    return _to_vendor_admin_out(updated)


# ─── Vendor: Profile & status ─────────────────────────────────────────────────

async def get_vendor_profile(vendor: dict) -> VendorOut:
    return _to_vendor_out(vendor)


async def update_vendor_status(vendor_id: str, new_status: VendorStatus) -> VendorOut:
    try:
        oid = ObjectId(vendor_id)
    except InvalidId:
        raise VendorError("Invalid vendor ID.", 400)
    now = datetime.now(timezone.utc)
    updated = await vendors_collection.find_one_and_update(
        {"_id": oid, "isDeleted": False, "isActive": True},
        {"$set": {"status": new_status, "lastSeenAt": now, "updatedAt": now}},
        return_document=True,
    )
    if not updated:
        raise VendorError("Vendor not found or account inactive.", 404)
    return _to_vendor_out(updated)


async def update_push_token(vendor_id: str, token: str, platform: str) -> None:
    try:
        oid = ObjectId(vendor_id)
    except InvalidId:
        return
    now = datetime.now(timezone.utc)
    await vendors_collection.update_one(
        {"_id": oid},
        {"$set": {"devicePushToken": token, "platformOS": platform, "updatedAt": now}},
    )


# ─── Vendor: Order operations ─────────────────────────────────────────────────

async def _get_vendor_job(job_id: str, vendor_id_str: str) -> dict:
    """Get a delivery job and verify it belongs to this vendor."""
    from delivery.db import delivery_jobs_collection

    try:
        job_oid = ObjectId(job_id)
        vendor_oid = ObjectId(vendor_id_str)
    except InvalidId:
        raise VendorError("Invalid ID.", 400)

    job = await delivery_jobs_collection.find_one({"_id": job_oid})
    if not job:
        raise VendorError("Order not found.", 404)
    if job.get("vendorId") != vendor_oid:
        raise VendorError("This order does not belong to your store.", 403)
    return job


async def get_vendor_order_queue(vendor: dict) -> list[VendorOrderOut]:
    """Active orders for this vendor (not in terminal states)."""
    from delivery.db import delivery_jobs_collection
    from delivery.service import TERMINAL_STATES, STATUS_LABELS
    try:
        vendor_oid = ObjectId(str(vendor["_id"]))
    except InvalidId:
        return []
    jobs = await delivery_jobs_collection.find(
        {"vendorId": vendor_oid, "status": {"$nin": list(TERMINAL_STATES)}}
    ).sort("createdAt", -1).to_list(100)
    return [_job_to_vendor_order_out(j, STATUS_LABELS) for j in jobs]


async def get_vendor_order_detail(job_id: str, vendor: dict) -> VendorOrderOut:
    from delivery.service import STATUS_LABELS
    job = await _get_vendor_job(job_id, str(vendor["_id"]))
    return _job_to_vendor_order_out(job, STATUS_LABELS)


async def accept_order(job_id: str, vendor: dict, note: Optional[str] = None) -> VendorOrderOut:
    """Vendor accepts an order — transitions WAITING_VENDOR → VENDOR_ACCEPTED."""
    from delivery.service import update_job_status, DeliveryJobStatus, STATUS_LABELS
    job = await _get_vendor_job(job_id, str(vendor["_id"]))
    if job.get("status") != DeliveryJobStatus.WAITING_VENDOR:
        raise VendorError(
            f"Can only accept orders in 'waiting_vendor' status (current: {job.get('status')}).", 409
        )
    vendor_name = f"{vendor.get('businessName', vendor.get('firstName', 'Vendor'))}"
    updated_job = await update_job_status(
        job_id, DeliveryJobStatus.VENDOR_ACCEPTED,
        actor=f"vendor:{vendor['_id']}",
        note=f"Order accepted by {vendor_name}" + (f" — {note}" if note else ""),
    )
    from delivery.db import delivery_jobs_collection
    raw = await delivery_jobs_collection.find_one({"_id": ObjectId(job_id)})
    return _job_to_vendor_order_out(raw, STATUS_LABELS)


async def reject_order(job_id: str, vendor: dict, reason: str) -> VendorOrderOut:
    """Vendor rejects an order — transitions WAITING_VENDOR → REJECTED (terminal)."""
    from delivery.service import update_job_status, DeliveryJobStatus, STATUS_LABELS
    from delivery.db import delivery_jobs_collection
    job = await _get_vendor_job(job_id, str(vendor["_id"]))
    if job.get("status") != DeliveryJobStatus.WAITING_VENDOR:
        raise VendorError(
            f"Can only reject orders in 'waiting_vendor' status (current: {job.get('status')}).", 409
        )
    # Store rejection reason before transitioning
    now = datetime.now(timezone.utc)
    await delivery_jobs_collection.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {"rejectionReason": reason, "updatedAt": now}},
    )
    await update_job_status(
        job_id, DeliveryJobStatus.REJECTED,
        actor=f"vendor:{vendor['_id']}",
        note=f"Order rejected: {reason}",
    )
    raw = await delivery_jobs_collection.find_one({"_id": ObjectId(job_id)})
    return _job_to_vendor_order_out(raw, STATUS_LABELS)


async def start_preparing(job_id: str, vendor: dict) -> VendorOrderOut:
    """Vendor starts preparing — VENDOR_ACCEPTED → PREPARING."""
    from delivery.service import update_job_status, DeliveryJobStatus, STATUS_LABELS
    from delivery.db import delivery_jobs_collection
    job = await _get_vendor_job(job_id, str(vendor["_id"]))
    if job.get("status") != DeliveryJobStatus.VENDOR_ACCEPTED:
        raise VendorError(
            f"Can only start preparing from 'vendor_accepted' status (current: {job.get('status')}).", 409
        )
    await update_job_status(
        job_id, DeliveryJobStatus.PREPARING,
        actor=f"vendor:{vendor['_id']}",
        note="Vendor started preparing items",
    )
    raw = await delivery_jobs_collection.find_one({"_id": ObjectId(job_id)})
    return _job_to_vendor_order_out(raw, STATUS_LABELS)


async def mark_ready_for_pickup(job_id: str, vendor: dict) -> VendorOrderOut:
    """Vendor marks order ready — PREPARING → READY_FOR_PICKUP. Unlocks rider assignment."""
    from delivery.service import update_job_status, DeliveryJobStatus, STATUS_LABELS
    from delivery.db import delivery_jobs_collection
    job = await _get_vendor_job(job_id, str(vendor["_id"]))
    if job.get("status") != DeliveryJobStatus.PREPARING:
        raise VendorError(
            f"Can only mark ready from 'preparing' status (current: {job.get('status')}).", 409
        )
    await update_job_status(
        job_id, DeliveryJobStatus.READY_FOR_PICKUP,
        actor=f"vendor:{vendor['_id']}",
        note="Order is ready for rider pickup",
    )
    raw = await delivery_jobs_collection.find_one({"_id": ObjectId(job_id)})
    return _job_to_vendor_order_out(raw, STATUS_LABELS)


async def set_unavailable_items_vendor(
    job_id: str, vendor: dict, items: list, vendor_note: Optional[str] = None
) -> VendorOrderOut:
    """Vendor marks items as unavailable. Can be done in VENDOR_ACCEPTED or PREPARING state."""
    from delivery.service import set_unavailable_items, STATUS_LABELS
    from delivery.db import delivery_jobs_collection
    # Validate state
    job = await _get_vendor_job(job_id, str(vendor["_id"]))
    from delivery.service import DeliveryJobStatus, TERMINAL_STATES
    if job.get("status") in TERMINAL_STATES:
        raise VendorError("Cannot update a completed or cancelled order.", 409)
    if job.get("status") not in {DeliveryJobStatus.VENDOR_ACCEPTED, DeliveryJobStatus.PREPARING}:
        raise VendorError(
            "Unavailable items can only be set in 'vendor_accepted' or 'preparing' status.", 409
        )
    await set_unavailable_items(job_id, str(vendor["_id"]), items, vendor_note)
    raw = await delivery_jobs_collection.find_one({"_id": ObjectId(job_id)})
    return _job_to_vendor_order_out(raw, STATUS_LABELS)


async def get_vendor_order_history(
    vendor: dict, limit: int = 20, offset: int = 0
) -> tuple[list[VendorOrderOut], int]:
    """Completed/terminal orders for history screen."""
    from delivery.db import delivery_jobs_collection
    from delivery.service import TERMINAL_STATES, STATUS_LABELS
    try:
        vendor_oid = ObjectId(str(vendor["_id"]))
    except InvalidId:
        return [], 0
    query = {"vendorId": vendor_oid, "status": {"$in": list(TERMINAL_STATES)}}
    total = await delivery_jobs_collection.count_documents(query)
    cursor = delivery_jobs_collection.find(query).sort("updatedAt", -1).skip(offset).limit(limit)
    jobs = await cursor.to_list(limit)
    return [_job_to_vendor_order_out(j, STATUS_LABELS) for j in jobs], total


async def get_vendor_live_stats(vendor: dict) -> VendorStatsOut:
    """Compute live stats from delivery_jobs."""
    from delivery.db import delivery_jobs_collection
    from delivery.service import DeliveryJobStatus
    try:
        vendor_oid = ObjectId(str(vendor["_id"]))
    except InvalidId:
        return VendorStatsOut()
    pipeline = [
        {"$match": {"vendorId": vendor_oid}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    results = await delivery_jobs_collection.aggregate(pipeline).to_list(20)
    sm = {r["_id"]: r["count"] for r in results}
    total = sum(sm.values())
    return VendorStatsOut(
        totalOrders=total,
        acceptedOrders=sm.get(DeliveryJobStatus.VENDOR_ACCEPTED, 0)
            + sm.get(DeliveryJobStatus.PREPARING, 0)
            + sm.get(DeliveryJobStatus.READY_FOR_PICKUP, 0)
            + sm.get(DeliveryJobStatus.PENDING_ASSIGNMENT, 0)
            + sm.get(DeliveryJobStatus.ASSIGNED, 0)
            + sm.get(DeliveryJobStatus.AT_STORE, 0)
            + sm.get(DeliveryJobStatus.IN_TRANSIT, 0)
            + sm.get(DeliveryJobStatus.ARRIVED, 0)
            + sm.get(DeliveryJobStatus.DELIVERED, 0),
        rejectedOrders=sm.get(DeliveryJobStatus.REJECTED, 0),
        completedOrders=sm.get(DeliveryJobStatus.DELIVERED, 0),
    )
