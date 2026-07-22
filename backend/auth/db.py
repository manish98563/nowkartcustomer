"""Dedicated Mongo collections for customer auth. Uses the same MONGO_URL/DB_NAME
as the rest of the app (already loaded into the environment by server.py's
load_dotenv() before this module is imported)."""
import os

from motor.motor_asyncio import AsyncIOMotorClient

_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = _client[os.environ["DB_NAME"]]

users_collection = db["users"]
refresh_tokens_collection = db["auth_refresh_tokens"]


async def ensure_indexes() -> None:
    await users_collection.create_index("shopifyCustomerId", unique=True)
    await refresh_tokens_collection.create_index("tokenHash")
    await refresh_tokens_collection.create_index("userId")
