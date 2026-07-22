"""Business logic orchestrating the Shopify GraphQL client, queries, mappers
and cache. This is the single place the FastAPI router talks to."""
import logging
from typing import Any, Optional

from .cache import cache
from .client import ShopifyAPIError, shopify_client
from .collection_groups import CATEGORY_GROUPS, RAIL_COLLECTIONS
from .config import settings
from .mappers import map_cart, map_collection, map_product
from .queries import (
    CART_ATTRIBUTES_UPDATE_MUTATION,
    CART_BUYER_IDENTITY_UPDATE_MUTATION,
    CART_CREATE_MUTATION,
    CART_GET_QUERY,
    CART_LINES_ADD_MUTATION,
    CART_LINES_REMOVE_MUTATION,
    CART_LINES_UPDATE_MUTATION,
    COLLECTION_PRODUCTS_QUERY,
    COLLECTIONS_QUERY,
    PRODUCT_BY_HANDLE_QUERY,
    SEARCH_PRODUCTS_QUERY,
    SHOP_PRODUCTS_QUERY,
)
from .schemas import CartOut, CategoryGroupOut, CategoryOut, HomeSectionsOut, ProductOut, ProductRailOut

logger = logging.getLogger(__name__)


class ProductNotFoundError(Exception):
    pass


async def _get_all_collections_raw(buyer_ip: Optional[str] = None) -> list[dict[str, Any]]:
    cache_key = "collections:all"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = await shopify_client.execute(COLLECTIONS_QUERY, {"first": 50}, buyer_ip)
    nodes = data.get("collections", {}).get("nodes", [])
    cache.set(cache_key, nodes, settings.cache_ttl_seconds)
    return nodes


async def get_category_groups(buyer_ip: Optional[str] = None) -> list[CategoryGroupOut]:
    collections_raw = await _get_all_collections_raw(buyer_ip)
    by_handle = {c["handle"]: c for c in collections_raw}

    groups: list[CategoryGroupOut] = []
    for group_title, candidate_handles in CATEGORY_GROUPS.items():
        matched = [by_handle[h] for h in candidate_handles if h in by_handle]
        if not matched:
            continue
        categories: list[CategoryOut] = [map_collection(c, group_title) for c in matched]
        groups.append(CategoryGroupOut(groupTitle=group_title, categories=categories))
    return groups


async def _fetch_collection_products(handle: str, first: int, buyer_ip: Optional[str]) -> Optional[dict[str, Any]]:
    data = await shopify_client.execute(
        COLLECTION_PRODUCTS_QUERY,
        {"handle": handle, "first": first, "sortKey": "COLLECTION_DEFAULT", "reverse": False},
        buyer_ip,
    )
    return data.get("collection")


async def get_home_rails(buyer_ip: Optional[str] = None) -> list[ProductRailOut]:
    collections_raw = await _get_all_collections_raw(buyer_ip)
    by_handle = {c["handle"] for c in collections_raw}

    rails: list[ProductRailOut] = []
    fallback_sort = {"Best Sellers": ("BEST_SELLING", False), "New Arrivals": ("CREATED_AT", True)}

    for rail_title, candidate_handles in RAIL_COLLECTIONS.items():
        matched_handle = next((h for h in candidate_handles if h in by_handle), None)
        cache_key = f"rail:{rail_title}:{matched_handle or 'sitewide'}"
        cached = cache.get(cache_key)
        if cached is not None:
            rails.append(cached)
            continue

        products: list[ProductOut] = []
        if matched_handle:
            collection = await _fetch_collection_products(matched_handle, 12, buyer_ip)
            if collection:
                products = [
                    map_product(p, category_handle=matched_handle, category_title=collection.get("title"))
                    for p in collection.get("products", {}).get("nodes", [])
                ]
        if not products:
            sort_key, reverse = fallback_sort.get(rail_title, ("BEST_SELLING", False))
            data = await shopify_client.execute(
                SHOP_PRODUCTS_QUERY, {"first": 12, "sortKey": sort_key, "reverse": reverse}, buyer_ip
            )
            products = [map_product(p) for p in data.get("products", {}).get("nodes", [])]

        if not products:
            continue

        rail = ProductRailOut(title=rail_title, handle=matched_handle, products=products)
        cache.set(cache_key, rail, settings.cache_ttl_seconds)
        rails.append(rail)

    return rails


async def get_home_sections(buyer_ip: Optional[str] = None) -> HomeSectionsOut:
    category_groups = await get_category_groups(buyer_ip)
    rails = await get_home_rails(buyer_ip)
    return HomeSectionsOut(categoryGroups=category_groups, rails=rails)


async def get_collection_products(handle: str, first: int = 24, buyer_ip: Optional[str] = None) -> Optional[dict[str, Any]]:
    cache_key = f"collection_products:{handle}:{first}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    collection = await _fetch_collection_products(handle, first, buyer_ip)
    if not collection:
        return None

    result = {
        "collection": map_collection(collection),
        "products": [
            map_product(p, category_handle=handle, category_title=collection.get("title"))
            for p in collection.get("products", {}).get("nodes", [])
        ],
    }
    cache.set(cache_key, result, settings.cache_ttl_seconds)
    return result


async def get_product_by_handle(handle: str, buyer_ip: Optional[str] = None) -> Optional[ProductOut]:
    cache_key = f"product:{handle}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = await shopify_client.execute(PRODUCT_BY_HANDLE_QUERY, {"handle": handle}, buyer_ip)
    node = data.get("product")
    if not node:
        return None

    product = map_product(node)
    cache.set(cache_key, product, settings.cache_ttl_seconds)
    return product


async def search_products(query: str, first: int = 20, buyer_ip: Optional[str] = None) -> list[ProductOut]:
    if not query.strip():
        return []
    shopify_query = f"title:*{query.strip()}* OR tag:*{query.strip()}*"
    data = await shopify_client.execute(SEARCH_PRODUCTS_QUERY, {"query": shopify_query, "first": first}, buyer_ip)
    return [map_product(p) for p in data.get("products", {}).get("nodes", [])]


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

def _raise_on_user_errors(payload: dict[str, Any], mutation_key: str) -> None:
    user_errors = payload.get(mutation_key, {}).get("userErrors") or []
    if user_errors:
        raise ShopifyAPIError(user_errors[0].get("message", "Cart operation failed."), 400)


async def create_cart(variant_id: Optional[str], quantity: int, buyer_ip: Optional[str] = None) -> CartOut:
    cart_input: dict[str, Any] = {}
    if variant_id:
        cart_input["lines"] = [{"merchandiseId": variant_id, "quantity": quantity}]

    data = await shopify_client.execute(CART_CREATE_MUTATION, {"input": cart_input}, buyer_ip)
    _raise_on_user_errors(data, "cartCreate")
    return map_cart(data["cartCreate"]["cart"])


async def get_cart(cart_id: str, buyer_ip: Optional[str] = None) -> Optional[CartOut]:
    data = await shopify_client.execute(CART_GET_QUERY, {"cartId": cart_id}, buyer_ip)
    node = data.get("cart")
    return map_cart(node) if node else None


async def add_cart_line(cart_id: str, variant_id: str, quantity: int, buyer_ip: Optional[str] = None) -> CartOut:
    lines = [{"merchandiseId": variant_id, "quantity": quantity}]
    data = await shopify_client.execute(CART_LINES_ADD_MUTATION, {"cartId": cart_id, "lines": lines}, buyer_ip)
    _raise_on_user_errors(data, "cartLinesAdd")
    return map_cart(data["cartLinesAdd"]["cart"])


async def update_cart_line(cart_id: str, line_id: str, quantity: int, buyer_ip: Optional[str] = None) -> CartOut:
    lines = [{"id": line_id, "quantity": quantity}]
    data = await shopify_client.execute(CART_LINES_UPDATE_MUTATION, {"cartId": cart_id, "lines": lines}, buyer_ip)
    _raise_on_user_errors(data, "cartLinesUpdate")
    return map_cart(data["cartLinesUpdate"]["cart"])


async def remove_cart_line(cart_id: str, line_id: str, buyer_ip: Optional[str] = None) -> CartOut:
    data = await shopify_client.execute(
        CART_LINES_REMOVE_MUTATION, {"cartId": cart_id, "lineIds": [line_id]}, buyer_ip
    )
    _raise_on_user_errors(data, "cartLinesRemove")
    return map_cart(data["cartLinesRemove"]["cart"])


async def update_cart_note(cart_id: str, note: str, buyer_ip: Optional[str] = None) -> None:
    """Attach a delivery note to the cart as a custom attribute visible in Shopify Admin."""
    attributes = [{"key": "delivery_note", "value": note}]
    data = await shopify_client.execute(
        CART_ATTRIBUTES_UPDATE_MUTATION, {"cartId": cart_id, "attributes": attributes}, buyer_ip
    )
    user_errors = (data.get("cartAttributesUpdate") or {}).get("userErrors") or []
    if user_errors:
        logger.warning("cartAttributesUpdate userErrors: %s", user_errors)


# ---------------------------------------------------------------------------
# Checkout foundation: buyer identity attachment + cart validation.
# No payment processing here \u2014 this only prepares the cart/checkoutUrl so a
# future iteration can hand off to Shopify Checkout Sheet Kit / hosted
# checkout. `customer_access_token` (if any) is always resolved server-side
# by auth.service from the caller's session \u2014 it never comes from the app.
# ---------------------------------------------------------------------------

async def attach_buyer_identity(
    cart_id: str,
    customer_access_token: str,
    buyer_ip: Optional[str] = None,
    delivery_address: Optional[dict] = None,
) -> Optional[CartOut]:
    """Update the cart's buyer identity. Optionally includes a delivery address
    preference so Shopify Checkout pre-populates the shipping address field."""
    delivery_prefs = None
    if delivery_address:
        # Build MailingAddressInput from the address fields we have.
        # countryCode is a CountryCode enum in Shopify; pass ISO 3166-1 alpha-2 string.
        mailing: dict = {}
        for src, dst in [
            ("firstName", "firstName"),
            ("lastName", "lastName"),
            ("address1", "address1"),
            ("address2", "address2"),
            ("city", "city"),
            ("zip", "zip"),
        ]:
            if delivery_address.get(src):
                mailing[dst] = delivery_address[src]
        if delivery_address.get("territoryCode"):
            mailing["countryCode"] = delivery_address["territoryCode"]
        if delivery_address.get("phone"):
            mailing["phone"] = delivery_address["phone"]
        if mailing:
            delivery_prefs = [{"deliveryAddress": mailing}]

    data = await shopify_client.execute(
        CART_BUYER_IDENTITY_UPDATE_MUTATION,
        {
            "cartId": cart_id,
            "customerAccessToken": customer_access_token,
            "deliveryAddressPreferences": delivery_prefs,
        },
        buyer_ip,
    )
    payload = data.get("cartBuyerIdentityUpdate", {})
    if payload.get("userErrors"):
        logger.warning("cartBuyerIdentityUpdate userErrors: %s", payload["userErrors"])
        return None
    cart_node = payload.get("cart")
    return map_cart(cart_node) if cart_node else None


def _validate_cart_lines(cart: CartOut) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for line in cart.lines:
        if not line.availableForSale:
            issues.append(
                {"lineId": line.id, "title": line.title, "message": f'"{line.title}" is currently out of stock.'}
            )
        elif (
            line.quantityAvailable is not None
            and line.quantityAvailable > 0
            and line.quantity > line.quantityAvailable
        ):
            # Only a real blocker when Shopify reports a positive-but-insufficient
            # stock count. A variant with quantityAvailable == 0 that is still
            # availableForSale means the merchant enabled "continue selling when
            # out of stock" — Shopify will still fulfill/backorder it, so that
            # is NOT a checkout-blocking issue.
            issues.append(
                {
                    "lineId": line.id,
                    "title": line.title,
                    "message": f'Only {line.quantityAvailable} left of "{line.title}" \u2014 please reduce the quantity.',
                }
            )
    return issues


async def prepare_checkout(
    cart_id: str,
    customer_access_token: Optional[str] = None,
    buyer_ip: Optional[str] = None,
    delivery_address: Optional[dict] = None,
) -> Optional[dict[str, Any]]:
    """Validates a cart's lines against live Shopify stock and, if the caller
    is a signed-in customer, attaches their Shopify buyer identity (+ optional
    delivery address preference) so the resulting checkoutUrl opens with the
    shipping address pre-populated. Returns None if the cart no longer exists.
    Payment is never initiated here."""
    cart = await get_cart(cart_id, buyer_ip)
    if cart is None:
        return None

    if customer_access_token:
        updated = await attach_buyer_identity(
            cart_id, customer_access_token, buyer_ip, delivery_address
        )
        if updated is not None:
            cart = updated

    issues = _validate_cart_lines(cart)
    return {
        "cart": cart,
        "isValid": len(issues) == 0 and len(cart.lines) > 0,
        "issues": issues,
        "checkoutUrl": cart.checkoutUrl,
    }
