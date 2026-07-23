"""
Rider module schemas — Pydantic models for all rider API shapes.

Separation of concerns:
  RiderOut             — public rider profile (for the rider themselves)
  RiderAdminOut        — full rider detail for admin (includes all fields)
  RiderSessionOut      — returned on login / refresh
  RiderCreateIn        — admin creates a new rider account
  RiderUpdateIn        — admin updates rider fields
  DeliveryJobBriefOut  — minimal job summary for rider job history (avoids
                         importing full DeliveryJobOut from delivery module
                         into every schema consumer)

RIDER APP EXTENSION POINTS:
  RiderOut has commented-out GPS fields that will be added when the Rider App
  ships: currentLocation, currentJobId. Adding these is backward-compatible.
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


# ─── Enums ────────────────────────────────────────────────────────────────────

class RiderStatus(str, Enum):
    ONLINE  = "online"
    OFFLINE = "offline"
    BUSY    = "busy"


class RiderVehicleType(str, Enum):
    BICYCLE    = "bicycle"
    MOTORCYCLE = "motorcycle"
    CAR        = "car"


# ─── Embedded sub-schemas ─────────────────────────────────────────────────────

class RiderStatsOut(BaseModel):
    totalDeliveries:     int   = 0
    completedDeliveries: int   = 0
    failedDeliveries:    int   = 0
    cancelledDeliveries: int   = 0
    successRate:         float = 0.0   # percentage, 0–100


# ─── Rider profile outputs ────────────────────────────────────────────────────

class RiderOut(BaseModel):
    """
    Rider profile view — for the rider themselves (returned in the session
    and on GET /api/rider/profile).
    """
    id:            str
    email:         str
    phone:         str
    firstName:     str
    lastName:      str
    status:        RiderStatus
    vehicleType:   RiderVehicleType
    vehicleNumber: Optional[str] = None
    storeIds:      List[str] = []
    stats:         RiderStatsOut
    isActive:      bool
    lastSeenAt:    Optional[str] = None
    createdAt:     str
    updatedAt:     str
    # ── Rider App extension points (uncomment when Rider App ships) ──────────
    # currentLocation: Optional[dict] = None   # {"lat": float, "lng": float}
    # currentJobId:    Optional[str]  = None


class RiderAdminOut(BaseModel):
    """
    Full rider view for the Admin Dashboard — includes internal fields.
    Never returned to the rider themselves.
    """
    id:            str
    email:         str
    phone:         str
    firstName:     str
    lastName:      str
    status:        RiderStatus
    vehicleType:   RiderVehicleType
    vehicleNumber: Optional[str] = None
    storeIds:      List[str] = []
    devicePushToken: Optional[str] = None
    platformOS:    Optional[str] = None
    stats:         RiderStatsOut
    isActive:      bool
    isDeleted:     bool
    lastSeenAt:    Optional[str] = None
    createdAt:     str
    updatedAt:     str


# ─── Auth schemas ─────────────────────────────────────────────────────────────

class RiderLoginIn(BaseModel):
    email:    str
    password: str


class RiderSessionOut(BaseModel):
    accessToken:  str
    refreshToken: str
    expiresIn:    int    # seconds
    rider:        RiderOut


class RiderRefreshIn(BaseModel):
    refreshToken: str


class RiderLogoutIn(BaseModel):
    refreshToken: str


# ─── Rider action schemas ─────────────────────────────────────────────────────

class RiderStatusUpdateIn(BaseModel):
    status: RiderStatus


class PushTokenIn(BaseModel):
    token:    str
    platform: str   # "ios" | "android"


# ─── Admin CRUD schemas ───────────────────────────────────────────────────────

class RiderCreateIn(BaseModel):
    """Admin creates a new rider account."""
    email:         str
    phone:         str
    password:      str
    firstName:     str
    lastName:      str
    vehicleType:   RiderVehicleType = RiderVehicleType.BICYCLE
    vehicleNumber: Optional[str] = None
    storeIds:      List[str] = []


class RiderUpdateIn(BaseModel):
    """Admin updates rider fields. All fields optional — patch semantics."""
    phone:         Optional[str]            = None
    firstName:     Optional[str]            = None
    lastName:      Optional[str]            = None
    vehicleType:   Optional[RiderVehicleType] = None
    vehicleNumber: Optional[str]            = None
    storeIds:      Optional[List[str]]      = None


class PaginatedRidersOut(BaseModel):
    riders: List[RiderAdminOut]
    total:  int
    limit:  int
    offset: int


# ─── Job brief (rider history view) ──────────────────────────────────────────

class DeliveryJobBriefOut(BaseModel):
    """
    Minimal job summary for the rider's delivery history screen.
    Avoids importing the full DeliveryJobOut schema from the delivery module.
    """
    id:               str
    shopifyOrderName: str
    status:           str
    statusLabel:      str
    orderTotal:       float
    currencyCode:     str
    deliveryCity:     Optional[str] = None
    completedAt:      Optional[str] = None
    createdAt:        str
