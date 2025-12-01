"""Base storage adapter"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class StorageAdapter(ABC):
    """Base storage adapter interface"""
    
    @abstractmethod
    async def get_cache(self, key: str) -> Optional[Any]:
        """Get cached value"""
        pass
    
    @abstractmethod
    async def set_cache(self, key: str, value: Any, ttl: int = 900) -> None:
        """Set cached value with TTL"""
        pass
    
    @abstractmethod
    async def delete_cache(self, key: str) -> None:
        """Delete cached value"""
        pass

