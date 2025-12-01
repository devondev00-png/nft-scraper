"""
Reservoir API client for EVM chain collections
Provides floor price, volume, sales, owners, and collection metadata
Supports: Ethereum, Polygon, Arbitrum, Optimism, Base, Zora, etc.
"""

import aiohttp
from typing import Dict, Any, Optional
from loguru import logger

from .base import BaseAPIClient


class ReservoirClient(BaseAPIClient):
    """Reservoir API client for EVM NFT collections"""
    
    BASE_URL = "https://api.reservoir.tools/v4"
    
    # Chain name mapping
    CHAIN_MAPPING = {
        "ethereum": "ethereum",
        "polygon": "polygon",
        "arbitrum": "arbitrum",
        "optimism": "optimism",
        "base": "base",
        "zora": "zora",
    }
    
    def __init__(self, api_key: Optional[str] = None, rate_limit: float = 1.0):
        """
        Initialize Reservoir client
        
        Args:
            api_key: Optional API key for higher rate limits (free tier available)
            rate_limit: Requests per second
        """
        # Convert API key to list format expected by base client
        api_keys = [api_key] if api_key else []
        super().__init__(
            api_keys=api_keys,
            base_url=self.BASE_URL,
            rate_limit=int(rate_limit),
            timeout=30,
            max_retries=3,
        )
        self.api_key = api_key
    
    def _get_chain_name(self, chain: str) -> str:
        """Convert chain name to Reservoir format"""
        chain_lower = chain.lower()
        return self.CHAIN_MAPPING.get(chain_lower, chain_lower)
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """Make request with API key header if available"""
        headers = kwargs.pop("headers", {})
        if self.api_key:
            headers["X-API-KEY"] = self.api_key
        
        return await self._request(method, endpoint, params=params, headers=headers, **kwargs)
    
    async def get_collection_stats(self, contract_address: str, chain: str) -> Dict[str, Any]:
        """
        Get collection statistics (floor price, volume, sales, owners)
        
        Args:
            contract_address: NFT contract address
            chain: Chain name (ethereum, polygon, etc.)
        
        Returns:
            Dict with stats including floorAsk, volume, sales, owners, etc.
        """
        chain_name = self._get_chain_name(chain)
        endpoint = f"/collections/{chain_name}:{contract_address}/v1"
        
        try:
            response = await self._make_request("GET", endpoint)
            if response and isinstance(response, dict):
                # Reservoir returns data in 'collections' array
                collections = response.get("collections", [])
                if collections:
                    return collections[0]
            return response if response else {}
        except Exception as e:
            logger.error(f"Reservoir get_collection_stats error: {e}")
            return {}
    
    async def get_collection_info(self, contract_address: str, chain: str) -> Dict[str, Any]:
        """
        Get collection information (metadata, social links, etc.)
        
        Args:
            contract_address: NFT contract address
            chain: Chain name
        
        Returns:
            Dict with collection metadata
        """
        # Collection info is included in stats endpoint
        return await self.get_collection_stats(contract_address, chain)
    
    # Dummy methods to satisfy abstract base class
    async def get_wallet_nfts(self, wallet_address: str, chain: str, cursor: Optional[str] = None, page_size: int = 100) -> Dict[str, Any]:
        """Not supported by Reservoir"""
        raise NotImplementedError("Reservoir doesn't support wallet NFTs")
    
    async def get_collection_metadata(self, contract_address: str, chain: str) -> Dict[str, Any]:
        """Get collection metadata (alias for get_collection_stats)"""
        return await self.get_collection_stats(contract_address, chain)
    
    async def get_token_metadata(self, asset_id: str, chain: str) -> Dict[str, Any]:
        """Not supported by Reservoir"""
        raise NotImplementedError("Reservoir doesn't support token metadata")

