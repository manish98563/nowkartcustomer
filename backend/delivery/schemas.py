"""
Delivery module schemas — Pydantic models for requests, responses, and enums.

ARCHITECTURE NOTE:
  DeliveryJobCustomerOut  — limited view for the Customer App (no internal ops fields).
  DeliveryJobOut          — full view for the future Admin Dashboard and Rider App.
  The two response shapes allow the same service layer to serve both clients
  without two separate API routes.

RIDER APP EXTENSION POINTS:
  DeliveryJobCustomerOut has commented-out fields that will be uncommented when
  the Rider App ships: riderFirstName, riderLocation, riderEta.
  Adding those fields is backward-compatible — existing consumers ignore unknown fields.
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


# ─── Status enum ──────────────────────────────────────────────────────────────

class DeliveryJobStatus(str, Enum):
    # ── Vendor workflow (new in Iteration 10) ─────────────────────────────────
    WAITING_VENDOR   = "waiting_vendor"    # initial state — awaiting vendor acceptance
    VENDOR_ACCEPTED  = "vendor_accepted"   # vendor accepted, reviewing items
    PREPARING        = "preparing"         # vendor preparing items
    READY_FOR_PICKUP = "ready_for_pickup"  # vendor done — rider can now be assigned
    REJECTED         = "rejected"          # vendor rejected order (terminal)
    # ── Rider workflow (existing) ─────────────────────────────────────────────
    PENDING_ASSIGNMENT = "pending_assignment"
    ASSIGNED           = "assigned"
    AT_STORE           = "at_store"
    IN_TRANSIT         = "in_transit"
    ARRIVED            = "arrived"
    DELIVERED          = "delivered"
    FAILED_DELIVERY    = "failed_delivery"
    CANCELLED          = "cancelled"


# ─── Embedded sub-schemas ─────────────────────────────────────────────────────

class DeliveryAddressOut(BaseModel):
    firstName:   Optional[str] = None
    lastName:    Optional[str] = None
    line1:       str
    line2:       Optional[str] = None
    city:        str
    province:    Optional[str] = None
    postcode:    str
    country:     str
    phone:       Optional[str] = None
    coordinates: Optional[dict] = None   # {"lat": float, "lng": float} — populated by ETA module


class OrderItemSnapshotOut(BaseModel):
    title:        str
    variantTitle: Optional[str] = None
    quantity:     int
    price:        float
    imageUrl:     Optional[str] = None


class DeliveryEventOut(BaseModel):
    """Single entry in the delivery job audit trail."""
    status:    str
    timestamp: str            # ISO 8601
    actor:     str            # "system" | "webhook:orders/paid" | "admin" | "rider:{id}"
    note:      Optional[str] = None


# ─── Customer-facing response (limited fields) ────────────────────────────────

class DeliveryJobCustomerOut(BaseModel):
    """
    Delivery job view for the Customer App.
    Contains only what a customer needs to see — no internal ops fields,
    no rider contact details, no failure internals.
    """
    id:                  str
    shopifyOrderId:      str
    shopifyOrderName:    str
    status:              DeliveryJobStatus
    statusLabel:         str
    deliveryAddress:     DeliveryAddressOut
    orderItems:          List[OrderItemSnapshotOut]
    orderTotal:          float
    currencyCode:        str
    estimatedDeliveryAt: Optional[str] = None
    etaMinutes:          Optional[int] = None
    createdAt:           str
    updatedAt:           str
    # ── Rider App extension points — uncomment when Rider App ships ──────────
    # riderFirstName: Optional[str] = None
    # riderLocation:  Optional[dict] = None   # {"lat": float, "lng": float}
    # riderEta:       Optional[str] = None     # ISO datetime


# ─── Full response (Admin Dashboard + Rider App + internal) ───────────────────

class DeliveryJobOut(BaseModel):
    """
    Full delivery job view with all operational fields.
    Used by the future Admin Dashboard and Rider App.
    Auth is applied at the router level; this schema itself is unopinionated.
    """
    id:                  str
    shopifyOrderId:      str
    shopifyOrderName:    str
    shopifyNumericId:    int
    storeId:             str
    status:              DeliveryJobStatus
    statusLabel:         str
    customerId:          Optional[str] = None
    shopifyCustomerId:   Optional[str] = None
    customerEmail:       Optional[str] = None
    customerFirstName:   Optional[str] = None
    customerLastName:    Optional[str] = None
    assignedRiderId:     Optional[str] = None
    deliveryAddress:     DeliveryAddressOut
    pickupAddress:       DeliveryAddressOut
    orderItems:          List[OrderItemSnapshotOut]
    orderTotal:          float
    currencyCode:        str
    deliveryInstructions: Optional[str] = None
    estimatedDeliveryAt: Optional[str] = None
    etaMinutes:          Optional[int] = None
    assignedAt:          Optional[str] = None
    pickedUpAt:          Optional[str] = None
    arrivedAt:           Optional[str] = None
    completedAt:         Optional[str] = None
    failureCount:        int = 0
    lastFailureReason:   Optional[str] = None
    recentEvents:        List[DeliveryEventOut] = []
    # ── Vendor fields (added in Iteration 10) ─────────────────────────────────
    vendorId:            Optional[str] = None
    vendorAcceptedAt:    Optional[str] = None
    preparingAt:         Optional[str] = None
    readyForPickupAt:    Optional[str] = None
    unavailableItems:    List[dict] = []
    vendorNote:          Optional[str] = None
    rejectionReason:     Optional[str] = None
    createdAt:           str
    updatedAt:           str


# ─── Request bodies ───────────────────────────────────────────────────────────

class DeliveryJobStatusUpdateIn(BaseModel):
    """
    Request body for PUT /api/delivery/jobs/{id}/status.
    The `actor` field identifies who triggered the transition:
      "admin"        — via Admin Dashboard
      "rider:{id}"   — via Rider App (set by rider router in Phase 2)
      "system"       — automated/internal
    """
    status: DeliveryJobStatus
    note:   Optional[str] = None
    actor:  Optional[str] = "admin"


# ─── Paginated list response ──────────────────────────────────────────────────

class PaginatedJobsOut(BaseModel):
    jobs:   List[DeliveryJobOut]
    total:  int
    limit:  int
    offset: int


# ─── Store schemas ────────────────────────────────────────────────────────────

class StoreAddressOut(BaseModel):
    line1:       str
    city:        str
    postcode:    str
    country:     str
    coordinates: Optional[dict] = None   # {"lat": float, "lng": float}


class StoreSettingsOut(BaseModel):
    defaultEtaMinutes: int
    prepTimeMinutes:   int
    maxConcurrentJobs: int
    autoAssignment:    bool


class StoreOut(BaseModel):
    id:            str
    name:          str
    shopifyDomain: str
    isDefault:     bool
    isActive:      bool
    address:       StoreAddressOut
    settings:      StoreSettingsOut
    createdAt:     str


# ─── Assignment request ───────────────────────────────────────────────────────

class DeliveryJobAssignIn(BaseModel):
    """
    Request body for POST /api/delivery/jobs/{id}/assign.
    Admin provides the riderId to assign to the job.
    """
    riderId: str
    note:    Optional[str] = None
