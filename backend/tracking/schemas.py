"""
Tracking schemas — the canonical interface for order tracking data.

ARCHITECTURE PREP FOR RIDER APP:
These models are intentionally forward-compatible. When the Rider App is
built, the following fields will be added to TrackingStatusOut without
breaking existing consumers:
  - riderName: Optional[str]
  - riderPhone: Optional[str]
  - riderLocation: Optional[dict]   # {"lat": float, "lng": float, "updatedAt": str}
  - riderEta: Optional[str]         # ISO datetime from rider's GPS ETA
  - trackingUrl: Optional[str]      # External courier tracking URL

The `isActive` flag is the key signal to the frontend for whether to
start polling and show the live-tracking UI.
"""
from typing import List, Optional

from pydantic import BaseModel

from auth.schemas import AddressOut, OrderLineItemOut


class TrackingStageOut(BaseModel):
    key: str            # placed | confirmed | preparing | out_for_delivery | delivered | cancelled
    label: str
    timestamp: Optional[str] = None   # ISO 8601 when this stage occurred (from Shopify data)
    done: bool
    active: bool        # True = customer is currently at this stage
    icon: str           # Ionicons name for the frontend


class TrackingStatusOut(BaseModel):
    orderId: str
    orderName: str
    currentStage: str        # key of active / last-completed stage
    currentStageLabel: str
    lastUpdatedAt: Optional[str] = None
    estimatedDelivery: Optional[str] = None  # populated only when Shopify provides it
    isActive: bool           # False for FULFILLED or CANCELLED — frontend stops polling
    stages: List[TrackingStageOut]
    deliveryAddress: Optional[AddressOut] = None
    totalPrice: float
    currencyCode: str
    items: List[OrderLineItemOut]    # included so tracking screen needs only ONE API call
    # ── Rider App extension points (uncomment when Rider App is built) ──
    # riderName: Optional[str] = None
    # riderPhone: Optional[str] = None
    # riderLocation: Optional[dict] = None
    # riderEta: Optional[str] = None
    # trackingUrl: Optional[str] = None
