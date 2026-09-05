"""
Delivery service — business logic for the delivery job lifecycle.

STATE MACHINE (updated Iteration 10 — Vendor workflow added)
─────────────────────────────────────────────────────────────
WAITING_VENDOR    →  VENDOR_ACCEPTED, REJECTED (terminal), CANCELLED
VENDOR_ACCEPTED   →  PREPARING, CANCELLED
PREPARING         →  READY_FOR_PICKUP, CANCELLED
READY_FOR_PICKUP  →  PENDING_ASSIGNMENT, ASSIGNED (direct), CANCELLED
PENDING_ASSIGNMENT→  ASSIGNED, CANCELLED
ASSIGNED          →  AT_STORE, PENDING_ASSIGNMENT (unassign), CANCELLED
AT_STORE          →  IN_TRANSIT, CANCELLED
IN_TRANSIT        →  ARRIVED, FAILED_DELIVERY  (cannot cancel mid-delivery)
ARRIVED           →  DELIVERED, FAILED_DELIVERY
DELIVERED         →  (terminal)
FAILED_DELIVERY   →  PENDING_ASSIGNMENT (retry), CANCELLED
CANCELLED         →  (terminal)
REJECTED          →  (terminal)

VENDOR WORKFLOW
───────────────
• Orders are created with WAITING_VENDOR status (not PENDING_ASSIGNMENT).
• Rider assignment is only permitted from PENDING_ASSIGNMENT or READY_FOR_PICKUP.
• Vendors can mark unavailable items at any active state via set_unavailable_items().

CANCELLATION RULES
──────────────────
• Jobs in IN_TRANSIT cannot be auto-cancelled — an alert event is added and
  admin must intervene.
• All other pre-terminal states accept cancellation.

MULTI-VENDOR ORCHESTRATION (Iteration 20)
──────────────────────────────────────────
• orchestrate_multi_vendor_order() is the single entry-point for orders/paid.
• Line items are grouped by their Shopify vendor field (exact case-insensitive
  match against vendors.businessName in NowKart).
• If no vendor info is present → LEGACY mode (backward-compatible single job).
• Unmapped vendors are NOT silently assigned; they are recorded in parent_order.
• All processing is idempotent via parent_orders.shopifyOrderId unique index.
"""
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId

from .db import delivery_jobs_collection, parent_orders_collection, stores_collection
from .schemas import (
    DeliveryAddressOut,
    DeliveryEventOut,
    DeliveryJobCustomerOut,
    DeliveryJobOut,
    DeliveryJobStatus,
    OrderItemSnapshotOut,
    PaginatedJobsOut,
    StoreAddressOut,
    StoreOut,
    StoreSettingsOut,
)

logger = logging.getLogger(__name__)


# ─── Business-logic constants ─────────────────────────────────────────────────

STATUS_LABELS: dict[str, str] = {
    # Vendor workflow
    DeliveryJobStatus.WAITING_VENDOR:   "Waiting for Vendor",
    DeliveryJobStatus.VENDOR_ACCEPTED:  "Vendor Accepted",
    DeliveryJobStatus.PREPARING:        "Preparing Order",
    DeliveryJobStatus.READY_FOR_PICKUP: "Ready for Pickup",
    DeliveryJobStatus.REJECTED:         "Order Rejected",
    # Rider workflow
    DeliveryJobStatus.PENDING_ASSIGNMENT: "Awaiting Rider",
    DeliveryJobStatus.ASSIGNED:           "Rider Assigned",
    DeliveryJobStatus.AT_STORE:           "Rider at Store",
    DeliveryJobStatus.IN_TRANSIT:         "Out for Delivery",
    DeliveryJobStatus.ARRIVED:            "Rider Arrived",
    DeliveryJobStatus.DELIVERED:          "Delivered",
    DeliveryJobStatus.FAILED_DELIVERY:    "Delivery Failed",
    DeliveryJobStatus.CANCELLED:          "Cancelled",
}

# key = current status, value = list of valid next statuses
VALID_TRANSITIONS: dict[str, list[str]] = {
    # ── Vendor workflow ──────────────────────────────────────────────────────
    DeliveryJobStatus.WAITING_VENDOR: [
        DeliveryJobStatus.VENDOR_ACCEPTED,
        DeliveryJobStatus.REJECTED,
        DeliveryJobStatus.CANCELLED,
    ],
    DeliveryJobStatus.VENDOR_ACCEPTED: [
        DeliveryJobStatus.PREPARING,
        DeliveryJobStatus.CANCELLED,
    ],
    DeliveryJobStatus.PREPARING: [
        DeliveryJobStatus.READY_FOR_PICKUP,
        DeliveryJobStatus.CANCELLED,
    ],
    DeliveryJobStatus.READY_FOR_PICKUP: [
        DeliveryJobStatus.PENDING_ASSIGNMENT,   # vendor marked ready → awaiting rider queue
        DeliveryJobStatus.ASSIGNED,             # admin directly assigns (shortcut)
        DeliveryJobStatus.CANCELLED,
    ],
    DeliveryJobStatus.REJECTED:         [],     # terminal
    # ── Rider workflow ───────────────────────────────────────────────────────
    DeliveryJobStatus.PENDING_ASSIGNMENT: [
        DeliveryJobStatus.ASSIGNED,
        DeliveryJobStatus.CANCELLED,
    ],
    DeliveryJobStatus.ASSIGNED: [
        DeliveryJobStatus.AT_STORE,
        DeliveryJobStatus.PENDING_ASSIGNMENT,   # unassign / reassign
        DeliveryJobStatus.CANCELLED,
    ],
    DeliveryJobStatus.AT_STORE: [
        DeliveryJobStatus.IN_TRANSIT,
        DeliveryJobStatus.CANCELLED,
    ],
    DeliveryJobStatus.IN_TRANSIT: [
        DeliveryJobStatus.ARRIVED,
        DeliveryJobStatus.FAILED_DELIVERY,
        # No CANCELLED — in-transit jobs require admin override
    ],
    DeliveryJobStatus.ARRIVED: [
        DeliveryJobStatus.DELIVERED,
        DeliveryJobStatus.FAILED_DELIVERY,
    ],
    DeliveryJobStatus.DELIVERED:       [],   # terminal
    DeliveryJobStatus.FAILED_DELIVERY: [
        DeliveryJobStatus.PENDING_ASSIGNMENT,   # retry
        DeliveryJobStatus.CANCELLED,
    ],
    DeliveryJobStatus.CANCELLED:       [],   # terminal
}

TERMINAL_STATES: frozenset[str] = frozenset({
    DeliveryJobStatus.DELIVERED,
    DeliveryJobStatus.CANCELLED,
    DeliveryJobStatus.REJECTED,   # added Iteration 10
})

# State transitions that set a timing field on the delivery job document
_TRANSITION_TIMESTAMPS: dict[str, str] = {
    # Vendor workflow
    DeliveryJobStatus.VENDOR_ACCEPTED:  "vendorAcceptedAt",
    DeliveryJobStatus.PREPARING:        "preparingAt",
    DeliveryJobStatus.READY_FOR_PICKUP: "readyForPickupAt",
    # Rider workflow
    DeliveryJobStatus.ASSIGNED:    "assignedAt",
    DeliveryJobStatus.IN_TRANSIT:  "pickedUpAt",
    DeliveryJobStatus.ARRIVED:     "arrivedAt",
    DeliveryJobStatus.DELIVERED:   "completedAt",
}


# ─── Custom exception ─────────────────────────────────────────────────────────

class DeliveryError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


# ─── Serialisation helpers ────────────────────────────────────────────────────

def _dt(value: Any) -> Optional[str]:
    """Convert a datetime or None to ISO 8601 string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _oid(value: Any) -> Optional[str]:
    """Convert an ObjectId or None to str or None."""
    return str(value) if value is not None else None


def _addr(raw: dict) -> DeliveryAddressOut:
    return DeliveryAddressOut(
        firstName=raw.get("firstName"),
        lastName=raw.get("lastName"),
        line1=raw.get("line1", ""),
        line2=raw.get("line2"),
        city=raw.get("city", ""),
        province=raw.get("province"),
        postcode=raw.get("postcode", ""),
        country=raw.get("country", ""),
        phone=raw.get("phone"),
        coordinates=raw.get("coordinates"),
    )


def _items(raw: list) -> list[OrderItemSnapshotOut]:
    return [
        OrderItemSnapshotOut(
            title=i.get("title", ""),
            variantTitle=i.get("variantTitle"),
            quantity=int(i.get("quantity", 1)),
            price=float(i.get("price", 0)),
            imageUrl=i.get("imageUrl"),
        )
        for i in raw
    ]


def _events(raw: list) -> list[DeliveryEventOut]:
    return [
        DeliveryEventOut(
            status=e.get("status", ""),
            timestamp=e.get("timestamp", ""),
            actor=e.get("actor", "system"),
            note=e.get("note"),
        )
        for e in raw
    ]


def _to_full(job: dict) -> DeliveryJobOut:
    status = job.get("status", DeliveryJobStatus.WAITING_VENDOR)
    return DeliveryJobOut(
        id=str(job["_id"]),
        shopifyOrderId=job["shopifyOrderId"],
        shopifyOrderName=job.get("shopifyOrderName", ""),
        shopifyNumericId=int(job.get("shopifyNumericId", 0)),
        storeId=_oid(job.get("storeId")) or "",
        status=status,
        statusLabel=STATUS_LABELS.get(status, status),
        customerId=_oid(job.get("customerId")),
        shopifyCustomerId=job.get("shopifyCustomerId"),
        customerEmail=job.get("customerEmail"),
        customerFirstName=job.get("customerFirstName"),
        customerLastName=job.get("customerLastName"),
        assignedRiderId=_oid(job.get("assignedRiderId")),
        deliveryAddress=_addr(job.get("deliveryAddress") or {}),
        pickupAddress=_addr(job.get("pickupAddress") or {}),
        orderItems=_items(job.get("orderItems") or []),
        orderTotal=float(job.get("orderTotal", 0)),
        currencyCode=job.get("currencyCode", "GBP"),
        deliveryInstructions=job.get("deliveryInstructions"),
        estimatedDeliveryAt=_dt(job.get("estimatedDeliveryAt")),
        etaMinutes=job.get("etaMinutes"),
        assignedAt=_dt(job.get("assignedAt")),
        pickedUpAt=_dt(job.get("pickedUpAt")),
        arrivedAt=_dt(job.get("arrivedAt")),
        completedAt=_dt(job.get("completedAt")),
        failureCount=int(job.get("failureCount", 0)),
        lastFailureReason=job.get("lastFailureReason"),
        recentEvents=_events(job.get("recentEvents") or []),
        # Vendor fields (Iteration 10)
        vendorId=_oid(job.get("vendorId")),
        vendorAcceptedAt=_dt(job.get("vendorAcceptedAt")),
        preparingAt=_dt(job.get("preparingAt")),
        readyForPickupAt=_dt(job.get("readyForPickupAt")),
        unavailableItems=job.get("unavailableItems") or [],
        vendorNote=job.get("vendorNote"),
        rejectionReason=job.get("rejectionReason"),
        createdAt=_dt(job.get("createdAt")) or "",
        updatedAt=_dt(job.get("updatedAt")) or "",
    )


def _to_customer(job: dict) -> DeliveryJobCustomerOut:
    status = job.get("status", DeliveryJobStatus.WAITING_VENDOR)
    return DeliveryJobCustomerOut(
        id=str(job["_id"]),
        shopifyOrderId=job["shopifyOrderId"],
        shopifyOrderName=job.get("shopifyOrderName", ""),
        status=status,
        statusLabel=STATUS_LABELS.get(status, status),
        deliveryAddress=_addr(job.get("deliveryAddress") or {}),
        orderItems=_items(job.get("orderItems") or []),
        orderTotal=float(job.get("orderTotal", 0)),
        currencyCode=job.get("currencyCode", "GBP"),
        estimatedDeliveryAt=_dt(job.get("estimatedDeliveryAt")),
        etaMinutes=job.get("etaMinutes"),
        createdAt=_dt(job.get("createdAt")) or "",
        updatedAt=_dt(job.get("updatedAt")) or "",
    )


def _store_out(store: dict) -> StoreOut:
    addr = store.get("address") or {}
    settings = store.get("settings") or {}
    return StoreOut(
        id=str(store["_id"]),
        name=store.get("name", ""),
        shopifyDomain=store.get("shopifyDomain", ""),
        isDefault=bool(store.get("isDefault", False)),
        isActive=bool(store.get("isActive", True)),
        address=StoreAddressOut(
            line1=addr.get("line1", ""),
            city=addr.get("city", ""),
            postcode=addr.get("postcode", ""),
            country=addr.get("country", ""),
            coordinates=addr.get("coordinates"),
        ),
        settings=StoreSettingsOut(
            defaultEtaMinutes=int(settings.get("defaultEtaMinutes", 30)),
            prepTimeMinutes=int(settings.get("prepTimeMinutes", 10)),
            maxConcurrentJobs=int(settings.get("maxConcurrentJobs", 10)),
            autoAssignment=bool(settings.get("autoAssignment", False)),
        ),
        createdAt=_dt(store.get("createdAt")) or "",
    )


# ─── Store management ─────────────────────────────────────────────────────────

async def get_default_store() -> dict:
    """
    Return the active default store document, creating one automatically
    if none exists.  Called on startup to ensure a store is always available.
    """
    store = await stores_collection.find_one({"isDefault": True, "isActive": True})
    if store:
        return store
    return await _seed_default_store()


async def _seed_default_store() -> dict:
    now = datetime.now(timezone.utc)
    doc = {
        "name": os.environ.get("DELIVERY_DEFAULT_STORE_NAME", "Now Kart"),
        "shopifyDomain": os.environ.get("SHOPIFY_STORE_DOMAIN", ""),
        "isDefault": True,
        "isActive": True,
        "address": {
            "line1": "Store address — configure via Admin Dashboard",
            "city": "London",
            "postcode": "N/A",
            "country": "GB",
            "coordinates": None,   # set when Google Maps ETA module is added
        },
        "settings": {
            "defaultEtaMinutes": int(os.environ.get("DELIVERY_DEFAULT_ETA_MINUTES", "30")),
            "prepTimeMinutes": 10,
            "maxConcurrentJobs": 10,
            "autoAssignment": False,
        },
        "createdAt": now,
        "updatedAt": now,
    }
    result = await stores_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    logger.info("Seeded default delivery store: id=%s", doc["_id"])
    return doc


async def get_all_stores() -> list[StoreOut]:
    stores = await stores_collection.find({}).to_list(100)
    return [_store_out(s) for s in stores]


# ─── Job creation ─────────────────────────────────────────────────────────────

async def create_delivery_job_from_order(order_data: dict) -> DeliveryJobOut:
    """
    Create a DeliveryJob from a Shopify orders/paid webhook payload (REST format).
    Idempotent — returns the existing job unchanged if one already exists
    for this Shopify order ID.

    Called by: webhooks/service.py
    """
    now = datetime.now(timezone.utc)
    shopify_order_id = f"gid://shopify/Order/{order_data['id']}"

    # Idempotency guard — must also be enforced at the webhook level via
    # the unique index on webhook_events.shopifyWebhookId, but we double-
    # check here so that manual test calls also behave correctly.
    existing = await delivery_jobs_collection.find_one({"shopifyOrderId": shopify_order_id})
    if existing:
        logger.info(
            "Delivery job already exists for order %s — returning existing (id=%s)",
            shopify_order_id, existing["_id"],
        )
        return _to_full(existing)

    # Resolve customer linkage (authenticated shoppers only)
    # Import lazily to keep module boundary explicit — delivery doesn't own auth.
    shopify_customer_id: Optional[str] = None
    customer_id: Optional[ObjectId] = None
    if order_data.get("customer") and order_data["customer"].get("id"):
        shopify_customer_id = f"gid://shopify/Customer/{order_data['customer']['id']}"
        from auth.db import users_collection
        user = await users_collection.find_one({"shopifyCustomerId": shopify_customer_id})
        if user:
            customer_id = user["_id"]

    # Resolve store
    store = await get_default_store()

    # Build denormalised delivery address from Shopify shipping_address
    shipping = order_data.get("shipping_address") or {}
    delivery_address = {
        "firstName":  shipping.get("first_name", ""),
        "lastName":   shipping.get("last_name", ""),
        "line1":      shipping.get("address1", ""),
        "line2":      shipping.get("address2") or "",
        "city":       shipping.get("city", ""),
        "province":   shipping.get("province") or "",
        "postcode":   shipping.get("zip", ""),
        "country":    shipping.get("country", ""),
        "phone":      shipping.get("phone") or "",
        "coordinates": None,   # populated by Google Maps ETA module (future)
    }

    # Build order items snapshot
    order_items = []
    for item in order_data.get("line_items") or []:
        order_items.append({
            "title":        item.get("title", ""),
            "variantTitle": item.get("variant_title"),
            "quantity":     int(item.get("quantity", 1)),
            "price":        float(item.get("price", "0")),
            "imageUrl":     None,   # REST webhook payload doesn't include image URLs
        })

    # Resolve vendor for this store (lazy import — vendor module)
    vendor_id: Optional[ObjectId] = None
    try:
        from vendor.db import vendors_collection as _vendors_col
        vendor_doc = await _vendors_col.find_one(
            {"storeId": store["_id"], "isDeleted": False, "isActive": True}
        )
        if vendor_doc:
            vendor_id = vendor_doc["_id"]
    except ImportError:
        pass   # vendor module not yet available

    order_name = order_data.get("name") or f"#{order_data['id']}"

    job_doc = {
        # Shopify linkage
        "shopifyOrderId":   shopify_order_id,
        "shopifyOrderName": order_name,
        "shopifyNumericId": int(order_data["id"]),

        # Store & customer
        "storeId":           store["_id"],
        "customerId":        customer_id,
        "shopifyCustomerId": shopify_customer_id,
        "customerEmail":     (
            order_data.get("email")
            or (order_data.get("customer") or {}).get("email")
        ),
        "customerFirstName": (order_data.get("customer") or {}).get("first_name"),
        "customerLastName":  (order_data.get("customer") or {}).get("last_name"),

        # Status — WAITING_VENDOR is the new initial state (Iteration 10)
        # Rider assignment is only permitted after READY_FOR_PICKUP
        "status":         DeliveryJobStatus.WAITING_VENDOR,
        "assignedRiderId": None,

        # Vendor (Iteration 10)
        "vendorId":          vendor_id,
        "vendorAcceptedAt":  None,
        "preparingAt":       None,
        "readyForPickupAt":  None,
        "unavailableItems":  [],
        "vendorNote":        None,
        "rejectionReason":   None,

        # Addresses (denormalised snapshot — independent of Shopify after creation)
        "deliveryAddress": delivery_address,
        "pickupAddress":   store["address"],   # store address snapshot

        # Order snapshot
        "orderItems":      order_items,
        "orderTotal":      float(order_data.get("total_price", "0")),
        "currencyCode":    order_data.get("currency", "GBP"),
        "deliveryInstructions": order_data.get("note"),

        # ETA (populated by ETA module — future)
        "estimatedDeliveryAt": None,
        "etaMinutes":          None,

        # Timing fields (set on state transitions)
        "assignedAt":  None,
        "pickedUpAt":  None,
        "arrivedAt":   None,
        "completedAt": None,

        # Failure tracking
        "failureCount":      0,
        "lastFailureReason": None,
        "retriedByJobId":    None,
        "originalJobId":     None,

        # Proof of delivery (populated by Rider App — future)
        "proofOfDelivery": None,

        # Audit trail
        "recentEvents": [
            {
                "status":    DeliveryJobStatus.WAITING_VENDOR,
                "timestamp": now.isoformat(),
                "actor":     "webhook:orders/paid",
                "note":      f"Order {order_name} paid via Shopify — delivery job created, awaiting vendor acceptance",
                "location":  None,
            }
        ],

        "createdAt": now,
        "updatedAt": now,
    }

    result = await delivery_jobs_collection.insert_one(job_doc)
    job_doc["_id"] = result.inserted_id
    logger.info(
        "Created delivery job %s for Shopify order %s (%s)",
        job_doc["_id"], shopify_order_id, order_name,
    )
    return _to_full(job_doc)


# ─── Job queries ──────────────────────────────────────────────────────────────

async def _get_raw_by_id(job_id: str) -> Optional[dict]:
    try:
        oid = ObjectId(job_id)
    except InvalidId:
        return None
    return await delivery_jobs_collection.find_one({"_id": oid})


async def get_delivery_job_for_customer(shopify_order_id: str) -> Optional[DeliveryJobCustomerOut]:
    """
    Customer-facing: limited view of the delivery job for a given Shopify order GID.
    Returns None if no job exists (not an error — order may still be processing).
    """
    job = await delivery_jobs_collection.find_one({"shopifyOrderId": shopify_order_id})
    if not job:
        return None
    return _to_customer(job)


async def get_delivery_job_detail(job_id: str) -> Optional[DeliveryJobOut]:
    """Full detail — for admin dashboard / internal use."""
    job = await _get_raw_by_id(job_id)
    if not job:
        return None
    return _to_full(job)


async def list_delivery_jobs(
    status: Optional[str] = None,
    store_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedJobsOut:
    """
    Paginated list of delivery jobs with optional status and store filters.
    Sorted by createdAt descending (newest first).
    Designed for the Admin Dashboard.
    """
    query: dict = {}
    if status:
        query["status"] = status
    if store_id:
        try:
            query["storeId"] = ObjectId(store_id)
        except InvalidId:
            pass   # ignore invalid storeId — return unfiltered

    total = await delivery_jobs_collection.count_documents(query)
    cursor = (
        delivery_jobs_collection
        .find(query)
        .sort("createdAt", -1)
        .skip(offset)
        .limit(limit)
    )
    jobs = await cursor.to_list(limit)
    return PaginatedJobsOut(
        jobs=[_to_full(j) for j in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )


# ─── State machine ────────────────────────────────────────────────────────────

async def update_job_status(
    job_id: str,
    new_status: DeliveryJobStatus,
    actor: str,
    note: Optional[str] = None,
) -> DeliveryJobOut:
    """
    Transition a delivery job to a new status via the state machine.
    Raises DeliveryError (409) for invalid transitions.
    Raises DeliveryError (404) if the job doesn't exist.
    """
    job = await _get_raw_by_id(job_id)
    if not job:
        raise DeliveryError("Delivery job not found.", 404)

    current = job.get("status")

    # Terminal state guard
    if current in TERMINAL_STATES:
        raise DeliveryError(
            f"Cannot modify a job in terminal state '{current}'.", 409
        )

    # Valid transition guard
    allowed = VALID_TRANSITIONS.get(current, [])
    if new_status not in allowed:
        allowed_str = ", ".join(allowed) if allowed else "none"
        raise DeliveryError(
            f"Transition '{current}' → '{new_status}' is not permitted. "
            f"Allowed next states: {allowed_str}.",
            409,
        )

    now = datetime.now(timezone.utc)

    new_event = {
        "status":    new_status,
        "timestamp": now.isoformat(),
        "actor":     actor,
        "note":      note or STATUS_LABELS.get(new_status, new_status),
        "location":  None,
    }

    update: dict[str, Any] = {
        "$set": {
            "status":    new_status,
            "updatedAt": now,
        },
        "$push": {
            "recentEvents": {
                "$each":  [new_event],
                "$slice": -50,   # retain only the last 50 events inline
            }
        },
    }

    # Set timing field for this transition
    if new_status in _TRANSITION_TIMESTAMPS:
        update["$set"][_TRANSITION_TIMESTAMPS[new_status]] = now

    # Unassign rider when reverting ASSIGNED → PENDING_ASSIGNMENT
    if new_status == DeliveryJobStatus.PENDING_ASSIGNMENT and current == DeliveryJobStatus.ASSIGNED:
        update["$set"]["assignedRiderId"] = None
        update["$set"]["assignedAt"] = None

    # Track failures
    if new_status == DeliveryJobStatus.FAILED_DELIVERY:
        update["$inc"] = {"failureCount": 1}
        if note:
            update["$set"]["lastFailureReason"] = note

    try:
        oid = ObjectId(job_id)
    except InvalidId:
        raise DeliveryError("Invalid job ID format.", 400)

    updated = await delivery_jobs_collection.find_one_and_update(
        {"_id": oid},
        update,
        return_document=True,
    )
    if not updated:
        raise DeliveryError("Delivery job not found after update.", 404)

    logger.info(
        "Job %s: %s → %s  actor=%s",
        job_id, current, new_status, actor,
    )
    return _to_full(updated)


async def cancel_delivery_job_by_order_id(
    shopify_order_id: str,
    reason: str = "Cancelled via Shopify",
) -> Optional[DeliveryJobOut]:
    """
    Cancel a delivery job located by its Shopify order GID.
    Called by the webhook processor on orders/cancelled.

    Returns None if no job exists for this order (not an error — order may
    have been cancelled before payment was confirmed, meaning no job was
    ever created).

    If the job is already in a terminal state, returns it unchanged.

    If the job is IN_TRANSIT, adds a warning event but does NOT cancel —
    admin must intervene.
    """
    job = await delivery_jobs_collection.find_one({"shopifyOrderId": shopify_order_id})
    if not job:
        logger.info(
            "No delivery job found for order %s — nothing to cancel.",
            shopify_order_id,
        )
        return None

    current = job.get("status")
    job_id = str(job["_id"])

    if current in TERMINAL_STATES:
        logger.info(
            "Job %s for order %s already in terminal state '%s' — skipping cancel.",
            job_id, shopify_order_id, current,
        )
        return _to_full(job)

    if current == DeliveryJobStatus.IN_TRANSIT:
        # Per architecture: do NOT auto-cancel a live delivery.
        # Add an alert event and let the admin resolve it.
        now = datetime.now(timezone.utc)
        alert_event = {
            "status":    current,
            "timestamp": now.isoformat(),
            "actor":     "webhook:orders/cancelled",
            "note":      (
                "ALERT: Shopify order cancelled while rider is IN TRANSIT. "
                "Admin intervention required — do not auto-cancel."
            ),
            "location":  None,
        }
        await delivery_jobs_collection.update_one(
            {"_id": job["_id"]},
            {
                "$push": {"recentEvents": {"$each": [alert_event], "$slice": -50}},
                "$set":  {"updatedAt": now},
            },
        )
        logger.warning(
            "ALERT: Order %s cancelled by Shopify but delivery job %s is IN_TRANSIT. "
            "Admin intervention required.",
            shopify_order_id, job_id,
        )
        refreshed = await delivery_jobs_collection.find_one({"_id": job["_id"]})
        return _to_full(refreshed)

    return await update_job_status(
        job_id,
        DeliveryJobStatus.CANCELLED,
        "webhook:orders/cancelled",
        reason,
    )



# ─── Rider assignment (extended in Iteration 9) ───────────────────────────────

async def assign_rider_to_job(
    job_id: str,
    rider_id: str,
    actor: str = "admin",
) -> "DeliveryJobOut":
    """
    Assign a rider to a delivery job and transition it to ASSIGNED.

    Validates:
      • Job must exist and be in PENDING_ASSIGNMENT status
      • Rider must exist, be active, and not be soft-deleted

    Side effects:
      • delivery_jobs.assignedRiderId = rider ObjectId
      • delivery_jobs.status = ASSIGNED
      • delivery_jobs.assignedAt = now
      • riders.status = BUSY  (non-atomic; acceptable for MVP)

    Imports rider.db lazily to maintain clean module boundaries.
    The delivery → rider dependency direction is explicitly approved in the
    architecture document.
    """
    job = await _get_raw_by_id(job_id)
    if not job:
        raise DeliveryError("Delivery job not found.", 404)

    if job.get("status") not in {DeliveryJobStatus.PENDING_ASSIGNMENT, DeliveryJobStatus.READY_FOR_PICKUP}:
        raise DeliveryError(
            f"Cannot assign a rider to a job in status '{job.get('status')}'. "
            "Job must be in PENDING_ASSIGNMENT or READY_FOR_PICKUP status.",
            409,
        )

    # Validate rider (lazy import — rider module may not be imported yet)
    from rider.db import riders_collection as _riders_col
    try:
        rider_oid = ObjectId(rider_id)
    except InvalidId:
        raise DeliveryError("Invalid rider ID.", 400)

    rider = await _riders_col.find_one({"_id": rider_oid, "isDeleted": False, "isActive": True})
    if not rider:
        raise DeliveryError("Rider not found or not active.", 404)

    now = datetime.now(timezone.utc)
    rider_name = f"{rider.get('firstName', '')} {rider.get('lastName', '')}".strip()

    try:
        oid = ObjectId(job_id)
    except InvalidId:
        raise DeliveryError("Invalid job ID.", 400)

    new_event = {
        "status":    DeliveryJobStatus.ASSIGNED,
        "timestamp": now.isoformat(),
        "actor":     actor,
        "note":      f"Assigned to rider {rider_name}" if rider_name else "Rider assigned",
        "location":  None,
    }

    updated = await delivery_jobs_collection.find_one_and_update(
        {"_id": oid},
        {
            "$set": {
                "status":          DeliveryJobStatus.ASSIGNED,
                "assignedRiderId": rider_oid,
                "assignedAt":      now,
                "updatedAt":       now,
            },
            "$push": {
                "recentEvents": {"$each": [new_event], "$slice": -50}
            },
        },
        return_document=True,
    )
    if not updated:
        raise DeliveryError("Failed to update delivery job.", 500)

    # Set rider status to BUSY (non-atomic, best-effort)
    await _riders_col.update_one(
        {"_id": rider_oid},
        {"$set": {"status": "busy", "updatedAt": now}},
    )

    logger.info(
        "Job %s assigned to rider %s (%s) by %s",
        job_id, rider_id, rider_name, actor,
    )
    return _to_full(updated)


# ─── Vendor-facing delivery functions (added Iteration 10) ───────────────────

async def set_unavailable_items(
    job_id: str,
    vendor_id: str,
    items: list,
    vendor_note: Optional[str] = None,
) -> "DeliveryJobOut":
    """
    Set / replace the unavailable items list on a delivery job.
    Called by vendor when they cannot fulfil some items.

    `items` is a list of dicts: [{itemTitle: str, reason: str | None}]
    Validates that the job belongs to the requesting vendor.
    Does NOT trigger a state transition — items can be updated at any active state.
    """
    job = await _get_raw_by_id(job_id)
    if not job:
        raise DeliveryError("Delivery job not found.", 404)

    # Vendor ownership check
    job_vendor_id = job.get("vendorId")
    try:
        vendor_oid = ObjectId(vendor_id)
    except InvalidId:
        raise DeliveryError("Invalid vendor ID.", 400)

    if job_vendor_id != vendor_oid:
        raise DeliveryError("This delivery job does not belong to your store.", 403)

    if job.get("status") in TERMINAL_STATES:
        raise DeliveryError("Cannot update a completed or cancelled job.", 409)

    now = datetime.now(timezone.utc)
    enriched_items = [
        {
            "itemTitle": item.get("itemTitle", ""),
            "reason":    item.get("reason"),
            "markedAt":  now.isoformat(),
        }
        for item in items
    ]

    update: dict = {
        "$set": {
            "unavailableItems": enriched_items,
            "updatedAt":        now,
        }
    }
    if vendor_note is not None:
        update["$set"]["vendorNote"] = vendor_note

    try:
        oid = ObjectId(job_id)
    except InvalidId:
        raise DeliveryError("Invalid job ID.", 400)

    updated = await delivery_jobs_collection.find_one_and_update(
        {"_id": oid}, update, return_document=True
    )
    if not updated:
        raise DeliveryError("Delivery job not found after update.", 404)

    logger.info("Job %s unavailable items updated by vendor %s", job_id, vendor_id)
    return _to_full(updated)


async def get_jobs_for_vendor(
    vendor_id: str,
    active_only: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> "PaginatedJobsOut":
    """
    Return delivery jobs assigned to a vendor.
    active_only=True returns only non-terminal jobs (the vendor order queue).
    active_only=False returns all jobs (history).
    """
    try:
        vendor_oid = ObjectId(vendor_id)
    except InvalidId:
        return PaginatedJobsOut(jobs=[], total=0, limit=limit, offset=offset)

    query: dict = {"vendorId": vendor_oid}
    if active_only:
        query["status"] = {"$nin": list(TERMINAL_STATES)}
    else:
        query["status"] = {"$in": list(TERMINAL_STATES)}

    total = await delivery_jobs_collection.count_documents(query)
    cursor = (
        delivery_jobs_collection.find(query)
        .sort("createdAt", -1)
        .skip(offset)
        .limit(limit)
    )
    jobs = await cursor.to_list(limit)
    return PaginatedJobsOut(
        jobs=[_to_full(j) for j in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )



# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-VENDOR ORDER ORCHESTRATION  (Iteration 20)
# ═══════════════════════════════════════════════════════════════════════════════

async def _lookup_vendor_by_name(vendor_name: str) -> Optional[dict]:
    """
    Exact case-insensitive lookup of a NowKart vendor by businessName.
    Returns None if no active, non-deleted vendor matches.
    Does NOT use fuzzy matching — only a full-string case-insensitive regex.
    """
    try:
        from vendor.db import vendors_collection as _vendors_col
        pattern = f"^{re.escape(vendor_name.strip())}$"
        return await _vendors_col.find_one({
            "businessName": {"$regex": pattern, "$options": "i"},
            "isDeleted": False,
            "isActive":  True,
        })
    except ImportError:
        logger.error("vendor module not available — cannot look up vendor by name")
        return None


async def _get_store_for_vendor(vendor_doc: dict) -> Optional[dict]:
    """Return the active store document linked to a vendor via storeId. None if unlinked."""
    store_oid = vendor_doc.get("storeId")
    if not store_oid:
        return None
    return await stores_collection.find_one({"_id": store_oid, "isActive": True})


async def _create_delivery_job_for_vendor_group(
    order_data: dict,
    vendor_items: list,
    store: dict,
    vendor_doc: dict,
    parent_order_id: ObjectId,
) -> DeliveryJobOut:
    """
    Create ONE delivery job for a specific vendor's line items within a Shopify order.

    Idempotent: re-calling for the same (shopifyOrderId, vendorId) pair returns
    the existing job without modification.

    Called exclusively by orchestrate_multi_vendor_order().
    """
    now = datetime.now(timezone.utc)
    shopify_order_id = f"gid://shopify/Order/{order_data['id']}"
    vendor_id = vendor_doc["_id"]

    # Idempotency check via compound (shopifyOrderId, vendorId)
    existing = await delivery_jobs_collection.find_one({
        "shopifyOrderId": shopify_order_id,
        "vendorId":        vendor_id,
    })
    if existing:
        logger.info(
            "Delivery job already exists for order %s vendor %s — idempotent return (id=%s)",
            shopify_order_id, vendor_doc.get("businessName", ""), existing["_id"],
        )
        return _to_full(existing)

    # Customer linkage
    shopify_customer_id: Optional[str] = None
    customer_id: Optional[ObjectId] = None
    if order_data.get("customer") and order_data["customer"].get("id"):
        shopify_customer_id = f"gid://shopify/Customer/{order_data['customer']['id']}"
        from auth.db import users_collection
        user = await users_collection.find_one({"shopifyCustomerId": shopify_customer_id})
        if user:
            customer_id = user["_id"]

    # Delivery address snapshot
    shipping = order_data.get("shipping_address") or {}
    delivery_address = {
        "firstName":   shipping.get("first_name", ""),
        "lastName":    shipping.get("last_name", ""),
        "line1":       shipping.get("address1", ""),
        "line2":       shipping.get("address2") or "",
        "city":        shipping.get("city", ""),
        "province":    shipping.get("province") or "",
        "postcode":    shipping.get("zip", ""),
        "country":     shipping.get("country", ""),
        "phone":       shipping.get("phone") or "",
        "coordinates": None,
    }

    # Line-item snapshot (this vendor's items only) + per-vendor subtotal
    order_items = []
    vendor_total = 0.0
    for item in vendor_items:
        price = float(item.get("price", "0"))
        qty   = int(item.get("quantity", 1))
        vendor_total += price * qty
        order_items.append({
            "title":        item.get("title", ""),
            "variantTitle": item.get("variant_title"),
            "quantity":     qty,
            "price":        price,
            "imageUrl":     None,
        })

    order_name = order_data.get("name") or f"#{order_data['id']}"
    vendor_name = vendor_doc.get("businessName", "")

    job_doc = {
        # Shopify linkage
        "shopifyOrderId":   shopify_order_id,
        "shopifyOrderName": order_name,
        "shopifyNumericId": int(order_data["id"]),

        # Parent order linkage (Iteration 20)
        "parentOrderId": parent_order_id,

        # Store & customer
        "storeId":           store["_id"],
        "customerId":        customer_id,
        "shopifyCustomerId": shopify_customer_id,
        "customerEmail": (
            order_data.get("email")
            or (order_data.get("customer") or {}).get("email")
        ),
        "customerFirstName": (order_data.get("customer") or {}).get("first_name"),
        "customerLastName":  (order_data.get("customer") or {}).get("last_name"),

        # Status
        "status":          DeliveryJobStatus.WAITING_VENDOR,
        "assignedRiderId": None,

        # Vendor
        "vendorId":          vendor_id,
        "vendorAcceptedAt":  None,
        "preparingAt":       None,
        "readyForPickupAt":  None,
        "unavailableItems":  [],
        "vendorNote":        None,
        "rejectionReason":   None,

        # Addresses
        "deliveryAddress": delivery_address,
        "pickupAddress":   store.get("address", {}),

        # Order snapshot (this vendor's items only)
        "orderItems":   order_items,
        "orderTotal":   round(vendor_total, 2),
        "currencyCode": order_data.get("currency", "GBP"),
        "deliveryInstructions": order_data.get("note"),

        # ETA (future)
        "estimatedDeliveryAt": None,
        "etaMinutes":          None,

        # Timing
        "assignedAt":  None,
        "pickedUpAt":  None,
        "arrivedAt":   None,
        "completedAt": None,

        # Failure tracking
        "failureCount":      0,
        "lastFailureReason": None,
        "retriedByJobId":    None,
        "originalJobId":     None,
        "proofOfDelivery":   None,

        # Audit trail
        "recentEvents": [
            {
                "status":    DeliveryJobStatus.WAITING_VENDOR,
                "timestamp": now.isoformat(),
                "actor":     "webhook:orders/paid",
                "note": (
                    f"Order {order_name} paid via Shopify — "
                    f"vendor group '{vendor_name}' delivery job created, awaiting vendor acceptance"
                ),
                "location":  None,
            }
        ],

        "createdAt": now,
        "updatedAt": now,
    }

    result = await delivery_jobs_collection.insert_one(job_doc)
    job_doc["_id"] = result.inserted_id
    logger.info(
        "Created vendor-group delivery job %s for order %s (vendor=%s)",
        job_doc["_id"], shopify_order_id, vendor_name,
    )
    return _to_full(job_doc)


async def orchestrate_multi_vendor_order(order_data: dict) -> dict:
    """
    Single entry-point for processing a Shopify orders/paid event.

    MODES
    ─────
    LEGACY       — no `vendor` field in any line item
                   → calls the existing create_delivery_job_from_order() for full
                     backward compatibility; wraps result in a parent_order record.
    SINGLE_VENDOR — all items carry the same Shopify vendor string and it maps to
                     exactly one active NowKart vendor.
    MULTI_VENDOR  — items from 2+ distinct Shopify vendor strings.

    VENDOR MAPPING RULE
    ───────────────────
    Shopify line-item `vendor` field matched against `vendors.businessName` using
    exact case-insensitive regex (^...$, i flag).  No fuzzy matching.
    Unmatched vendors are recorded in `parent_orders.unmappedGroups`; no delivery
    job is silently created for them.

    IDEMPOTENCY
    ───────────
    Guarded by a unique index on parent_orders.shopifyOrderId — re-processing
    the same Shopify order returns the stored result without side-effects.
    Per-job idempotency uses the compound (shopifyOrderId, vendorId) unique index.
    """
    now = datetime.now(timezone.utc)
    shopify_order_id = f"gid://shopify/Order/{order_data['id']}"

    # ── Service-level idempotency ─────────────────────────────────────────────
    existing_parent = await parent_orders_collection.find_one({"shopifyOrderId": shopify_order_id})
    if existing_parent:
        logger.info(
            "Parent order already exists for %s (id=%s) — idempotent return",
            shopify_order_id, existing_parent["_id"],
        )
        return _format_parent_order_result(existing_parent)

    # ── Group line items by Shopify vendor string ─────────────────────────────
    line_items = order_data.get("line_items") or []
    vendor_groups: dict = {}  # Optional[str] → list[item]
    for item in line_items:
        raw = (item.get("vendor") or "").strip()
        key = raw if raw else None
        vendor_groups.setdefault(key, []).append(item)

    has_any_vendor = any(k is not None for k in vendor_groups)

    # ── LEGACY MODE ───────────────────────────────────────────────────────────
    if not has_any_vendor:
        # No vendor field in any line item → preserve existing single-job behavior
        job = await create_delivery_job_from_order(order_data)
        parent_doc = {
            "shopifyOrderId":   shopify_order_id,
            "shopifyOrderName": order_data.get("name") or f"#{order_data['id']}",
            "shopifyNumericId": int(order_data["id"]),
            "totalPrice":       float(order_data.get("total_price", 0)),
            "currencyCode":     order_data.get("currency", "GBP"),
            "customerEmail": (
                order_data.get("email")
                or (order_data.get("customer") or {}).get("email")
            ),
            "deliveryJobIds":  [ObjectId(job.id)],
            "vendorGroups": [
                {
                    "shopifyVendorName": None,
                    "vendorId":         None,
                    "storeId":          None,
                    "deliveryJobId":    ObjectId(job.id),
                    "status":           "created_legacy",
                }
            ],
            "unmappedGroups": [],
            "mode":           "legacy",
            "status":         "created",
            "createdAt":      now,
            "updatedAt":      now,
        }
        await parent_orders_collection.insert_one(parent_doc)
        # Back-fill parentOrderId on the delivery job
        await delivery_jobs_collection.update_one(
            {"_id": ObjectId(job.id)},
            {"$set": {"parentOrderId": parent_doc["_id"]}},
        )
        logger.info(
            "Parent order %s created (legacy mode) for %s",
            parent_doc["_id"], shopify_order_id,
        )
        return {
            "action":        "delivery_job_created",   # backward-compatible key
            "jobId":         job.id,
            "orderId":       shopify_order_id,
            "status":        job.status,
            "parentOrderId": str(parent_doc["_id"]),
            "mode":          "legacy",
        }

    # ── MULTI-VENDOR / EXPLICIT SINGLE-VENDOR MODE ────────────────────────────

    # Insert parent_order immediately so it acts as a transaction guard.
    # deliveryJobIds / vendorGroups are filled after job creation.
    parent_doc = {
        "shopifyOrderId":   shopify_order_id,
        "shopifyOrderName": order_data.get("name") or f"#{order_data['id']}",
        "shopifyNumericId": int(order_data["id"]),
        "totalPrice":       float(order_data.get("total_price", 0)),
        "currencyCode":     order_data.get("currency", "GBP"),
        "customerEmail": (
            order_data.get("email")
            or (order_data.get("customer") or {}).get("email")
        ),
        "deliveryJobIds":  [],
        "vendorGroups":    [],
        "unmappedGroups":  [],
        "mode":            "pending",
        "status":          "pending",
        "createdAt":       now,
        "updatedAt":       now,
    }
    await parent_orders_collection.insert_one(parent_doc)
    parent_oid = parent_doc["_id"]

    created_jobs: list = []   # list of (DeliveryJobOut, shopify_vendor_name)
    vendor_groups_log: list = []
    unmapped_groups: list = []

    # Items with no vendor field (when the order also has explicit-vendor items)
    if None in vendor_groups:
        no_vendor_items = vendor_groups[None]
        unmapped_groups.append({
            "shopifyVendorName": None,
            "reason":            "no_vendor_field",
            "itemCount":         len(no_vendor_items),
            "itemTitles":        [i.get("title", "") for i in no_vendor_items],
        })
        logger.warning(
            "Order %s has %d item(s) with no vendor field — skipped (no delivery job created)",
            shopify_order_id, len(no_vendor_items),
        )

    # Items WITH explicit vendor string
    for vendor_name, items in vendor_groups.items():
        if vendor_name is None:
            continue  # handled above

        vendor_doc = await _lookup_vendor_by_name(vendor_name)
        if not vendor_doc:
            unmapped_groups.append({
                "shopifyVendorName": vendor_name,
                "reason":            "unmatched_vendor",
                "itemCount":         len(items),
                "itemTitles":        [i.get("title", "") for i in items],
            })
            vendor_groups_log.append({
                "shopifyVendorName": vendor_name,
                "vendorId":         None,
                "storeId":          None,
                "deliveryJobId":    None,
                "status":           "unmatched",
            })
            logger.warning(
                "Order %s: Shopify vendor '%s' not matched to any active NowKart vendor "
                "(checked vendors.businessName exact case-insensitive) — no job created",
                shopify_order_id, vendor_name,
            )
            continue

        store = await _get_store_for_vendor(vendor_doc)
        if not store:
            unmapped_groups.append({
                "shopifyVendorName": vendor_name,
                "reason":            "no_active_store",
                "itemCount":         len(items),
                "itemTitles":        [i.get("title", "") for i in items],
            })
            vendor_groups_log.append({
                "shopifyVendorName": vendor_name,
                "vendorId":         vendor_doc["_id"],
                "storeId":          None,
                "deliveryJobId":    None,
                "status":           "no_active_store",
            })
            logger.warning(
                "Order %s: vendor '%s' (id=%s) has no active store — no job created",
                shopify_order_id, vendor_name, vendor_doc["_id"],
            )
            continue

        job = await _create_delivery_job_for_vendor_group(
            order_data, items, store, vendor_doc, parent_oid
        )
        created_jobs.append((job, vendor_name))
        vendor_groups_log.append({
            "shopifyVendorName": vendor_name,
            "vendorId":         vendor_doc["_id"],
            "storeId":          store["_id"],
            "deliveryJobId":    ObjectId(job.id),
            "status":           "created",
        })

    # Determine final status and mode
    n_created = len(created_jobs)
    n_unmapped = len(unmapped_groups)
    if n_created == 0 and n_unmapped > 0:
        final_status = "failed"
    elif n_unmapped > 0:
        final_status = "partial"
    else:
        final_status = "created"

    final_mode = "single_vendor" if n_created == 1 else "multi_vendor"

    # Finalise parent_order record
    job_oids = [ObjectId(j.id) for j, _ in created_jobs]
    await parent_orders_collection.update_one(
        {"_id": parent_oid},
        {
            "$set": {
                "deliveryJobIds": job_oids,
                "vendorGroups":   vendor_groups_log,
                "unmappedGroups": unmapped_groups,
                "mode":           final_mode,
                "status":         final_status,
                "updatedAt":      now,
            }
        },
    )
    logger.info(
        "Parent order %s finalised: mode=%s status=%s jobs=%d unmapped=%d",
        parent_oid, final_mode, final_status, n_created, n_unmapped,
    )

    return {
        "action":         "delivery_jobs_created",
        "parentOrderId":  str(parent_oid),
        "jobs": [
            {"jobId": j.id, "vendorName": vn, "status": j.status}
            for j, vn in created_jobs
        ],
        "orderId":        shopify_order_id,
        "unmappedGroups": unmapped_groups,
        "mode":           final_mode,
        "status":         final_status,
    }


def _format_parent_order_result(parent: dict) -> dict:
    """Reconstruct orchestration result from a stored parent_order (idempotent re-delivery)."""
    mode = parent.get("mode", "legacy")
    if mode == "legacy":
        job_oids = parent.get("deliveryJobIds", [])
        return {
            "action":        "delivery_job_created",
            "jobId":         str(job_oids[0]) if job_oids else None,
            "orderId":       parent["shopifyOrderId"],
            "status":        "already_processed",
            "parentOrderId": str(parent["_id"]),
            "mode":          "legacy",
        }
    vg_log = parent.get("vendorGroups", [])
    return {
        "action":         "delivery_jobs_created",
        "parentOrderId":  str(parent["_id"]),
        "jobs": [
            {
                "jobId":      str(vg.get("deliveryJobId", "")),
                "vendorName": vg.get("shopifyVendorName"),
                "status":     vg.get("status", ""),
            }
            for vg in vg_log
            if vg.get("deliveryJobId") is not None
        ],
        "orderId":        parent["shopifyOrderId"],
        "unmappedGroups": parent.get("unmappedGroups", []),
        "mode":           mode,
        "status":         parent.get("status", ""),
    }


async def cancel_all_delivery_jobs_by_order_id(
    shopify_order_id: str,
    reason: str = "Cancelled via Shopify",
) -> list:
    """
    Cancel ALL delivery jobs for a Shopify order (handles multi-vendor orders).
    Returns list of DeliveryJobOut — one per job found.
    Jobs in terminal states are returned unchanged.
    IN_TRANSIT jobs receive a warning event but are NOT cancelled.
    """
    jobs = await delivery_jobs_collection.find(
        {"shopifyOrderId": shopify_order_id}
    ).to_list(100)

    if not jobs:
        logger.info("No delivery jobs found for order %s — nothing to cancel.", shopify_order_id)
        return []

    results = []
    for job in jobs:
        current = job.get("status")
        job_id  = str(job["_id"])

        if current in TERMINAL_STATES:
            logger.info("Job %s already in terminal state '%s' — skipping cancel.", job_id, current)
            results.append(_to_full(job))
            continue

        if current == DeliveryJobStatus.IN_TRANSIT:
            now = datetime.now(timezone.utc)
            alert_event = {
                "status":    current,
                "timestamp": now.isoformat(),
                "actor":     "webhook:orders/cancelled",
                "note": (
                    "ALERT: Shopify order cancelled while rider is IN TRANSIT. "
                    "Admin intervention required — do not auto-cancel."
                ),
                "location":  None,
            }
            await delivery_jobs_collection.update_one(
                {"_id": job["_id"]},
                {
                    "$push": {"recentEvents": {"$each": [alert_event], "$slice": -50}},
                    "$set":  {"updatedAt": now},
                },
            )
            logger.warning(
                "ALERT: Order %s cancelled by Shopify but job %s is IN_TRANSIT.",
                shopify_order_id, job_id,
            )
            refreshed = await delivery_jobs_collection.find_one({"_id": job["_id"]})
            results.append(_to_full(refreshed))
            continue

        cancelled = await update_job_status(
            job_id, DeliveryJobStatus.CANCELLED, "webhook:orders/cancelled", reason
        )
        results.append(cancelled)

    return results
