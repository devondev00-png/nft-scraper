"""Moralis API client"""

from typing import Dict, Any, Optional, List
import asyncio
import aiohttp
from loguru import logger

from .base import BaseAPIClient


class MoralisClient(BaseAPIClient):
    """Moralis API client"""
    
    CHAIN_MAP = {
        "ethereum": "eth",
        "polygon": "polygon",
        "arbitrum": "arbitrum",
        "optimism": "optimism",
        "base": "base",
        "bsc": "bsc",
    }
    
    def __init__(self, api_keys: List[str], timeout: int = 30, max_retries: int = 3, **kwargs: Any):
        base_url = "https://deep-index.moralis.io/api/v2"
        super().__init__(api_keys, base_url, rate_limit=200, timeout=timeout, max_retries=max_retries, **kwargs)
    
    def _get_chain_name(self, chain: str) -> str:
        """Convert chain name to Moralis format"""
        chain_lower = chain.lower()
        return self.CHAIN_MAP.get(chain_lower, chain_lower)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with API key"""
        return {
            "X-API-Key": self.get_api_key(),
            "Accept": "application/json",
        }
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make Moralis API request"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 429:
                    logger.warning("Moralis rate limited, rotating key")
                    self.rotate_api_key()
                    await asyncio.sleep(5)
                
                response.raise_for_status()
                return await response.json()
    
    async def get_wallet_nfts(
        self,
        wallet_address: str,
        chain: str,
        cursor: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Get NFTs owned by a wallet"""
        chain_name = self._get_chain_name(chain)
        params = {
            "chain": chain_name,
            "limit": min(page_size, 10000),
        }
        if cursor:
            params["cursor"] = cursor
        
        try:
            response = await self._make_request(
                "GET",
                f"{wallet_address}/nft",
                params=params,
            )
            return {
                "ownedNfts": response.get("result", []),
                "cursor": response.get("cursor"),
                "totalCount": response.get("total"),
            }
        except Exception as e:
            logger.error(f"Moralis get_wallet_nfts error: {e}")
            raise
    
    async def get_collection_metadata(
        self,
        contract_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Get collection metadata"""
        chain_name = self._get_chain_name(chain)
        params = {
            "chain": chain_name,
        }
        
        try:
            response = await self._make_request(
                "GET",
                f"nft/{contract_address}/metadata",
                params=params,
            )
            return response
        except Exception as e:
            logger.error(f"Moralis get_collection_metadata error: {e}")
            return {}
    
    async def get_token_metadata(
        self,
        contract_address: str,
        token_id: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Get individual token metadata"""
        chain_name = self._get_chain_name(chain)
        params = {
            "chain": chain_name,
        }
        
        try:
            response = await self._make_request(
                "GET",
                f"nft/{contract_address}/{token_id}",
                params=params,
            )
            return response
        except Exception as e:
            logger.error(f"Moralis get_token_metadata error: {e}")
            return {}
    
    async def get_contract_nfts(
        self,
        contract_address: str,
        chain: str,
        cursor: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Get all NFTs in a collection"""
        chain_name = self._get_chain_name(chain)
        params = {
            "chain": chain_name,
            "limit": min(page_size, 10000),  # Increased limit for better performance
        }
        if cursor:
            params["cursor"] = cursor
        
        try:
            response = await self._make_request(
                "GET",
                f"nft/{contract_address}",
                params=params,
            )
            return {
                "nfts": response.get("result", []),
                "cursor": response.get("cursor"),
                "pageKey": response.get("cursor"),  # Alias for compatibility
                "page": response.get("cursor"),  # Alias for compatibility
            }
        except Exception as e:
            logger.error(f"Moralis get_contract_nfts error: {e}")
            return {"nfts": [], "cursor": None}
    
    async def get_collection_stats(
        self,
        contract_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Get collection statistics"""
        chain_name = self._get_chain_name(chain)
        params = {
            "chain": chain_name,
        }
        
        try:
            response = await self._make_request(
                "GET",
                f"nft/{contract_address}/stats",
                params=params,
            )
            return response
        except Exception as e:
            logger.error(f"Moralis get_collection_stats error: {e}")
            return {}

