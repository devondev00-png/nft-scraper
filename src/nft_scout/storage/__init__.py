"""Storage adapters for caching and persistence"""

from .base import StorageAdapter
from .memory import MemoryStorage
from .redis_adapter import RedisStorage

__all__ = ["MemoryStorage", "RedisStorage", "StorageAdapter"]


def get_storage_adapter(config):
    """Get appropriate storage adapter based on config"""
    if config.cache_type == "redis" and config.redis_url:
        return RedisStorage(config)
    return MemoryStorage(config)

