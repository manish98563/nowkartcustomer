"""Thin async client for Shopify's Customer Account API (OAuth2 + PKCE +
GraphQL). This module is the ONLY place that ever talks to Shopify's
authentication endpoints — the actual customer refresh/access tokens it
receives are handed back to service.py for encrypted storage and are never
returned to the Expo app.
"""
import logging
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from .config import settings

logger = logging.getLogger(__name__)

_discovery_cache: dict[str, Any] = {}
_graphql_endpoint_cache: dict[str, str] = {}

SCOPES = "openid email customer-account-api:full"


class CustomerAccountAPIError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


async def _discovery() -> dict[str, Any]:
    if _discovery_cache:
        return _discovery_cache
    url = f"https://{settings.shop_domain}/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url)
        except httpx.RequestError as exc:
            logger.error("Shopify OIDC discovery unreachable: %s", exc)
            raise CustomerAccountAPIError("Unable to reach Shopify's authentication service. Please try again.", 503)
    if resp.status_code >= 400:
        logger.error("Shopify OIDC discovery failed: %s %s", resp.status_code, resp.text)
        raise CustomerAccountAPIError("Unable to reach Shopify's authentication service. Please try again.", 503)
    _discovery_cache.update(resp.json())
    return _discovery_cache


async def _graphql_endpoint() -> str:
    if "url" in _graphql_endpoint_cache:
        return _graphql_endpoint_cache["url"]
    url = f"https://{settings.shop_domain}/.well-known/customer-account-api"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url)
        except httpx.RequestError as exc:
            logger.error("Shopify Customer Account API discovery unreachable: %s", exc)
            raise CustomerAccountAPIError("Unable to reach your account right now. Please try again.", 503)
    if resp.status_code >= 400:
        logger.error("Shopify Customer Account API discovery failed: %s %s", resp.status_code, resp.text)
        raise CustomerAccountAPIError("Unable to reach your account right now. Please try again.", 503)
    endpoint = resp.json()["graphql_api"]
    _graphql_endpoint_cache["url"] = endpoint
    return endpoint


async def build_authorize_url(redirect_uri: str, state: str, code_challenge: str) -> str:
    discovery = await _discovery()
    params = {
        "client_id": settings.customer_account_client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{discovery['authorization_endpoint']}?{urlencode(params)}"


async def exchange_code(code: str, redirect_uri: str, code_verifier: str) -> dict[str, Any]:
    """Exchanges an authorization code (with its PKCE verifier, generated and
    held in-memory by the mobile app for the duration of this single login
    attempt) for Shopify Customer Account access + refresh tokens. This is
    the only step where those tokens ever exist — they are handed to
    service.py immediately afterward for encrypted storage and are never
    returned to the caller (the app).
    """
    discovery = await _discovery()
    body = {
        "grant_type": "authorization_code",
        "client_id": settings.customer_account_client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                discovery["token_endpoint"], data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
        except httpx.RequestError as exc:
            logger.error("Shopify token exchange unreachable: %s", exc)
            raise CustomerAccountAPIError("Could not complete sign-in. Please try again.", 503)
    if resp.status_code >= 400:
        logger.error("Shopify Customer Account token exchange failed: status=%s", resp.status_code)
        raise CustomerAccountAPIError("Could not complete sign-in. Please try again.", 401)
    return resp.json()


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    discovery = await _discovery()
    body = {
        "grant_type": "refresh_token",
        "client_id": settings.customer_account_client_id,
        "refresh_token": refresh_token,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                discovery["token_endpoint"], data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
        except httpx.RequestError as exc:
            logger.error("Shopify token refresh unreachable: %s", exc)
            raise CustomerAccountAPIError("Your session with Shopify has expired. Please sign in again.", 503)
    if resp.status_code >= 400:
        logger.warning("Shopify Customer Account token refresh failed: status=%s", resp.status_code)
        raise CustomerAccountAPIError("Your session with Shopify has expired. Please sign in again.", 401)
    return resp.json()


ME_QUERY = """
query Me {
  customer {
    id
    firstName
    lastName
    emailAddress { emailAddress }
    defaultAddress { id }
    orders(first: 20, sortKey: PROCESSED_AT, reverse: true) {
      edges {
        node {
          id
          name
          processedAt
          cancelledAt
          financialStatus
          fulfillmentStatus
          totalPrice { amount currencyCode }
          lineItems(first: 4) {
            edges {
              node {
                id
                title
                quantity
                image { url altText }
              }
            }
          }
        }
      }
    }
    addresses(first: 20) {
      edges {
        node {
          id
          firstName
          lastName
          address1
          address2
          city
          zoneCode
          territoryCode
          zip
          phoneNumber
        }
      }
    }
  }
}
"""

ADDRESS_CREATE_MUTATION = """
mutation CreateAddress($address: CustomerAddressInput!, $defaultAddress: Boolean) {
  customerAddressCreate(address: $address, defaultAddress: $defaultAddress) {
    customerAddress { id firstName lastName address1 address2 city zoneCode territoryCode zip phoneNumber }
    userErrors { field message code }
  }
}
"""

ADDRESS_UPDATE_MUTATION = """
mutation UpdateAddress($addressId: ID!, $address: CustomerAddressInput!, $defaultAddress: Boolean) {
  customerAddressUpdate(addressId: $addressId, address: $address, defaultAddress: $defaultAddress) {
    customerAddress { id firstName lastName address1 address2 city zoneCode territoryCode zip phoneNumber }
    userErrors { field message code }
  }
}
"""

ADDRESS_DELETE_MUTATION = """
mutation DeleteAddress($addressId: ID!) {
  customerAddressDelete(addressId: $addressId) {
    deletedAddressId
    userErrors { field message code }
  }
}
"""

ORDER_DETAIL_QUERY = """
query OrderDetail($id: ID!) {
  order(id: $id) {
    id
    name
    processedAt
    cancelledAt
    cancelReason
    financialStatus
    fulfillmentStatus
    email
    currencyCode
    totalPrice { amount currencyCode }
    subtotal { amount currencyCode }
    totalTax { amount currencyCode }
    totalShipping { amount currencyCode }
    totalRefunded { amount currencyCode }
    statusPageUrl
    shippingAddress {
      firstName
      lastName
      address1
      address2
      city
      zoneCode
      territoryCode
      zip
      phoneNumber
    }
    lineItems(first: 50) {
      edges {
        node {
          id
          title
          quantity
          image { url altText }
          currentTotalPrice { amount currencyCode }
          originalTotalPrice { amount currencyCode }
        }
      }
    }
    fulfillments(first: 10) {
      edges {
        node {
          id
          createdAt
          updatedAt
        }
      }
    }
  }
}
"""


async def customer_graphql(access_token: str, query: str, variables: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    endpoint = await _graphql_endpoint()
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                endpoint,
                json={"query": query, "variables": variables or {}},
                headers={"Content-Type": "application/json", "Authorization": access_token},
            )
        except httpx.RequestError as exc:
            logger.error("Customer Account GraphQL unreachable: %s", exc)
            raise CustomerAccountAPIError("Could not reach your account right now. Please try again.", 503)
    if resp.status_code == 401:
        raise CustomerAccountAPIError("Your session has expired. Please sign in again.", 401)
    if resp.status_code >= 400:
        logger.error("Customer Account GraphQL error: status=%s", resp.status_code)
        raise CustomerAccountAPIError("Could not reach your account right now. Please try again.", 502)
    body = resp.json()
    if body.get("errors"):
        logger.error("Customer Account GraphQL errors: %s", body["errors"])
        raise CustomerAccountAPIError(body["errors"][0].get("message", "Account request failed."), 502)
    return body.get("data", {})
