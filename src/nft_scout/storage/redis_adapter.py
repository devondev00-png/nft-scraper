"""Redis storage adapter (optional)"""

import json
from typing import Any, Optional

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from .base import StorageAdapter
from ..config import Config


class RedisStorage(StorageAdapter):
    """Redis-based storage adapter"""
    
    def __init__(self, config: Config):
        self.config = config
        self.redis_client: Optional[Any] = None
        self._initialized = False
        if not REDIS_AVAILABLE:
            raise ImportError("redis package not installed. Install with: pip install redis")
    
    async def _ensure_connected(self):
        """Ensure Redis connection is established"""
        if not self._initialized:
            if not self.config.redis_url:
                raise ValueError("Redis URL not configured")
            if not REDIS_AVAILABLE:
                raise ImportError("redis package not installed")
            self.redis_client = await redis.from_url(
                self.config.redis_url,
                decode_responses=True,
            )
            self._initialized = True
    
    async def get_cache(self, key: str) -> Optional[Any]:
        """Get cached value from Redis"""
        try:
            await self._ensure_connected()
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            # Fallback to None if Redis unavailable
            logger.debug(f"Redis get_cache error: {e}")
            return None
    
    async def set_cache(self, key: str, value: Any, ttl: int = 900) -> None:
        """Set cached value in Redis with TTL"""
        try:
            await self._ensure_connected()
            serialized = json.dumps(value, default=str)
            await self.redis_client.setex(key, ttl, serialized)
        except Exception as e:
            # Silently fail if Redis unavailable
            logger.debug(f"Redis set_cache error: {e}")
    
    async def delete_cache(self, key: str) -> None:
        """Delete cached value from Redis"""
        try:
            await self._ensure_connected()
            await self.redis_client.delete(key)
        except Exception as e:
            # Redis unavailable or error, silently fail
            logger.debug(f"Redis delete_cache error: {e}")
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()

