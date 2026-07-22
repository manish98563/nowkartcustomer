import os


class AuthSettings:
    """Environment-driven settings for Shopify Customer Account API auth + our
    own backend-issued session tokens. Loaded once at import time."""

    def __init__(self) -> None:
        self.customer_account_client_id: str = os.environ["SHOPIFY_CUSTOMER_ACCOUNT_CLIENT_ID"]
        self.mobile_redirect_uri: str = os.environ["SHOPIFY_CUSTOMER_ACCOUNT_MOBILE_REDIRECT_URI"]
        self.shop_id: str = os.environ["SHOPIFY_SHOP_ID"]
        self.shop_domain: str = os.environ["SHOPIFY_STORE_DOMAIN"]

        self.jwt_secret_key: str = os.environ["JWT_SECRET_KEY"]
        self.jwt_algorithm: str = os.environ.get("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes: int = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
        self.refresh_token_expire_days: int = int(os.environ.get("SESSION_REFRESH_TOKEN_EXPIRE_DAYS", "30"))

        self.token_encryption_key: str = os.environ["TOKEN_ENCRYPTION_KEY"]


settings = AuthSettings()
