"""
Rider module MongoDB collections.

Follows the same pattern as auth/db.py — a dedicated Motor client that reads
MONGO_URL / DB_NAME after server.py's load_dotenv() has run.

Collections:
  riders               — one document per rider (isDeleted for soft delete)
  rider_refresh_tokens — opaque refresh tokens stored as SHA-256 hashes;
                         mirrors the auth_refresh_tokens pattern exactly
"""
import os

from motor.motor_asyncio import AsyncIOMotorClient

_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
_db = _client[os.environ["DB_NAME"]]

riders_collection = _db["riders"]
rider_refresh_tokens_collection = _db["rider_refresh_tokens"]


async def ensure_rider_indexes() -> None:
    """
    Create all indexes for the rider module.
    Called once on application startup from server.py.

    riders:
      email (unique)          — login + dedup guard
      phone                   — search / dedup
      status + isActive       — admin dashboard "available riders" query
      storeIds                — zone-based assignment queries (Phase 2)
      isDeleted               — filter out soft-deleted riders in all queries

    rider_refresh_tokens:
      tokenHash               — fast single-token lookup on refresh/logout
      riderId                 — revoke all tokens for a rider on compromise
    """
    # riders
    await riders_collection.create_index("email", unique=True)
    await riders_collection.create_index("phone")
    await riders_collection.create_index([("status", 1), ("isActive", 1)])
    await riders_collection.create_index("storeIds")
    await riders_collection.create_index("isDeleted")

    # rider_refresh_tokens
    await rider_refresh_tokens_collection.create_index("tokenHash")
    await rider_refresh_tokens_collection.create_index("riderId")
