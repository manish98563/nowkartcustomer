"""
Admin module MongoDB collections.
"""
import os
from motor.motor_asyncio import AsyncIOMotorClient

_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
_db = _client[os.environ["DB_NAME"]]

admin_users_collection = _db["admin_users"]
admin_refresh_tokens_collection = _db["admin_refresh_tokens"]
audit_logs_collection = _db["audit_logs"]


async def ensure_admin_indexes() -> None:
    """Create all admin module indexes. Called once on startup."""
    # admin_users
    await admin_users_collection.create_index("email", unique=True)
    await admin_users_collection.create_index("role")
    await admin_users_collection.create_index("isDeleted")

    # admin_refresh_tokens
    await admin_refresh_tokens_collection.create_index("tokenHash")
    await admin_refresh_tokens_collection.create_index("adminId")

    # audit_logs — primary query pattern: newest-first, per-admin, per-resource
    await audit_logs_collection.create_index([("timestamp", -1)])
    await audit_logs_collection.create_index("adminId")
    await audit_logs_collection.create_index("resourceType")
    await audit_logs_collection.create_index("action")
