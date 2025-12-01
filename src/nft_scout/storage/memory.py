"""In-memory storage adapter"""

import asyncio
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
from cachetools import TTLCache

from .base import StorageAdapter
from ..config import Config


class MemoryStorage(StorageAdapter):
    """In-memory TTL cache"""
    
    def __init__(self, config: Config):
        self.config = config
        # Create TTL cache with max size
        max_size = 10000
        self.cache: TTLCache[str, Any] = TTLCache(
            maxsize=max_size,
            ttl=config.cache_ttl,
        )
        self._lock = asyncio.Lock()
    
    async def get_cache(self, key: str) -> Optional[Any]:
        """Get cached value"""
        async with self._lock:
            return self.cache.get(key)
    
    async def set_cache(self, key: str, value: Any, ttl: int = 900) -> None:
        """Set cached value with TTL"""
        async with self._lock:
            # Create temporary cache with custom TTL if needed
            if ttl != self.config.cache_ttl:
                # For custom TTL, we'd need a different approach
                # For now, use default TTL
                self.cache[key] = value
            else:
                self.cache[key] = value
    
    async def delete_cache(self, key: str) -> None:
        """Delete cached value"""
        async with self._lock:
            self.cache.pop(key, None)

