import json
from typing import Any, Optional
from .logger import get_structured_logger

logger = get_structured_logger("signal_engine.cache")

class LookbackCache:
    """
    Redis-based cache for fast access to Investor DNA and historical stats.
    Using a simple dict for mock purposes if Redis is unavailable in Phase 1,
    but structured to accept an async Redis client (like from redis.asyncio).
    """
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._mock_cache = {} # Fallback for local testing without Redis
        if not self.redis:
            logger.info("Redis client not provided, using in-memory mock cache.")

    async def get(self, key: str) -> Optional[Any]:
        if self.redis:
            val = await self.redis.get(key)
            return json.loads(val) if val else None
        return self._mock_cache.get(key)

    async def set(self, key: str, value: Any, expire: int = 3600):
        if self.redis:
            await self.redis.set(key, json.dumps(value), ex=expire)
        else:
            self._mock_cache[key] = value
