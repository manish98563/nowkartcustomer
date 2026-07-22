"""
Shopify webhook payload schemas.

IMPORTANT: Shopify webhook payloads use the REST API format with numeric
integer IDs and snake_case field names.  These are DIFFERENT from the
GraphQL GID-based schemas used by the Storefront and Customer Account APIs
elsewhere in this codebase.

Conversion rule:
  Shopify REST order id  450789469
  → GraphQL GID          "gid://shopify/Order/450789469"

All fields are Optional (except `id`) because Shopify's webhook payload
content varies by plan and configuration.
"""
from typing import List, Optional

from pydantic import BaseModel


class ShopifyWebhookCustomer(BaseModel):
    id:         Optional[int] = None
    email:      Optional[str] = None
    first_name: Optional[str] = None
    last_name:  Optional[str] = None


class ShopifyWebhookAddress(BaseModel):
    first_name: Optional[str] = None
    last_name:  Optional[str] = None
    address1:   Optional[str] = None
    address2:   Optional[str] = None
    city:       Optional[str] = None
    province:   Optional[str] = None
    zip:        Optional[str] = None
    country:    Optional[str] = None
    phone:      Optional[str] = None


class ShopifyWebhookLineItem(BaseModel):
    id:            Optional[int] = None
    title:         Optional[str] = None
    quantity:      Optional[int] = 1
    price:         Optional[str] = "0"
    variant_title: Optional[str] = None


class ShopifyOrderWebhookPayload(BaseModel):
    """Covers orders/paid and orders/cancelled topics."""
    id:                 int
    name:               Optional[str] = None
    email:              Optional[str] = None
    note:               Optional[str] = None
    total_price:        Optional[str] = "0"
    currency:           Optional[str] = "GBP"
    financial_status:   Optional[str] = None
    fulfillment_status: Optional[str] = None
    cancelled_at:       Optional[str] = None
    cancel_reason:      Optional[str] = None
    customer:           Optional[ShopifyWebhookCustomer] = None
    shipping_address:   Optional[ShopifyWebhookAddress] = None
    line_items:         Optional[List[ShopifyWebhookLineItem]] = []
