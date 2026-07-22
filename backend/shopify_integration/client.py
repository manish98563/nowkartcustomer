import logging
from typing import Any, Optional

import httpx

from .config import settings

logger = logging.getLogger(__name__)


class ShopifyAPIError(Exception):
    """Raised when the Shopify Storefront API returns GraphQL or transport errors."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ShopifyGraphQLClient:
    """Thin, async GraphQL transport for the Shopify Storefront API.

    Uses the PRIVATE Storefront API token (server-side only, per Shopify's
    Headless-channel token model) via the `Shopify-Storefront-Private-Token`
    header — this token is never sent to or exposed by the frontend.
    """

    def __init__(self) -> None:
        self._endpoint = settings.graphql_endpoint
        self._timeout = httpx.Timeout(15.0)

    async def execute(
        self,
        query: str,
        variables: Optional[dict[str, Any]] = None,
        buyer_ip: Optional[str] = None,
    ) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "Shopify-Storefront-Private-Token": settings.storefront_token,
        }
        if buyer_ip:
            headers["Shopify-Storefront-Buyer-IP"] = buyer_ip

        payload = {"query": query, "variables": variables or {}}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http_client:
                response = await http_client.post(self._endpoint, json=payload, headers=headers)
        except httpx.RequestError as exc:
            logger.error("Shopify Storefront API request failed: %s", exc)
            raise ShopifyAPIError("Unable to reach Shopify. Please try again shortly.", 503) from exc

        if response.status_code == 401:
            raise ShopifyAPIError("Shopify rejected the Storefront API token.", 401)
        if response.status_code == 429:
            raise ShopifyAPIError("Shopify rate limit reached. Please try again shortly.", 429)
        if response.status_code >= 400:
            logger.error("Shopify Storefront API HTTP %s: %s", response.status_code, response.text)
            raise ShopifyAPIError("Shopify Storefront API returned an error.", 502)

        body = response.json()
        if "errors" in body and body["errors"]:
            logger.error("Shopify Storefront API GraphQL errors: %s", body["errors"])
            raise ShopifyAPIError(body["errors"][0].get("message", "Shopify GraphQL error"), 502)

        return body.get("data", {})


shopify_client = ShopifyGraphQLClient()
