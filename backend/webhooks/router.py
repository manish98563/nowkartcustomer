"""
Shopify webhook router.

POST /api/webhooks/shopify  — receives all Shopify webhook events.

SECURITY:
  • X-Shopify-Hmac-Sha256 signature verified against SHOPIFY_WEBHOOK_SECRET.
  • Returns 401 on invalid signature (Shopify does not retry 4xx responses).
  • Idempotent: X-Shopify-Webhook-Id is the dedup key; duplicates are
    acknowledged with 200 without re-processing.

RELIABILITY:
  • Always returns 200 for valid, processable webhooks.
  • If business logic raises, the error is logged and stored in
    webhook_events.processingError — the 200 still goes back to Shopify
    so Shopify does not retry a hard processing failure.
  • The raw request body is read before JSON parsing so it can be passed
    to the HMAC verifier (JSON re-serialisation would change byte order).

REGISTERING WEBHOOKS IN SHOPIFY:
  Shopify Admin → Settings → Notifications → Webhooks
    URL:    https://<your-domain>/api/webhooks/shopify
    Format: JSON
  Register:
    - orders/paid
    - orders/cancelled
  Copy the "Signing secret" into SHOPIFY_WEBHOOK_SECRET in backend/.env.
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from . import service
from .db import webhook_events_collection
from .verification import verify_shopify_webhook

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/shopify")
async def shopify_webhook(
    request: Request,
    x_shopify_topic: Optional[str] = Header(default=None),
    x_shopify_webhook_id: Optional[str] = Header(default=None),
    x_shopify_hmac_sha256: Optional[str] = Header(default=None),
    x_shopify_shop_domain: Optional[str] = Header(default=None),
):
    """
    Receives Shopify webhook events.
    Supported topics: orders/paid, orders/cancelled.

    Steps:
      1. Read raw body (needed for HMAC before JSON parsing)
      2. Verify HMAC-SHA256 signature
      3. Parse JSON
      4. Idempotency check via X-Shopify-Webhook-Id
      5. Record event in webhook_events
      6. Route to handler
      7. Return 200
    """
    # ── 1. Read raw body ─────────────────────────────────────────────────────
    body = await request.body()

    # ── 2. HMAC verification ──────────────────────────────────────────────────
    if not verify_shopify_webhook(body, x_shopify_hmac_sha256 or ""):
        logger.warning(
            "Invalid webhook signature from shop=%s topic=%s",
            x_shopify_shop_domain, x_shopify_topic,
        )
        # 401 — Shopify does not retry on 4xx
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    # ── 3. Parse JSON ─────────────────────────────────────────────────────────
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Could not parse webhook body (topic=%s): %s", x_shopify_topic, exc)
        # Return 200 — malformed payload cannot be fixed by Shopify retrying
        return JSONResponse(status_code=200, content={"status": "error", "detail": "Malformed JSON payload."})

    topic      = x_shopify_topic or "unknown"
    order_id   = str(payload.get("id", "unknown"))
    webhook_id = x_shopify_webhook_id or f"no-id-{topic}-{order_id}"

    logger.info(
        "Shopify webhook received: topic=%s webhook_id=%s order_id=%s shop=%s",
        topic, webhook_id, order_id, x_shopify_shop_domain,
    )

    # ── 4. Idempotency check ──────────────────────────────────────────────────
    existing = await webhook_events_collection.find_one({"shopifyWebhookId": webhook_id})
    if existing:
        if existing.get("processed"):
            logger.info("Duplicate webhook %s (already processed) — acknowledging.", webhook_id)
            return JSONResponse(
                status_code=200,
                content={"status": "duplicate", "webhookId": webhook_id},
            )
        # Exists but not yet processed — likely a concurrent duplicate delivery.
        # Acknowledge without racing.
        logger.info("Webhook %s already queued (not yet processed) — acknowledging.", webhook_id)
        return JSONResponse(
            status_code=200,
            content={"status": "processing", "webhookId": webhook_id},
        )

    # ── 5. Record event (audit + idempotency) ─────────────────────────────────
    shopify_order_gid = f"gid://shopify/Order/{order_id}"
    await service.record_webhook_event(
        topic=topic,
        shopify_order_id=shopify_order_gid,
        webhook_id=webhook_id,
        payload=payload,
    )

    # ── 6. Process ────────────────────────────────────────────────────────────
    # Return 200 even on processing errors — the error is stored in
    # webhook_events.processingError for admin review.
    try:
        result = await service.process_webhook(topic, webhook_id, payload)
        return JSONResponse(status_code=200, content={"status": "ok", "result": result})
    except Exception as exc:
        logger.exception(
            "Unhandled error processing webhook %s (topic=%s): %s", webhook_id, topic, exc
        )
        return JSONResponse(
            status_code=200,
            content={
                "status": "error",
                "detail": "Internal processing error. Check webhook_events collection.",
                "webhookId": webhook_id,
            },
        )
