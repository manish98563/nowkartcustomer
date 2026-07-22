import time
from typing import Any, Optional


class TTLCache:
    """
    Minimal in-memory TTL cache used to avoid hammering the Shopify Storefront
    API for data that changes infrequently (collections, product listings).
    Not shared across processes — fine for a single-instance preview/small
    deployment; swap for Redis if horizontally scaling later.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._store[key] = (time.monotonic() + ttl_seconds, value)

    def pop(self, key: str) -> Optional[Any]:
        """Reads and removes a key atomically (single-use tokens/state)."""
        entry = self._store.pop(key, None)
        if not entry:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            return None
        return value

    def invalidate_prefix(self, prefix: str) -> None:
        keys_to_drop = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_drop:
            self._store.pop(k, None)


cache = TTLCache()
