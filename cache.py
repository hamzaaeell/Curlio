"""
Simple in-memory cache with TTL support.
Keeps repeated identical queries from hitting Google.
"""

import time
import hashlib
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TTLCache:
    """Thread-safe in-memory cache with time-to-live expiry."""

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 500):
        """
        Args:
            ttl_seconds: How long to keep cached results (default 1 hour)
            max_size:    Max number of entries before evicting oldest
        """
        self.ttl = ttl_seconds
        self.max_size = max_size
        self._store: dict[str, tuple[float, dict]] = {}  # key -> (timestamp, data)

    def _make_key(self, query: str, num: int, lang: str, country: str, page: int) -> str:
        raw = json.dumps(
            {"q": query, "num": num, "lang": lang, "country": country, "page": page},
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, query: str, num: int, lang: str, country: str, page: int) -> Optional[dict]:
        key = self._make_key(query, num, lang, country, page)
        entry = self._store.get(key)
        if entry is None:
            return None
        timestamp, data = entry
        if time.time() - timestamp > self.ttl:
            del self._store[key]
            logger.debug("Cache expired for key %s", key[:8])
            return None
        logger.debug("Cache hit for key %s", key[:8])
        return data

    def set(self, query: str, num: int, lang: str, country: str, page: int, data: dict) -> None:
        key = self._make_key(query, num, lang, country, page)
        # Evict oldest entries if at capacity
        if len(self._store) >= self.max_size:
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest_key]
            logger.debug("Cache evicted oldest entry")
        self._store[key] = (time.time(), data)
        logger.debug("Cache set for key %s", key[:8])

    def clear(self) -> int:
        count = len(self._store)
        self._store.clear()
        return count

    @property
    def size(self) -> int:
        return len(self._store)


# Global cache instance (shared across requests)
cache = TTLCache(ttl_seconds=3600, max_size=500)
