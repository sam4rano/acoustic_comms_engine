import json
import logging
from typing import Optional

from app.memory.errors import RedisUnavailableError

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.host = host
        self.port = port
        self.db = db
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import redis.asyncio as aioredis

            self._client = aioredis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True,
            )
        return self._client

    async def get(self, key: str) -> Optional[dict]:
        try:
            val = await self.client.get(key)
            if val is not None:
                return json.loads(val)
            return None
        except Exception as e:
            logger.warning("Redis get failed for key %s: %s", key, e)
            raise RedisUnavailableError(f"Redis get failed: {e}") from e

    async def set(self, key: str, value: dict, ttl_s: int = 300) -> None:
        try:
            await self.client.set(key, json.dumps(value), ex=ttl_s)
        except Exception as e:
            logger.warning("Redis set failed for key %s: %s", key, e)
            raise RedisUnavailableError(f"Redis set failed: {e}") from e

    async def invalidate(self, prefix: str) -> None:
        try:
            cursor = 0
            while True:
                cursor, keys = await self.client.scan(
                    cursor=cursor, match=f"{prefix}*", count=100
                )
                if keys:
                    await self.client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.warning("Redis invalidate failed for prefix %s: %s", prefix, e)
            raise RedisUnavailableError(f"Redis invalidate failed: {e}") from e

    async def health(self) -> bool:
        try:
            return await self.client.ping()
        except Exception:
            return False
