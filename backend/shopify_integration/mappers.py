"""Transform raw Shopify Storefront API GraphQL JSON into our Pydantic schemas."""
from typing import Any, Optional

from .schemas import CartLineOut, CartOut, CategoryOut, ProductOut, ProductVariantOut, SelectedOption


def _money(money: Optional[dict[str, Any]]) -> Optional[float]:
    if not money:
        return None
    return float(money["amount"])


def map_variant(node: dict[str, Any]) -> ProductVariantOut:
    compare_at = _money(node.get("compareAtPrice"))
    return ProductVariantOut(
        id=node["id"],
        title=node["title"],
        price=_money(node["price"]) or 0.0,
        compareAtPrice=compare_at,
        currencyCode=node["price"]["currencyCode"],
        availableForSale=node.get("availableForSale", True),
        quantityAvailable=node.get("quantityAvailable"),
        selectedOptions=[SelectedOption(**o) for o in node.get("selectedOptions", [])],
        imageUrl=(node.get("image") or {}).get("url"),
    )


def map_product(
    node: dict[str, Any],
    category_handle: Optional[str] = None,
    category_title: Optional[str] = None,
) -> ProductOut:
    price = _money(node["priceRange"]["minVariantPrice"]) or 0.0
    compare_at = _money((node.get("compareAtPriceRange") or {}).get("minVariantPrice"))
    if compare_at is not None and compare_at <= price:
        compare_at = None

    featured_image = (node.get("featuredImage") or {}).get("url")
    images = [img["url"] for img in (node.get("images") or {}).get("nodes", [])]
    if not featured_image and images:
        featured_image = images[0]

    variants = [map_variant(v) for v in (node.get("variants") or {}).get("nodes", [])]

    return ProductOut(
        id=node["id"],
        handle=node["handle"],
        title=node["title"],
        description=node.get("description") or "",
        price=price,
        compareAtPrice=compare_at,
        currencyCode=node["priceRange"]["minVariantPrice"]["currencyCode"],
        imageUrl=featured_image,
        images=images,
        categoryHandle=category_handle or None,
        categoryTitle=category_title or node.get("productType") or None,
        vendor=node.get("vendor"),
        inStock=node.get("availableForSale", True),
        variants=variants,
    )


def map_collection(node: dict[str, Any], group_title: str = "") -> CategoryOut:
    return CategoryOut(
        id=node["id"],
        handle=node["handle"],
        title=node["title"],
        description=node.get("description") or None,
        imageUrl=(node.get("image") or {}).get("url"),
        groupTitle=group_title,
    )


def map_cart_line(node: dict[str, Any]) -> CartLineOut:
    merchandise = node["merchandise"]
    variant_title = merchandise.get("title")
    if variant_title in (None, "Default Title"):
        variant_title = None
    return CartLineOut(
        id=node["id"],
        quantity=node["quantity"],
        variantId=merchandise["id"],
        productHandle=merchandise["product"]["handle"],
        title=merchandise["product"]["title"],
        variantTitle=variant_title,
        imageUrl=(merchandise.get("image") or {}).get("url"),
        price=_money(merchandise["price"]) or 0.0,
        currencyCode=merchandise["price"]["currencyCode"],
        lineTotal=_money(node["cost"]["totalAmount"]) or 0.0,
        availableForSale=merchandise.get("availableForSale", True),
        quantityAvailable=merchandise.get("quantityAvailable"),
    )


def map_cart(node: dict[str, Any]) -> CartOut:
    cost = node["cost"]
    tax_node = cost.get("totalTaxAmount")
    return CartOut(
        id=node["id"],
        checkoutUrl=node["checkoutUrl"],
        totalQuantity=node.get("totalQuantity", 0),
        subtotal=_money(cost["subtotalAmount"]) or 0.0,
        total=_money(cost["totalAmount"]) or 0.0,
        totalTax=_money(tax_node) if tax_node else 0.0,
        currencyCode=cost["totalAmount"]["currencyCode"],
        lines=[map_cart_line(line) for line in node["lines"]["nodes"]],
    )
