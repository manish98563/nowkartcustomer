"""
Shopify webhook processing service.

Handles the following topics:
  orders/paid       → create a delivery job
  orders/cancelled  → cancel the delivery job (with IN_TRANSIT guard)

All handlers are designed to:
  1. Be idempotent (duplicate webhooks are safe — checked at the router level
     via the unique index on webhook_events.shopifyWebhookId).
  2. Return quickly — no synchronous Google Maps calls or external HTTP.
  3. Record processing state in webhook_events for audit + future retry worker.

ARCHITECTURE NOTE:
  This module imports from delivery.service (one-directional dependency,
  as defined in the architecture document: webhooks/ → delivery/).
  It never imports from auth/, shopify_integration/, or tracking/.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from delivery.service import (
    cancel_delivery_job_by_order_id,
    create_delivery_job_from_order,
)

from .db import webhook_events_collection

logger = logging.getLogger(__name__)


# ─── Webhook event lifecycle ──────────────────────────────────────────────────

async def record_webhook_event(
    topic: str,
    shopify_order_id: str,
    webhook_id: str,
    payload: dict,
) -> None:
    """
    Insert a webhook_events record before processing begins.
    The unique index on shopifyWebhookId ensures this fails gracefully on
    duplicate delivery (we check for the duplicate in the router, so a
    DuplicateKeyError here is a programming error, not a user error).
    """
    now = datetime.now(timezone.utc)
    await webhook_events_collection.insert_one(
        {
            "shopifyTopic":     topic,
            "shopifyOrderId":   shopify_order_id,
            "shopifyWebhookId": webhook_id,
            "payload":          payload,
            "processed":        False,
            "processedAt":      None,
            "processingError":  None,
            "retryCount":       0,
            "createdAt":        now,
        }
    )


async def mark_processed(webhook_id: str, error: Optional[str] = None) -> None:
    """Update the webhook_events record after processing completes or fails."""
    await webhook_events_collection.update_one(
        {"shopifyWebhookId": webhook_id},
        {
            "$set": {
                "processed":       error is None,
                "processedAt":     datetime.now(timezone.utc),
                "processingError": error,
            }
        },
    )


# ─── Topic routing ────────────────────────────────────────────────────────────

async def process_webhook(topic: str, webhook_id: str, payload: dict) -> dict:
    """
    Route a verified, non-duplicate webhook to the appropriate handler.
    Returns a result dict for structured logging.
    Any exception is caught by the router, which marks the event as failed
    and returns 200 to Shopify (never retry a processing failure).
    """
    if topic == "orders/paid":
        return await _handle_order_paid(webhook_id, payload)

    if topic == "orders/cancelled":
        return await _handle_order_cancelled(webhook_id, payload)

    # Unsupported topic — acknowledge and ignore
    logger.info("Webhook topic '%s' is not handled — acknowledged (webhook_id=%s).", topic, webhook_id)
    await mark_processed(webhook_id)
    return {"action": "ignored", "topic": topic}


async def _handle_order_paid(webhook_id: str, payload: dict) -> dict:
    """
    orders/paid → create a delivery job.
    """
    shopify_order_id = f"gid://shopify/Order/{payload.get('id', 'unknown')}"
    try:
        job = await create_delivery_job_from_order(payload)
        await mark_processed(webhook_id)
        logger.info(
            "orders/paid %s processed → delivery job %s created (order=%s)",
            webhook_id, job.id, shopify_order_id,
        )
        return {
            "action":  "delivery_job_created",
            "jobId":   job.id,
            "orderId": shopify_order_id,
            "status":  job.status,
        }
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        logger.error("Error processing orders/paid webhook %s: %s", webhook_id, err)
        await mark_processed(webhook_id, error=err)
        raise


async def _handle_order_cancelled(webhook_id: str, payload: dict) -> dict:
    """
    orders/cancelled → cancel the delivery job if one exists.
    """
    shopify_order_id = f"gid://shopify/Order/{payload.get('id', 'unknown')}"
    cancel_reason = payload.get("cancel_reason") or "Cancelled via Shopify"
    try:
        job = await cancel_delivery_job_by_order_id(shopify_order_id, cancel_reason)
        await mark_processed(webhook_id)
        if job:
            logger.info(
                "orders/cancelled %s processed → job %s updated to status=%s (order=%s)",
                webhook_id, job.id, job.status, shopify_order_id,
            )
            return {
                "action":  "delivery_job_updated",
                "jobId":   job.id,
                "status":  job.status,
                "orderId": shopify_order_id,
            }
        logger.info(
            "orders/cancelled %s processed → no delivery job found for order %s",
            webhook_id, shopify_order_id,
        )
        return {"action": "no_job_found", "orderId": shopify_order_id}
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        logger.error("Error processing orders/cancelled webhook %s: %s", webhook_id, err)
        await mark_processed(webhook_id, error=err)
        raise
