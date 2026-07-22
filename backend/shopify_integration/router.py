import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from auth import service as auth_service
from auth.dependencies import get_current_user_optional

from . import service
from .client import ShopifyAPIError
from .schemas import (
    AddCartLineRequest,
    CartNoteUpdateRequest,
    CartOut,
    CategoryGroupOut,
    CheckoutPrepareOut,
    CreateCartRequest,
    HomeSectionsOut,
    PrepareCheckoutRequest,
    ProductOut,
    RemoveCartLineRequest,
    UpdateCartLineRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/shopify", tags=["shopify"])


def _buyer_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("/home", response_model=HomeSectionsOut)
async def get_home_sections(request: Request):
    try:
        return await service.get_home_sections(_buyer_ip(request))
    except ShopifyAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/categories", response_model=list[CategoryGroupOut])
async def get_categories(request: Request):
    try:
        return await service.get_category_groups(_buyer_ip(request))
    except ShopifyAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/collections/{handle}/products")
async def get_collection_products(handle: str, request: Request, first: int = Query(24, le=50)):
    try:
        result = await service.get_collection_products(handle, first, _buyer_ip(request))
    except ShopifyAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Collection '{handle}' not found.")
    return result


@router.get("/products/{handle}", response_model=ProductOut)
async def get_product(handle: str, request: Request):
    try:
        product = await service.get_product_by_handle(handle, _buyer_ip(request))
    except ShopifyAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product '{handle}' not found.")
    return product


@router.get("/search", response_model=list[ProductOut])
async def search_products(request: Request, q: str = Query(..., min_length=1), first: int = Query(20, le=50)):
    try:
        return await service.search_products(q, first, _buyer_ip(request))
    except ShopifyAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/cart", response_model=CartOut)
async def create_cart(
    payload: CreateCartRequest, request: Request, user: Optional[dict] = Depends(get_current_user_optional)
):
    try:
        cart = await service.create_cart(payload.variantId, payload.quantity, _buyer_ip(request))
        if user:
            token = await auth_service.get_valid_shopify_access_token(user)
            if token:
                updated = await service.attach_buyer_identity(cart.id, token, _buyer_ip(request))
                if updated is not None:
                    cart = updated
        return cart
    except ShopifyAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/cart", response_model=CartOut)
async def get_cart(cart_id: str, request: Request):
    try:
        cart = await service.get_cart(cart_id, _buyer_ip(request))
    except ShopifyAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found or expired.")
    return cart


@router.post("/cart/lines", response_model=CartOut)
async def add_cart_line(payload: AddCartLineRequest, request: Request):
    try:
        return await service.add_cart_line(payload.cartId, payload.variantId, payload.quantity, _buyer_ip(request))
    except ShopifyAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/cart/lines", response_model=CartOut)
async def update_cart_line(payload: UpdateCartLineRequest, request: Request):
    try:
        return await service.update_cart_line(payload.cartId, payload.lineId, payload.quantity, _buyer_ip(request))
    except ShopifyAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.delete("/cart/lines", response_model=CartOut)
async def remove_cart_line(payload: RemoveCartLineRequest, request: Request):
    try:
        return await service.remove_cart_line(payload.cartId, payload.lineId, _buyer_ip(request))
    except ShopifyAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.put("/cart/note")
async def update_cart_note(payload: CartNoteUpdateRequest, request: Request):
    """Store a delivery instruction note as a Shopify cart attribute (visible in Admin)."""
    try:
        await service.update_cart_note(payload.cartId, payload.note, _buyer_ip(request))
    except ShopifyAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return {"ok": True}


@router.post("/checkout/prepare", response_model=CheckoutPrepareOut)
async def prepare_checkout(
    payload: PrepareCheckoutRequest, request: Request, user: Optional[dict] = Depends(get_current_user_optional)
):
    """Checkout foundation — validates the cart against live Shopify stock,
    attaches the signed-in customer's buyer identity (+ optional delivery
    address preference), and returns the (unpaid) checkoutUrl so the app can
    open Shopify's hosted checkout with the shipping address pre-populated."""
    token = await auth_service.get_valid_shopify_access_token(user) if user else None

    # Build delivery address dict from flat request fields (if provided)
    delivery_address = None
    if any([
        payload.deliveryAddress1, payload.deliveryCity,
        payload.deliveryTerritoryCode, payload.deliveryZip,
    ]):
        delivery_address = {
            "firstName": payload.deliveryFirstName,
            "lastName": payload.deliveryLastName,
            "address1": payload.deliveryAddress1,
            "address2": payload.deliveryAddress2,
            "city": payload.deliveryCity,
            "territoryCode": payload.deliveryTerritoryCode,
            "zip": payload.deliveryZip,
            "phone": payload.deliveryPhone,
        }

    try:
        result = await service.prepare_checkout(
            payload.cartId, token, _buyer_ip(request), delivery_address
        )
    except ShopifyAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="Cart not found or expired.")
    return result
