"""
Delivery module MongoDB collections.

Follows the same pattern as auth/db.py — a dedicated Motor client instance
that reads MONGO_URL / DB_NAME from the environment after server.py has
called load_dotenv().  All delivery-module code imports collections from here.
"""
import logging
import os

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
_db = _client[os.environ["DB_NAME"]]

delivery_jobs_collection = _db["delivery_jobs"]
stores_collection = _db["stores"]
parent_orders_collection = _db["parent_orders"]


async def ensure_delivery_indexes() -> None:
    """
    Create all indexes for the delivery module.
    Called once on application startup from server.py.

    Index rationale:
      delivery_jobs:
        (shopifyOrderId, vendorId) unique — multi-vendor: one job per (order, vendor)
          replaces old shopifyOrderId unique index (Iteration 20)
        parentOrderId                    — look up all jobs for a parent order
        status + createdAt               — admin dashboard list queries
        customerId + createdAt           — customer order history correlation
        storeId + status + createdAt     — store-scoped admin views
        assignedRiderId                  — rider's active job lookup

      stores:
        shopifyDomain                    — config lookup
        isDefault                        — fast default-store resolution

      parent_orders:
        shopifyOrderId (unique)          — service-level idempotency guard
    """
    # ── Drop legacy single-field unique index on shopifyOrderId ──────────────
    # Iteration 20: replaced by compound (shopifyOrderId, vendorId) to support
    # multiple delivery jobs per Shopify order (one per vendor).
    try:
        idx_info = await delivery_jobs_collection.index_information()
        if "shopifyOrderId_1" in idx_info:
            await delivery_jobs_collection.drop_index("shopifyOrderId_1")
            logger.info(
                "Dropped legacy delivery_jobs.shopifyOrderId_1 unique index "
                "(replaced by compound shopifyOrderId+vendorId index for multi-vendor support)"
            )
    except Exception as exc:
        logger.warning("Could not inspect/drop legacy shopifyOrderId_1 index: %s", exc)

    # ── delivery_jobs ─────────────────────────────────────────────────────────
    # Compound unique: one delivery job per (Shopify order, NowKart vendor)
    await delivery_jobs_collection.create_index(
        [("shopifyOrderId", 1), ("vendorId", 1)],
        unique=True,
        name="shopifyOrderId_vendorId_unique",
    )
    await delivery_jobs_collection.create_index("parentOrderId")
    await delivery_jobs_collection.create_index([("status", 1), ("createdAt", -1)])
    await delivery_jobs_collection.create_index([("customerId", 1), ("createdAt", -1)])
    await delivery_jobs_collection.create_index(
        [("storeId", 1), ("status", 1), ("createdAt", -1)]
    )
    await delivery_jobs_collection.create_index("assignedRiderId")
    await delivery_jobs_collection.create_index(
        [("vendorId", 1), ("status", 1), ("createdAt", -1)]
    )

    # ── stores ────────────────────────────────────────────────────────────────
    await stores_collection.create_index("shopifyDomain")
    await stores_collection.create_index("isDefault")


async def ensure_parent_order_indexes() -> None:
    """
    Create indexes for the parent_orders collection.
    Called once on application startup from server.py.
    """
    await parent_orders_collection.create_index("shopifyOrderId", unique=True)
    await parent_orders_collection.create_index("shopifyNumericId")
    await parent_orders_collection.create_index([("status", 1), ("createdAt", -1)])
