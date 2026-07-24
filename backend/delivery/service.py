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
"""
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId

from .db import delivery_jobs_collection, stores_collection
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
