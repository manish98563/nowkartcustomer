"""
Vendor module schemas — all Pydantic models.

VendorStatus values:
  OPEN   — store is accepting orders
  CLOSED — store is not accepting orders
  BUSY   — store is currently at capacity

VendorOrderOut is the vendor-specific view of a delivery job.
It exposes item details and preparation context without internal
operational fields meant for the admin or rider.
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


# ─── Enums ────────────────────────────────────────────────────────────────────

class VendorStatus(str, Enum):
    OPEN   = "open"
    CLOSED = "closed"
    BUSY   = "busy"


# ─── Embedded sub-schemas ─────────────────────────────────────────────────────

class VendorStatsOut(BaseModel):
    totalOrders:               int   = 0
    acceptedOrders:            int   = 0
    rejectedOrders:            int   = 0
    completedOrders:           int   = 0
    averagePreparationMinutes: float = 0.0


class UnavailableItemIn(BaseModel):
    """One item the vendor cannot fulfil."""
    itemTitle: str
    reason:    Optional[str] = None   # "out_of_stock" | "damaged" | free text


class MarkUnavailableItemsIn(BaseModel):
    items:      List[UnavailableItemIn]
    vendorNote: Optional[str] = None   # optional message to rider / admin


# ─── Vendor profile outputs ───────────────────────────────────────────────────

class VendorOut(BaseModel):
    """Vendor's own profile view."""
    id:           str
    email:        str
    phone:        str
    businessName: str
    firstName:    str
    lastName:     str
    status:       VendorStatus
    storeId:      Optional[str] = None
    stats:        VendorStatsOut
    isActive:     bool
    lastSeenAt:   Optional[str] = None
    createdAt:    str
    updatedAt:    str


class VendorAdminOut(BaseModel):
    """Full vendor detail for the Admin Dashboard."""
    id:              str
    email:           str
    phone:           str
    businessName:    str
    firstName:       str
    lastName:        str
    status:          VendorStatus
    storeId:         Optional[str] = None
    devicePushToken: Optional[str] = None
    platformOS:      Optional[str] = None
    stats:           VendorStatsOut
    isActive:        bool
    isDeleted:       bool
    lastSeenAt:      Optional[str] = None
    createdAt:       str
    updatedAt:       str


# ─── Auth schemas ─────────────────────────────────────────────────────────────

class VendorLoginIn(BaseModel):
    email:    str
    password: str


class VendorSessionOut(BaseModel):
    accessToken:  str
    refreshToken: str
    expiresIn:    int    # seconds
    vendor:       VendorOut


class VendorRefreshIn(BaseModel):
    refreshToken: str


class VendorLogoutIn(BaseModel):
    refreshToken: str


# ─── Vendor action schemas ────────────────────────────────────────────────────

class VendorStatusUpdateIn(BaseModel):
    status: VendorStatus


class VendorPushTokenIn(BaseModel):
    token:    str
    platform: str   # "ios" | "android"


class VendorOrderAcceptIn(BaseModel):
    note: Optional[str] = None   # optional vendor message


class VendorOrderRejectIn(BaseModel):
    reason: str   # mandatory rejection reason


# ─── Admin CRUD schemas ───────────────────────────────────────────────────────

class VendorCreateIn(BaseModel):
    email:        str
    phone:        str
    password:     str
    businessName: str
    firstName:    str
    lastName:     str
    storeId:      Optional[str] = None


class VendorUpdateIn(BaseModel):
    phone:        Optional[str] = None
    businessName: Optional[str] = None
    firstName:    Optional[str] = None
    lastName:     Optional[str] = None
    storeId:      Optional[str] = None


class PaginatedVendorsOut(BaseModel):
    vendors: List[VendorAdminOut]
    total:   int
    limit:   int
    offset:  int


# ─── Vendor order view ────────────────────────────────────────────────────────

class VendorOrderItemOut(BaseModel):
    title:         str
    variantTitle:  Optional[str] = None
    quantity:      int
    price:         float
    isUnavailable: bool = False   # True if vendor marked this item unavailable


class VendorOrderOut(BaseModel):
    """
    Vendor-facing view of a delivery job.
    Shows what needs to be prepared and the current vendor workflow state.
    """
    id:                  str
    shopifyOrderName:    str
    status:              str
    statusLabel:         str
    orderItems:          List[VendorOrderItemOut]
    unavailableItems:    List[dict] = []
    deliveryInstructions: Optional[str] = None
    vendorNote:          Optional[str] = None
    orderTotal:          float
    currencyCode:        str
    vendorAcceptedAt:    Optional[str] = None
    preparingAt:         Optional[str] = None
    readyForPickupAt:    Optional[str] = None
    createdAt:           str
    updatedAt:           str
