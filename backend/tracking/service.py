"""
Tracking service — maps Shopify order + fulfillment state to
TrackingStatusOut. This is the ONLY place the mapping logic lives.

Stage-to-Shopify mapping (all based on verified Shopify data):
 placed          → always done   (order exists)
 confirmed       → financialStatus in PAID/AUTHORIZED/PARTIALLY_PAID
 preparing       → fulfillments.length > 0 OR fulfillmentStatus PARTIAL/PARTIALLY_FULFILLED
 out_for_delivery→ (future: rider app) interim — done only after delivered
 delivered       → fulfillmentStatus == FULFILLED
 cancelled       → cancelledAt is set

Note: "Out for Delivery" maps to hasFulfillment && !FULFILLED today.
When the Rider App ships, this stage will be driven by real rider GPS/status.
"""
import logging
from typing import Any, Optional

from auth import service as auth_service
from auth.customer_account_client import CustomerAccountAPIError
from auth.schemas import AddressOut, OrderLineItemOut
from auth.service import AuthError

from .schemas import TrackingStageOut, TrackingStatusOut

logger = logging.getLogger(__name__)


def _money(m: Any) -> Optional[float]:
    if not m:
        return None
    try:
        return float(m["amount"])
    except Exception:
        return None


def _currency(m: Any) -> str:
    return (m or {}).get("currencyCode", "GBP")


def _build_stages(
    processedAt: str,
    financialStatus: Optional[str],
    fulfillmentStatus: Optional[str],
    cancelledAt: Optional[str],
    fulfillments: list,
) -> tuple[list[TrackingStageOut], str, str]:
    """
    Returns (stages, currentStageKey, currentStageLabel).
    Only derives from verified Shopify fields — never fabricates status.
    """
    paid = (financialStatus or "").upper() in ("PAID", "AUTHORIZED", "PARTIALLY_PAID")
    fs = (fulfillmentStatus or "").upper()
    fulfilled = fs == "FULFILLED"
    partial = fs in ("PARTIAL", "PARTIALLY_FULFILLED")
    has_fulfillment = len(fulfillments) > 0
    cancelled = bool(cancelledAt)

    # Timestamps from Shopify data
    first_fulfillment_at = fulfillments[0].get("createdAt") if fulfillments else None
    delivered_at = fulfillments[0].get("updatedAt") if (fulfillments and fulfilled) else None

    if cancelled:
        stages = [
            TrackingStageOut(
                key="placed", label="Order Placed", timestamp=processedAt,
                done=True, active=False, icon="receipt-outline",
            ),
            TrackingStageOut(
                key="cancelled", label="Order Cancelled", timestamp=cancelledAt,
                done=True, active=True, icon="close-circle-outline",
            ),
        ]
        return stages, "cancelled", "Order Cancelled"

    preparing_done = has_fulfillment or partial or fulfilled
    out_for_delivery_done = fulfilled  # will become rider-GPS-driven in Rider App
    out_for_delivery_active = has_fulfillment and not fulfilled

    stages = [
        TrackingStageOut(
            key="placed", label="Order Placed", timestamp=processedAt,
            done=True, active=False, icon="receipt-outline",
        ),
        TrackingStageOut(
            key="confirmed", label="Payment Confirmed", timestamp=processedAt if paid else None,
            done=paid, active=not paid, icon="card-outline",
        ),
        TrackingStageOut(
            key="preparing", label="Preparing Order", timestamp=first_fulfillment_at,
            done=preparing_done, active=not preparing_done and paid,
            icon="cube-outline",
        ),
        TrackingStageOut(
            key="out_for_delivery", label="Out for Delivery", timestamp=first_fulfillment_at if out_for_delivery_done else None,
            done=out_for_delivery_done, active=out_for_delivery_active,
            icon="bicycle-outline",
        ),
        TrackingStageOut(
            key="delivered", label="Delivered", timestamp=delivered_at,
            done=fulfilled, active=False, icon="checkmark-circle-outline",
        ),
    ]

    # Determine active stage key/label
    active_stage = next((s for s in reversed(stages) if s.done), stages[0])
    in_progress = next((s for s in stages if s.active), None)
    current = in_progress if in_progress else active_stage

    return stages, current.key, current.label


async def get_tracking_status(user: dict, order_id: str) -> TrackingStatusOut:
    """
    Single-call function that returns a TrackingStatusOut with everything
    the tracking screen needs. The frontend never needs to fetch order
    detail separately when tracking — one API call covers it all.
    """
    order_detail = await auth_service.get_order_detail(user, order_id)

    fulfillments_raw = [
        {"createdAt": f.createdAt, "updatedAt": f.updatedAt}
        for f in order_detail.fulfillments
    ]

    stages, current_key, current_label = _build_stages(
        processedAt=order_detail.processedAt,
        financialStatus=order_detail.financialStatus,
        fulfillmentStatus=order_detail.fulfillmentStatus,
        cancelledAt=order_detail.cancelledAt,
        fulfillments=fulfillments_raw,
    )

    fs = (order_detail.fulfillmentStatus or "").upper()
    is_active = not order_detail.cancelledAt and fs != "FULFILLED"

    # Last updated = most recent fulfillment updatedAt, else processedAt
    last_updated = None
    if order_detail.fulfillments:
        last_updated = order_detail.fulfillments[-1].updatedAt or order_detail.fulfillments[-1].createdAt
    last_updated = last_updated or order_detail.processedAt

    return TrackingStatusOut(
        orderId=order_detail.id,
        orderName=order_detail.name,
        currentStage=current_key,
        currentStageLabel=current_label,
        lastUpdatedAt=last_updated,
        estimatedDelivery=None,   # Shopify does not expose delivery ETA in Customer Account API
        isActive=is_active,
        stages=stages,
        deliveryAddress=order_detail.shippingAddress,
        totalPrice=order_detail.totalPrice,
        currencyCode=order_detail.currencyCode,
        items=order_detail.lineItems,
    )
