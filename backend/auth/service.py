"""Business logic for Shopify Customer Account authentication + our own
backend-issued session. This is the single place that:
  - mints/refreshes/revokes Now Kart's own session tokens
  - holds encrypted custody of the real Shopify customer tokens
  - talks to the Customer Account GraphQL API for profile/orders/addresses
The Expo app never sees a real Shopify token — only our own session pair.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId

from shopify_integration.cache import TTLCache

from . import customer_account_client as cac
from . import security
from .config import settings
from .customer_account_client import CustomerAccountAPIError
from .db import refresh_tokens_collection, users_collection
from .schemas import AddressIn, AddressOut, OrderDetailOut, OrderFulfillmentOut, OrderLineItemOut, OrderSummaryOut, ProfileOut, SessionOut, UserOut

logger = logging.getLogger(__name__)

_state_cache = TTLCache()
_STATE_TTL_SECONDS = 600


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _redirect_uri_for(platform: str, origin: Optional[str]) -> str:
    if platform == "web":
        # No "web" Customer Account API client is registered for Now Kart —
        # only the native mobile client (fixed, pre-registered redirect_uri)
        # exists today. Trusting a caller-supplied `origin` here would let a
        # request build a Shopify authorize URL that redirects the resulting
        # auth code to an attacker-controlled origin. Reject explicitly
        # rather than ever constructing a redirect_uri from client input.
        raise AuthError("Web sign-in is not available yet. Please use the Now Kart mobile app.", 400)
    return settings.mobile_redirect_uri


async def build_authorize_url(code_challenge: str, platform: str, origin: Optional[str]) -> dict[str, Any]:
    redirect_uri = _redirect_uri_for(platform, origin)
    state = security.generate_state()
    _state_cache.set(state, redirect_uri, _STATE_TTL_SECONDS)
    url = await cac.build_authorize_url(redirect_uri, state, code_challenge)
    return {"authorizeUrl": url, "state": state, "redirectUri": redirect_uri}


def _user_out(user: dict[str, Any]) -> UserOut:
    return UserOut(
        id=str(user["_id"]), email=user.get("email"), firstName=user.get("firstName"), lastName=user.get("lastName")
    )


async def _upsert_user_from_shopify(shopify_customer: dict[str, Any], shopify_tokens: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    email = (shopify_customer.get("emailAddress") or {}).get("emailAddress")
    expires_at = now.timestamp() + shopify_tokens.get("expires_in", 3600)
    doc = {
        "shopifyCustomerId": shopify_customer["id"],
        "email": email,
        "firstName": shopify_customer.get("firstName"),
        "lastName": shopify_customer.get("lastName"),
        "shopifyAccessTokenEnc": security.encrypt_secret(shopify_tokens["access_token"]),
        "shopifyRefreshTokenEnc": security.encrypt_secret(shopify_tokens["refresh_token"]),
        "shopifyTokenExpiresAt": expires_at,
        "updatedAt": now,
    }
    user = await users_collection.find_one_and_update(
        {"shopifyCustomerId": shopify_customer["id"]},
        {"$set": doc, "$setOnInsert": {"createdAt": now}},
        upsert=True,
        return_document=True,
    )
    return user


async def _issue_session(user: dict[str, Any]) -> SessionOut:
    user_id = str(user["_id"])
    access_token = security.create_access_token(user_id)
    refresh_token = security.generate_refresh_token()
    now = datetime.now(timezone.utc)
    await refresh_tokens_collection.insert_one(
        {
            "userId": user_id,
            "tokenHash": security.hash_refresh_token(refresh_token),
            "createdAt": now,
            "expiresAt": now.timestamp() + settings.refresh_token_expire_days * 86400,
            "revoked": False,
        }
    )
    return SessionOut(
        accessToken=access_token,
        refreshToken=refresh_token,
        expiresIn=settings.access_token_expire_minutes * 60,
        user=_user_out(user),
    )


async def exchange_code(code: str, state: str, code_verifier: str, redirect_uri: str) -> SessionOut:
    # Consume (pop) the state on first use — a state value must never be
    # exchangeable twice, otherwise a leaked/logged authorize URL could be
    # replayed within the TTL window.
    cached_redirect_uri = _state_cache.pop(state)
    if not cached_redirect_uri:
        raise AuthError("This sign-in request has expired. Please try again.", 400)
    if cached_redirect_uri != redirect_uri:
        raise AuthError("Sign-in request could not be verified. Please try again.", 400)

    shopify_tokens = await cac.exchange_code(code, redirect_uri, code_verifier)
    me_data = await cac.customer_graphql(shopify_tokens["access_token"], cac.ME_QUERY)
    customer = me_data.get("customer")
    if not customer:
        raise AuthError("Could not retrieve your account details from Shopify.", 502)

    user = await _upsert_user_from_shopify(customer, shopify_tokens)
    return await _issue_session(user)


async def refresh_session(refresh_token: str) -> SessionOut:
    token_hash = security.hash_refresh_token(refresh_token)
    record = await refresh_tokens_collection.find_one({"tokenHash": token_hash})
    if not record:
        raise AuthError("Your session has expired. Please sign in again.", 401)

    if record["revoked"]:
        # Reuse of an already-rotated refresh token. This is expected to be
        # rare now that the client single-flights its refresh calls, but if
        # it ever happens (stolen/replayed token, or a client bug) treat it
        # as a signal of compromise: revoke every other session for this
        # user too, forcing a fresh sign-in everywhere rather than trusting
        # a token that has already been used once.
        await refresh_tokens_collection.update_many(
            {"userId": record["userId"], "revoked": False}, {"$set": {"revoked": True}}
        )
        raise AuthError("Your session has expired. Please sign in again.", 401)

    if record["expiresAt"] < datetime.now(timezone.utc).timestamp():
        raise AuthError("Your session has expired. Please sign in again.", 401)

    user = await users_collection.find_one({"_id": ObjectId(record["userId"])})
    if not user:
        raise AuthError("Account not found.", 404)

    await refresh_tokens_collection.update_one({"_id": record["_id"]}, {"$set": {"revoked": True}})
    return await _issue_session(user)


async def logout(refresh_token: str) -> None:
    token_hash = security.hash_refresh_token(refresh_token)
    await refresh_tokens_collection.update_one({"tokenHash": token_hash}, {"$set": {"revoked": True}})


async def get_user_by_id(user_id: str) -> Optional[dict[str, Any]]:
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        return None
    return await users_collection.find_one({"_id": oid})


async def get_valid_shopify_access_token(user: Optional[dict[str, Any]]) -> Optional[str]:
    """Returns a live Shopify Customer Account access token for this user,
    transparently refreshing it server-side if it's expired/near expiry.
    Returns None (never raises) if the user is a guest or refresh fails —
    callers should treat that as "proceed as guest" for cart/checkout ops."""
    if not user:
        return None
    expires_at = user.get("shopifyTokenExpiresAt", 0)
    if expires_at - 60 > datetime.now(timezone.utc).timestamp():
        return security.decrypt_secret(user["shopifyAccessTokenEnc"])

    refresh_token = security.decrypt_secret(user["shopifyRefreshTokenEnc"])
    try:
        tokens = await cac.refresh_access_token(refresh_token)
    except CustomerAccountAPIError:
        return None

    now = datetime.now(timezone.utc)
    await users_collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "shopifyAccessTokenEnc": security.encrypt_secret(tokens["access_token"]),
                "shopifyRefreshTokenEnc": security.encrypt_secret(tokens.get("refresh_token", refresh_token)),
                "shopifyTokenExpiresAt": now.timestamp() + tokens.get("expires_in", 3600),
            }
        },
    )
    return tokens["access_token"]


async def get_profile(user: dict[str, Any]) -> ProfileOut:
    access_token = await get_valid_shopify_access_token(user)
    addresses: list[AddressOut] = []
    orders: list[OrderSummaryOut] = []
    if access_token:
        try:
            data = await cac.customer_graphql(access_token, cac.ME_QUERY)
            customer = data.get("customer") or {}
            default_id = (customer.get("defaultAddress") or {}).get("id")
            for edge in (customer.get("addresses") or {}).get("edges", []):
                node = edge["node"]
                addresses.append(AddressOut(**node, isDefault=(node["id"] == default_id)))
            for edge in (customer.get("orders") or {}).get("edges", []):
                node = edge["node"]
                line_edges = (node.get("lineItems") or {}).get("edges", [])
                item_count = len(line_edges)
                thumbnail_url = None
                for le in line_edges:
                    img = (le["node"].get("image") or {}).get("url")
                    if img:
                        thumbnail_url = img
                        break
                orders.append(
                    OrderSummaryOut(
                        id=node["id"],
                        name=node["name"],
                        processedAt=node["processedAt"],
                        cancelledAt=node.get("cancelledAt"),
                        financialStatus=node.get("financialStatus"),
                        fulfillmentStatus=node.get("fulfillmentStatus"),
                        totalPrice=float(node["totalPrice"]["amount"]),
                        currencyCode=node["totalPrice"]["currencyCode"],
                        itemCount=item_count,
                        thumbnailUrl=thumbnail_url,
                    )
                )
        except CustomerAccountAPIError:
            logger.warning("Could not fetch live Shopify profile data for user %s", user["_id"])
    return ProfileOut(user=_user_out(user), addresses=addresses, orders=orders)


async def get_order_detail(user: dict[str, Any], order_id: str) -> OrderDetailOut:
    """Fetch a single order's full details from the Shopify Customer Account API."""
    access_token = await get_valid_shopify_access_token(user)
    if not access_token:
        raise AuthError("Your session has expired. Please sign in again.", 401)

    data = await cac.customer_graphql(access_token, cac.ORDER_DETAIL_QUERY, {"id": order_id})
    node = data.get("order")
    if not node:
        raise AuthError("Order not found.", 404)

    def _money(m: Any) -> Optional[float]:
        if not m:
            return None
        try:
            return float(m["amount"])
        except Exception:
            return None

    def _currency(m: Any) -> str:
        return (m or {}).get("currencyCode", "GBP")

    # Parse line items
    line_items: list[OrderLineItemOut] = []
    for edge in (node.get("lineItems") or {}).get("edges", []):
        li = edge["node"]
        cur_price_node = li.get("currentTotalPrice") or li.get("totalPrice")
        orig_price_node = li.get("originalTotalPrice") or cur_price_node
        line_items.append(
            OrderLineItemOut(
                id=li["id"],
                title=li["title"],
                quantity=li.get("quantity", 1),
                imageUrl=(li.get("image") or {}).get("url"),
                price=_money(cur_price_node) or 0.0,
                originalPrice=_money(orig_price_node) or 0.0,
                currencyCode=_currency(cur_price_node),
            )
        )

    # Parse fulfillments
    fulfillments: list[OrderFulfillmentOut] = []
    for edge in (node.get("fulfillments") or {}).get("edges", []):
        fu = edge["node"]
        fulfillments.append(
            OrderFulfillmentOut(
                id=fu["id"],
                createdAt=fu.get("createdAt"),
                updatedAt=fu.get("updatedAt"),
            )
        )

    # Parse shipping address
    shipping_address: Optional[AddressOut] = None
    sa_node = node.get("shippingAddress")
    if sa_node:
        shipping_address = AddressOut(
            id=sa_node.get("id", "shipping"),
            firstName=sa_node.get("firstName"),
            lastName=sa_node.get("lastName"),
            address1=sa_node.get("address1"),
            address2=sa_node.get("address2"),
            city=sa_node.get("city"),
            zoneCode=sa_node.get("zoneCode"),
            territoryCode=sa_node.get("territoryCode"),
            zip=sa_node.get("zip"),
            phoneNumber=sa_node.get("phoneNumber"),
        )

    currency = node.get("currencyCode") or _currency(node.get("totalPrice"))
    return OrderDetailOut(
        id=node["id"],
        name=node["name"],
        processedAt=node["processedAt"],
        cancelledAt=node.get("cancelledAt"),
        cancelReason=node.get("cancelReason"),
        financialStatus=node.get("financialStatus"),
        fulfillmentStatus=node.get("fulfillmentStatus"),
        email=node.get("email"),
        totalPrice=_money(node.get("totalPrice")) or 0.0,
        subtotal=_money(node.get("subtotal")),
        totalTax=_money(node.get("totalTax")),
        totalShipping=_money(node.get("totalShipping")),
        totalRefunded=_money(node.get("totalRefunded")),
        currencyCode=currency,
        statusPageUrl=node.get("statusPageUrl"),
        shippingAddress=shipping_address,
        lineItems=line_items,
        fulfillments=fulfillments,
    )


async def create_address(user: dict[str, Any], address: AddressIn, set_default: bool = False) -> AddressOut:
    access_token = await get_valid_shopify_access_token(user)
    if not access_token:
        raise AuthError("Your session has expired. Please sign in again.", 401)
    data = await cac.customer_graphql(
        access_token,
        cac.ADDRESS_CREATE_MUTATION,
        {"address": address.model_dump(exclude_none=True), "defaultAddress": set_default},
    )
    payload = data["customerAddressCreate"]
    if payload.get("userErrors"):
        raise AuthError(payload["userErrors"][0]["message"], 400)
    return AddressOut(**payload["customerAddress"], isDefault=set_default)


async def update_address(
    user: dict[str, Any], address_id: str, address: AddressIn, set_default: bool = False
) -> AddressOut:
    access_token = await get_valid_shopify_access_token(user)
    if not access_token:
        raise AuthError("Your session has expired. Please sign in again.", 401)
    data = await cac.customer_graphql(
        access_token,
        cac.ADDRESS_UPDATE_MUTATION,
        {"addressId": address_id, "address": address.model_dump(exclude_none=True), "defaultAddress": set_default},
    )
    payload = data["customerAddressUpdate"]
    if payload.get("userErrors"):
        raise AuthError(payload["userErrors"][0]["message"], 400)
    return AddressOut(**payload["customerAddress"], isDefault=set_default)


async def delete_address(user: dict[str, Any], address_id: str) -> None:
    access_token = await get_valid_shopify_access_token(user)
    if not access_token:
        raise AuthError("Your session has expired. Please sign in again.", 401)
    data = await cac.customer_graphql(access_token, cac.ADDRESS_DELETE_MUTATION, {"addressId": address_id})
    payload = data["customerAddressDelete"]
    if payload.get("userErrors"):
        raise AuthError(payload["userErrors"][0]["message"], 400)
