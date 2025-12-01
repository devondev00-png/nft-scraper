"""
Magic Eden API client for Solana collections
Provides floor price, volume, sales, and collection metadata
"""

import aiohttp
import asyncio
from typing import Dict, Any, Optional, List
from loguru import logger

from .base import BaseAPIClient


class MagicEdenClient(BaseAPIClient):
    """Magic Eden API client for Solana NFT collections"""
    
    BASE_URL = "https://api-mainnet.magiceden.io/v2"
    
    def __init__(self, api_key: Optional[str] = None, rate_limit: float = 1.0):
        # Magic Eden API keys (optional but recommended for higher limits)
        import os
        self.api_key = api_key or os.getenv("MAGICEDEN_API_KEY") or os.getenv("MAGICEDEN_PUBLIC_API_KEY")
        # Security: Never log private keys
        self.private_api_key = os.getenv("MAGICEDEN_PRIVATE_API_KEY")
        if self.private_api_key:
            # Validate it's not accidentally exposed in logs
            if len(self.private_api_key) < 10:
                logger.warning("Magic Eden private API key seems too short - may be invalid")
        
        # Pass empty list to base class since we handle API keys manually
        super().__init__(
            api_keys=[],
            base_url=self.BASE_URL,
            rate_limit=int(rate_limit),
            timeout=30,
            max_retries=3,
        )
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """Make request with Magic Eden API keys in headers"""
        await self._apply_rate_limit()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        default_headers = {"Content-Type": "application/json"}
        
        # Add API key if available (use public key for most endpoints, private for premium)
        if self.api_key:
            default_headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.private_api_key:
            # Some endpoints might use private key
            default_headers["X-API-KEY"] = self.private_api_key
        
        if "headers" in kwargs:
            default_headers.update(kwargs["headers"])
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.request(
                method=method,
                url=url,
                params=params,
                json=kwargs.get("json_data"),
                headers=default_headers,
            ) as response:
                if response.status == 429:
                    await asyncio.sleep(5)
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                    )
                response.raise_for_status()
                return await response.json()
    
    async def get_collection_stats(self, collection_symbol: str) -> Dict[str, Any]:
        """
        Get collection statistics (floor price, volume, sales)
        
        Args:
            collection_symbol: Magic Eden collection symbol (e.g., 'skeleton_pepe')
        
        Returns:
            Dict with stats including floorPrice, volume24h, volume7d, volume30d, sales24h, etc.
        """
        endpoint = f"/collections/{collection_symbol}/stats"
        
        try:
            response = await self._make_request("GET", endpoint)
            return response if response else {}
        except Exception as e:
            logger.error(f"Magic Eden get_collection_stats error: {e}")
            return {}
    
    async def get_collection_info(self, collection_symbol: str) -> Dict[str, Any]:
        """
        Get collection information (metadata, social links, etc.)
        
        Args:
            collection_symbol: Magic Eden collection symbol
        
        Returns:
            Dict with collection metadata including name, description, social links, etc.
        """
        endpoint = f"/collections/{collection_symbol}"
        
        try:
            response = await self._make_request("GET", endpoint)
            return response if response else {}
        except Exception as e:
            logger.error(f"Magic Eden get_collection_info error: {e}")
            return {}
    
    async def get_collection_listings(self, collection_symbol: str, limit: int = 1) -> list:
        """
        Get collection listings (used for resolving collection address)
        
        Args:
            collection_symbol: Magic Eden collection symbol
            limit: Number of listings to fetch
        
        Returns:
            List of listings
        """
        endpoint = f"/collections/{collection_symbol}/listings"
        params = {"limit": limit}
        
        try:
            response = await self._make_request("GET", endpoint, params=params)
            return response if isinstance(response, list) else []
        except Exception as e:
            logger.error(f"Magic Eden get_collection_listings error: {e}")
            return []
    
    # Dummy methods to satisfy abstract base class
    async def get_wallet_nfts(self, wallet_address: str, chain: str, cursor: Optional[str] = None, page_size: int = 100) -> Dict[str, Any]:
        """Not supported by Magic Eden"""
        raise NotImplementedError("Magic Eden doesn't support wallet NFTs")
    
    async def get_collection_metadata(self, contract_address: str, chain: str) -> Dict[str, Any]:
        """Get collection metadata (alias for get_collection_info)"""
        return await self.get_collection_info(contract_address)
    
    async def get_token_metadata(self, asset_id: str, chain: str) -> Dict[str, Any]:
        """Not supported by Magic Eden"""
        raise NotImplementedError("Magic Eden doesn't support token metadata")

