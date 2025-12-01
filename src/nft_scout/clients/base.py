"""Base client with common functionality"""

import asyncio
import time
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
import aiohttp
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from loguru import logger


class BaseAPIClient(ABC):
    """Base class for API clients with retry logic and rate limiting"""
    
    def __init__(
        self,
        api_keys: List[str],
        base_url: str,
        rate_limit: int = 100,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.api_keys = api_keys
        self.base_url = base_url
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.max_retries = max_retries
        self.current_key_index = 0
        self._rate_limiter_semaphore = asyncio.Semaphore(rate_limit)
        self._last_request_time = 0
        self._min_request_interval = 1.0 / rate_limit
        
    def get_api_key(self) -> str:
        """Get current API key (with rotation)"""
        if not self.api_keys:
            raise ValueError("No API keys configured")
        key = self.api_keys[self.current_key_index % len(self.api_keys)]
        return key
    
    def rotate_api_key(self):
        """Rotate to next API key"""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
    
    async def _apply_rate_limit(self):
        """Rate limiting"""
        async with self._rate_limiter_semaphore:
            current_time = time.time()
            time_since_last = current_time - self._last_request_time
            if time_since_last < self._min_request_interval:
                await asyncio.sleep(self._min_request_interval - time_since_last)
            self._last_request_time = time.time()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        await self._apply_rate_limit()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            try:
                async with session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=default_headers,
                ) as response:
                    if response.status == 429:  # Rate limited
                        logger.warning(f"Rate limited, rotating API key")
                        self.rotate_api_key()
                        await asyncio.sleep(5)
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=429,
                        )
                    
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientError as e:
                logger.error(f"Request failed: {e}")
                raise
    
    @abstractmethod
    async def get_wallet_nfts(
        self,
        wallet_address: str,
        chain: str,
        cursor: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Get NFTs owned by a wallet"""
        pass
    
    @abstractmethod
    async def get_collection_metadata(
        self,
        contract_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Get collection metadata"""
        pass
    
    @abstractmethod
    async def get_token_metadata(
        self,
        contract_address: str,
        token_id: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Get individual token metadata"""
        pass

