"""Alchemy API client for EVM chains"""

from typing import Dict, Any, Optional, List
import aiohttp
from loguru import logger

from .base import BaseAPIClient


class AlchemyClient(BaseAPIClient):
    """Alchemy API client"""

    CHAIN_MAP = {
        "ethereum": "eth-mainnet",
        "polygon": "polygon-mainnet",
        "arbitrum": "arb-mainnet",
        "optimism": "opt-mainnet",
        "base": "base-mainnet",
    }

    def __init__(self, api_keys: List[str], timeout: int = 30, max_retries: int = 3, **kwargs: Any):
        base_url = "https://{chain}.g.alchemy.com"
        super().__init__(api_keys, base_url, rate_limit=330, timeout=timeout, max_retries=max_retries, **kwargs)
    
    def _get_chain_name(self, chain: str) -> str:
        """Convert chain name to Alchemy format"""
        chain_lower = chain.lower()
        return self.CHAIN_MAP.get(chain_lower, chain_lower)
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        chain: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make Alchemy API request"""
        chain_name = self._get_chain_name(chain)
        url = f"https://{chain_name}.g.alchemy.com/v2/{self.get_api_key()}/{endpoint}"
        
        async with aiohttp.ClientSession() as session:
            if method.upper() == "GET":
                async with session.get(url, params=params) as response:
                    response.raise_for_status()
                    return await response.json()
            else:
                async with session.post(url, json=json_data) as response:
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
        params = {
            "owner": wallet_address,
            "withMetadata": "true",
            "pageSize": min(page_size, 10000),
        }
        if cursor:
            params["pageKey"] = cursor
        
        try:
            response = await self._make_request("GET", "getNFTs", chain, params=params)
            return {
                "ownedNfts": response.get("ownedNfts", []),
                "pageKey": response.get("pageKey"),
                "totalCount": response.get("totalCount"),
            }
        except Exception as e:
            logger.error(f"Alchemy get_wallet_nfts error: {e}")
            raise
    
    async def get_collection_metadata(
        self,
        contract_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Get collection metadata"""
        # Get collection info via contract metadata
        try:
            response = await self._make_request(
                "GET",
                "getContractMetadata",
                chain,
                params={"contractAddress": contract_address},
            )
            return response
        except Exception as e:
            logger.error(f"Alchemy get_collection_metadata error: {e}")
            return {}
    
    async def get_token_metadata(
        self,
        contract_address: str,
        token_id: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Get individual token metadata"""
        try:
            response = await self._make_request(
                "GET",
                "getNFTMetadata",
                chain,
                params={
                    "contractAddress": contract_address,
                    "tokenId": token_id,
                },
            )
            return response
        except Exception as e:
            logger.error(f"Alchemy get_token_metadata error: {e}")
            return {}
    
    async def get_contract_nfts(
        self,
        contract_address: str,
        chain: str,
        cursor: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Get all NFTs in a collection"""
        params = {
            "contractAddress": contract_address,
            "withMetadata": "true",
            "pageSize": min(page_size, 10000),  # Increased limit for better performance
        }
        if cursor:
            # Alchemy accepts both pageKey and startToken - use startToken for better compatibility
            # startToken can be a token ID or the nextToken from previous response
            params["startToken"] = cursor
            # Also try pageKey as fallback (some endpoints use this)
            params["pageKey"] = cursor
        
        try:
            response = await self._make_request("GET", "getNFTsForCollection", chain, params=params)
            # Alchemy returns nextToken for pagination - use it as pageKey for compatibility
            next_token = response.get("nextToken") or response.get("pageKey")
            return {
                "nfts": response.get("nfts", []),
                "pageKey": next_token,  # Use nextToken as pageKey
                "nextToken": next_token,  # Also return as nextToken
            }
        except Exception as e:
            logger.error(f"Alchemy get_contract_nfts error: {e}")
            raise
    
    async def get_transfers_for_wallet(
        self,
        wallet_address: str,
        chain: str,
        from_block: Optional[str] = None,
        to_block: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get NFT transfers for a wallet"""
        params = {
            "fromAddress": wallet_address,
        }
        if from_block:
            params["fromBlock"] = from_block
        if to_block:
            params["toBlock"] = to_block
        
        try:
            response = await self._make_request("GET", "getNFTTransfers", chain, params=params)
            return {
                "transfers": response.get("transfers", []),
            }
        except Exception as e:
            logger.error(f"Alchemy get_transfers_for_wallet error: {e}")
            return {"transfers": []}

