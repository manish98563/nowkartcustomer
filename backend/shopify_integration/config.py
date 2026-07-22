import os


class ShopifySettings:
    """Environment-driven Shopify Storefront API settings. Loaded once at import time."""

    def __init__(self) -> None:
        self.store_domain: str = os.environ["SHOPIFY_STORE_DOMAIN"]
        self.storefront_token: str = os.environ["SHOPIFY_STOREFRONT_API_TOKEN"]
        self.api_version: str = os.environ["SHOPIFY_STOREFRONT_API_VERSION"]
        self.cache_ttl_seconds: int = int(os.environ.get("SHOPIFY_CACHE_TTL_SECONDS", "90"))

    @property
    def graphql_endpoint(self) -> str:
        return f"https://{self.store_domain}/api/{self.api_version}/graphql.json"


settings = ShopifySettings()
