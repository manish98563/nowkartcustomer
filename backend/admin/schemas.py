"""
Admin module schemas — Pydantic models and enums.

RBAC Role hierarchy (highest → lowest):
  super_admin (4) — full platform control, can create/manage admins
  admin (3)       — full operations, cannot manage admin accounts
  operations_manager (2) — manage deliveries and assignments
  support (1)     — read-only + limited overrides
"""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ─── Role enum ────────────────────────────────────────────────────────────────

class AdminRole(str, Enum):
    SUPER_ADMIN         = "super_admin"
    ADMIN               = "admin"
    OPERATIONS_MANAGER  = "operations_manager"
    SUPPORT             = "support"


ROLE_HIERARCHY: dict[str, int] = {
    AdminRole.SUPPORT:            1,
    AdminRole.OPERATIONS_MANAGER: 2,
    AdminRole.ADMIN:              3,
    AdminRole.SUPER_ADMIN:        4,
}

# Set of all valid admin role strings (for fast lookup)
ADMIN_ROLES: frozenset[str] = frozenset(ROLE_HIERARCHY.keys())


# ─── Auth schemas ─────────────────────────────────────────────────────────────

class AdminLoginIn(BaseModel):
    email:    str
    password: str


class AdminSessionOut(BaseModel):
    accessToken:  str
    refreshToken: str
    expiresIn:    int   # seconds
    admin:        "AdminOut"


class AdminRefreshIn(BaseModel):
    refreshToken: str


class AdminRefreshOut(BaseModel):
    """Minimal refresh response — only the two tokens the Admin Dashboard reads."""
    accessToken:  str
    refreshToken: str


class AdminLogoutIn(BaseModel):
    refreshToken: str


class ChangePasswordIn(BaseModel):
    currentPassword: str
    newPassword:     str


# ─── Admin profile schemas ────────────────────────────────────────────────────

class AdminOut(BaseModel):
    id:          str
    email:       str
    firstName:   str
    lastName:    str
    role:        AdminRole
    isActive:    bool
    lastLoginAt: Optional[str] = None
    createdAt:   str
    updatedAt:   str


class AdminCreateIn(BaseModel):
    """Super admin creates a new admin account."""
    email:     str
    password:  str
    firstName: str
    lastName:  str
    role:      AdminRole = AdminRole.SUPPORT


class AdminUpdateIn(BaseModel):
    """Patch semantics — only provided fields are changed."""
    firstName: Optional[str]    = None
    lastName:  Optional[str]    = None
    role:      Optional[AdminRole] = None


class PaginatedAdminsOut(BaseModel):
    admins: List[AdminOut]
    total:  int
    limit:  int
    offset: int


# ─── Audit log schemas ────────────────────────────────────────────────────────

class AuditLogOut(BaseModel):
    id:           str
    adminId:      str
    adminEmail:   str
    adminRole:    str
    action:       str
    resourceType: str
    resourceId:   str
    details:      Dict[str, Any] = {}
    timestamp:    str


class PaginatedAuditLogsOut(BaseModel):
    logs:   List[AuditLogOut]
    total:  int
    limit:  int
    offset: int


# ─── Store management schemas ─────────────────────────────────────────────────

class StoreAddressIn(BaseModel):
    line1:    str
    city:     str
    postcode: str
    country:  str


class StoreCreateIn(BaseModel):
    name:               str
    shopifyDomain:      Optional[str] = ""
    address:            StoreAddressIn
    phone:              Optional[str] = None
    operatingHours:     Optional[dict] = None
    deliveryRadiusKm:   Optional[float] = None
    settings:           Optional[dict] = None


class StoreUpdateIn(BaseModel):
    name:             Optional[str]   = None
    phone:            Optional[str]   = None
    address:          Optional[StoreAddressIn] = None
    operatingHours:   Optional[dict]  = None
    deliveryRadiusKm: Optional[float] = None
    settings:         Optional[dict]  = None


class StoreAdminOut(BaseModel):
    id:               str
    name:             str
    shopifyDomain:    str
    isDefault:        bool
    isActive:         bool
    address:          dict
    settings:         dict
    phone:            Optional[str] = None
    operatingHours:   Optional[dict] = None
    deliveryRadiusKm: Optional[float] = None
    createdAt:        str
    updatedAt:        str


# ─── Dashboard statistics schemas ─────────────────────────────────────────────

class DeliveryStatsOut(BaseModel):
    total:       int
    todayCount:  int
    activeCount: int
    byStatus:    Dict[str, int] = {}


class RiderStatsOut(BaseModel):
    total:    int
    active:   int
    byStatus: Dict[str, int] = {}


class VendorStatsOut(BaseModel):
    total:    int
    active:   int
    byStatus: Dict[str, int] = {}


class StoreStatsOut(BaseModel):
    total:  int
    active: int


class DashboardStatsOut(BaseModel):
    deliveries: DeliveryStatsOut
    riders:     RiderStatsOut
    vendors:    VendorStatsOut
    stores:     StoreStatsOut
    recentActivity: List[AuditLogOut] = []


# ─── Delivery admin schemas ───────────────────────────────────────────────────

class AdminDeliveryStatusUpdateIn(BaseModel):
    """Force a delivery job status transition (admin override)."""
    status: str
    note:   Optional[str] = None


class AdminReassignVendorIn(BaseModel):
    vendorId: str
    note:     Optional[str] = None


AdminSessionOut.model_rebuild()
