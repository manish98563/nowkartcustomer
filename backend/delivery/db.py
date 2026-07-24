"""
Delivery module MongoDB collections.

Follows the same pattern as auth/db.py — a dedicated Motor client instance
that reads MONGO_URL / DB_NAME from the environment after server.py has
called load_dotenv().  All delivery-module code imports collections from here.
"""
import os

from motor.motor_asyncio import AsyncIOMotorClient

_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
_db = _client[os.environ["DB_NAME"]]

delivery_jobs_collection = _db["delivery_jobs"]
stores_collection = _db["stores"]


async def ensure_delivery_indexes() -> None:
    """
    Create all indexes for the delivery module.
    Called once on application startup from server.py.

    Index rationale:
      delivery_jobs:
        shopifyOrderId (unique)          — webhook idempotency + customer lookup
        status + createdAt               — admin dashboard list queries
        customerId + createdAt           — customer order history correlation
        storeId + status + createdAt     — store-scoped admin views
        assignedRiderId                  — rider's active job lookup (Phase 2)

      stores:
        shopifyDomain                    — config lookup
        isDefault                        — fast default-store resolution
    """
    # delivery_jobs
    await delivery_jobs_collection.create_index("shopifyOrderId", unique=True)
    await delivery_jobs_collection.create_index([("status", 1), ("createdAt", -1)])
    await delivery_jobs_collection.create_index([("customerId", 1), ("createdAt", -1)])
    await delivery_jobs_collection.create_index(
        [("storeId", 1), ("status", 1), ("createdAt", -1)]
    )
    await delivery_jobs_collection.create_index("assignedRiderId")
    await delivery_jobs_collection.create_index(   # Iteration 10: vendor order queue
        [("vendorId", 1), ("status", 1), ("createdAt", -1)]
    )

    # stores
    await stores_collection.create_index("shopifyDomain")
    await stores_collection.create_index("isDefault")
