"""
Webhooks module MongoDB collections.
"""
import os

from motor.motor_asyncio import AsyncIOMotorClient

_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
_db = _client[os.environ["DB_NAME"]]

webhook_events_collection = _db["webhook_events"]


async def ensure_webhook_indexes() -> None:
    """
    Create all indexes for the webhooks module.
    Called once on application startup from server.py.

      shopifyWebhookId (unique)        — idempotency: never re-process the same webhook
      processed + createdAt            — retry worker queries (future background task)
      shopifyOrderId                   — correlation with delivery jobs
    """
    await webhook_events_collection.create_index("shopifyWebhookId", unique=True)
    await webhook_events_collection.create_index([("processed", 1), ("createdAt", -1)])
    await webhook_events_collection.create_index("shopifyOrderId")
