"""
Shopify webhook HMAC-SHA256 signature verification.

Reference: https://shopify.dev/docs/apps/build/webhooks/secure/validate-webhooks

The signature is computed by Shopify as:
  base64( HMAC-SHA256(SHOPIFY_WEBHOOK_SECRET, raw_request_body) )
and sent in the X-Shopify-Hmac-Sha256 header.

DEVELOPMENT MODE:
  If SHOPIFY_WEBHOOK_SECRET is not set (empty string), verification is
  skipped with a warning.  This allows local development and automated
  testing without needing a real Shopify webhook subscription.
  Set the secret before production deployment.
"""
import base64
import hashlib
import hmac
import logging
import os

logger = logging.getLogger(__name__)


def verify_shopify_webhook(body: bytes, signature: str) -> bool:
    """
    Returns True if the signature is valid or if SHOPIFY_WEBHOOK_SECRET
    is not configured (dev mode).
    Returns False if the secret is set but the signature does not match.
    """
    secret = os.environ.get("SHOPIFY_WEBHOOK_SECRET", "").strip()

    if not secret:
        logger.warning(
            "SHOPIFY_WEBHOOK_SECRET is not configured — "
            "skipping webhook signature verification (dev/test mode). "
            "Set this value before production deployment."
        )
        return True   # dev/test: accept all

    if not signature:
        logger.warning("Webhook received without X-Shopify-Hmac-Sha256 header.")
        return False

    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode("utf-8")

    # compare_digest is constant-time — prevents timing side-channel attacks
    return hmac.compare_digest(computed, signature)
