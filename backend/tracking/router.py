import logging
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query

from auth.customer_account_client import CustomerAccountAPIError
from auth.dependencies import get_current_user_required
from auth.service import AuthError

from . import service
from .schemas import TrackingStatusOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.get("/order", response_model=TrackingStatusOut)
async def get_tracking(
    id: str = Query(..., description="Shopify order GID (URL-encoded)"),
    user: dict = Depends(get_current_user_required),
):
    """
    Returns the live tracking status for a single order.
    Uses Shopify fulfillment data exclusively — no fabricated values.

    The ?id= query param (not a path segment) safely carries Shopify
    GIDs which contain slashes that Kubernetes NGINX would otherwise
    double-decode if used as a path segment.

    ARCHITECTURE NOTE:
    This endpoint is the extension point for the future Rider App.
    When the Rider App is built, riderName/riderLocation/riderEta will
    be populated here from a separate rider-data store, without any
    changes needed to this route's signature.
    """
    try:
        decoded_id = unquote(id)
        return await service.get_tracking_status(user, decoded_id)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except CustomerAccountAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
