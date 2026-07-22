import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from . import service
from .customer_account_client import CustomerAccountAPIError
from .dependencies import get_current_user_optional, get_current_user_required
from .schemas import (
    AddressIn,
    AddressOut,
    AuthorizeUrlRequest,
    AuthorizeUrlResponse,
    LogoutRequest,
    OrderDetailOut,
    ProfileOut,
    RefreshRequest,
    SessionOut,
    TokenExchangeRequest,
)
from .service import AuthError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/shopify/authorize-url", response_model=AuthorizeUrlResponse)
async def get_authorize_url(payload: AuthorizeUrlRequest):
    try:
        return await service.build_authorize_url(payload.codeChallenge, payload.platform, payload.origin)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except CustomerAccountAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/shopify/token-exchange", response_model=SessionOut)
async def token_exchange(payload: TokenExchangeRequest):
    try:
        return await service.exchange_code(payload.code, payload.state, payload.codeVerifier, payload.redirectUri)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except CustomerAccountAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/refresh", response_model=SessionOut)
async def refresh(payload: RefreshRequest):
    try:
        return await service.refresh_session(payload.refreshToken)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/logout")
async def logout_endpoint(payload: LogoutRequest):
    await service.logout(payload.refreshToken)
    return {"ok": True}


@router.get("/me", response_model=ProfileOut)
async def me(user: dict = Depends(get_current_user_required)):
    try:
        return await service.get_profile(user)
    except CustomerAccountAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/orders", response_model=OrderDetailOut)
async def get_order(id: str = Query(...), user: dict = Depends(get_current_user_required)):
    """Full order detail including line items, pricing breakdown, address, and fulfillments.
    Accepts the Shopify order GID via ?id= query param (not a path segment) to avoid
    Kubernetes NGINX double-decoding slashes in GIDs like gid://shopify/Order/123."""
    try:
        from urllib.parse import unquote
        decoded_id = unquote(id)
        return await service.get_order_detail(user, decoded_id)
    except service.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except CustomerAccountAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/addresses")
async def list_addresses(user: dict = Depends(get_current_user_required)):
    try:
        profile = await service.get_profile(user)
    except CustomerAccountAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return profile.addresses


@router.post("/addresses", response_model=AddressOut)
async def create_address(
    payload: AddressIn, set_default: bool = False, user: dict = Depends(get_current_user_required)
):
    try:
        return await service.create_address(user, payload, set_default)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except CustomerAccountAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/addresses", response_model=AddressOut)
async def update_address(
    payload: AddressIn,
    address_id: str = Query(..., alias="addressId"),
    set_default: bool = False,
    user: dict = Depends(get_current_user_required),
):
    try:
        return await service.update_address(user, address_id, payload, set_default)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except CustomerAccountAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.delete("/addresses")
async def delete_address(address_id: str = Query(..., alias="addressId"), user: dict = Depends(get_current_user_required)):
    try:
        await service.delete_address(user, address_id)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except CustomerAccountAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return {"ok": True}


# Exposed so shopify_integration.router can attach buyer identity to guest/
# logged-in carts without shopify_integration needing to duplicate any auth
# logic — it only ever receives an *optional* user dict, never a raw token.
__all__ = ["router", "get_current_user_optional", "get_current_user_required"]
