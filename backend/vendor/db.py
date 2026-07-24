"""
Vendor module MongoDB collections.
Follows the same pattern as rider/db.py.
"""
import os
from motor.motor_asyncio import AsyncIOMotorClient

_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
_db = _client[os.environ["DB_NAME"]]

vendors_collection = _db["vendors"]
vendor_refresh_tokens_collection = _db["vendor_refresh_tokens"]


async def ensure_vendor_indexes() -> None:
    """Create all vendor module indexes. Called once on startup."""
    # vendors
    await vendors_collection.create_index("email", unique=True)
    await vendors_collection.create_index("phone")
    await vendors_collection.create_index([("status", 1), ("isActive", 1)])
    await vendors_collection.create_index("storeId")
    await vendors_collection.create_index("isDeleted")

    # vendor_refresh_tokens
    await vendor_refresh_tokens_collection.create_index("tokenHash")
    await vendor_refresh_tokens_collection.create_index("vendorId")
