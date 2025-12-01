"""Helius API client for Solana"""

from typing import Dict, Any, Optional, List, Union, cast
import aiohttp
import re
from loguru import logger

from .base import BaseAPIClient


class HeliusClient(BaseAPIClient):
    """Helius API client for Solana"""
    
    def __init__(self, api_keys: List[str], rpc_url: Optional[str] = None, rate_limit: int = 1000, timeout: int = 30, max_retries: int = 3, **kwargs: Any):
        base_url = "https://api.helius.xyz"
        super().__init__(api_keys, base_url, rate_limit=rate_limit, timeout=timeout, max_retries=max_retries, **kwargs)
        # Store base RPC URL without API key
        if rpc_url and "api-key" in rpc_url:
            # Extract base URL if API key is already in URL
            self.rpc_url = rpc_url.split("?")[0]
        else:
            self.rpc_url = rpc_url or "https://mainnet.helius-rpc.com"
    
    def _get_rpc_url(self) -> str:
        """Get RPC URL with API key"""
        api_key = self.get_api_key()
        return f"{self.rpc_url}/?api-key={api_key}"
    
    async def _make_das_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make Helius DAS API request"""
        url = f"{self.base_url}/v0/{method}"
        headers = {"X-API-Key": self.get_api_key()}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=params, headers=headers) as response:
                if response.status == 404:
                    # Return empty result for 404 instead of raising
                    logger.warning(f"Helius DAS API 404 for {method}: {params}")
                    return {"items": [], "page": None}
                response.raise_for_status()
                return await response.json()
    
    async def _make_rpc_request(
        self,
        method: str,
        params: Optional[Union[Dict[str, Any], List[Any]]] = None,
    ) -> Dict[str, Any]:
        """Make Solana RPC request via Helius"""
        # Build RPC URL with API key
        api_key = self.get_api_key()
        url = f"{self.rpc_url}/?api-key={api_key}"
        
        # Handle params - could be a list or a dict
        if params is None:
            rpc_params: Union[Dict[str, Any], List[Any]] = []
        elif isinstance(params, dict):
            rpc_params = params
        elif isinstance(params, list) and len(params) == 1 and isinstance(params[0], dict):  # type: ignore[redundant-expr]
            # If list with one dict, use the dict directly
            rpc_params = params[0]  # type: ignore[assignment]
        else:
            rpc_params = params
        
        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": rpc_params,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                result = await response.json()
                return result.get("result", {})
    
    async def get_wallet_nfts(
        self,
        wallet_address: str,
        chain: str = "solana",
        cursor: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Get NFTs owned by a Solana wallet"""
        if chain.lower() != "solana":
            raise ValueError("Helius client only supports Solana")
        
        try:
            params = {
                "ownerAddress": wallet_address,
                "limit": min(page_size, 10000),
            }
            if cursor:
                params["page"] = cursor
            
            response = await self._make_das_request("getAssetsByOwner", params)
            
            items = response.get("items", [])
            
            # Filter for NFTs only
            nfts_raw = [item for item in items if item.get("interface") in ["V1_NFT", "V2_NFT", "ProgrammableNFT"]]
            
            # Enrich metadata for all NFTs
            nfts: List[Dict[str, Any]] = []
            for item in nfts_raw:
                try:
                    enriched_item: Dict[str, Any] = await self._enrich_nft_metadata(item)
                    nfts.append(enriched_item)
                except Exception as enrich_err:
                    logger.debug(f"Error enriching NFT metadata: {enrich_err}")
                    # item is already Dict[str, Any] from nfts_raw
                    nfts.append(cast(Dict[str, Any], item))  # Use original if enrichment fails
            
            return {
                "ownedNfts": nfts,
                "page": response.get("page"),
                "totalCount": len(nfts),
            }
        except Exception as e:
            logger.error(f"Helius get_wallet_nfts error: {e}")
            raise
    
    async def get_collection_metadata(
        self,
        contract_address: str,
        chain: str = "solana",
    ) -> Dict[str, Any]:
        """Get collection metadata"""
        if chain.lower() != "solana":
            raise ValueError("Helius client only supports Solana")
        
        try:
            params = {
                "groupKey": "collection",
                "groupValue": contract_address,
            }
            
            response = await self._make_das_request("getAssetsByGroup", params)
            
            items = response.get("items", [])
            if not items:
                return {}
            
            # Use first item for collection metadata
            first_item = items[0]
            content = first_item.get("content", {})

            return {
                "name": content.get("metadata", {}).get("name"),
                "description": content.get("metadata", {}).get("description"),
                "image": content.get("files", [{}])[0].get("uri") if content.get("files") else None,
                "totalSupply": len(items),
            }
        except Exception as e:
            logger.error(f"Helius get_collection_metadata error: {e}")
            return {}
    
    async def get_token_metadata(
        self,
        contract_address: str,
        token_id: str,
        chain: str = "solana",
    ) -> Dict[str, Any]:
        """Get individual token metadata"""
        if chain.lower() != "solana":
            raise ValueError("Helius client only supports Solana")
        
        try:
            # For Solana, contract_address is collection, token_id is the asset ID (mint address)
            asset_id = token_id if token_id else contract_address
            params = {
                "ids": [asset_id],
            }
            
            # Helius DAS API uses getAssets (plural) for fetching by IDs
            response = await self._make_das_request("getAssets", params)
            
            # Response can be dict or list depending on API version
            nft_data = None
            if isinstance(response, dict):  # type: ignore[redundant-expr]
                items = response.get("items", [])
                if items:
                    nft_data = items[0]
                else:
                    nft_data = response
            elif isinstance(response, list) and response:  # type: ignore[redundant-expr]
                nft_data = response[0]
            else:
                nft_data = response if response else {}
            
            # Enrich metadata if we have NFT data
            if nft_data and isinstance(nft_data, dict):
                nft_data = await self._enrich_nft_metadata(nft_data)  # type: ignore[arg-type]
            
            return nft_data
        except Exception as e:
            logger.error(f"Helius get_token_metadata error: {e}")
            return {}
    
    async def get_collection_nfts(
        self,
        collection_address: str,
        chain: str = "solana",
        cursor: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Get all NFTs in a Solana collection"""
        # Reset collection total tracking for new collections
        if not hasattr(self, '_current_collection') or self._current_collection != collection_address:
            self._current_collection = collection_address
            self._collection_total = None
            self._last_total = None
        if chain.lower() != "solana":
            raise ValueError("Helius client only supports Solana")
        
        try:
            # Check if it looks like a Solana address (base58, 32-44 chars)
            is_address = len(collection_address) >= 32 and len(collection_address) <= 44 and re.match(r'^[1-9A-HJ-NP-Za-km-z]+$', collection_address)
            
            if is_address:
                # It's a Solana address - use collection group
                # Try RPC first, then fallback to DAS API
                page_cursor = None
                has_more = False
                items = []
                
                try:
                    rpc_params = {
                        "groupKey": "collection",
                        "groupValue": collection_address,
                        "limit": min(page_size, 10000),
                    }
                    if cursor:
                        rpc_params["cursor"] = cursor
                    
                    rpc_response = await self._make_rpc_request("getAssetsByGroup", rpc_params)
                    items = rpc_response.get("items", [])
                    # Extract pagination cursor from RPC response
                    page_cursor = rpc_response.get("cursor")
                    total_returned = rpc_response.get("total", 0)
                    
                    logger.debug(f"Helius RPC Response (direct address): items={len(items)}, total={total_returned}, cursor={'Yes' if page_cursor else 'None'}, is_first_request={not cursor}, page_size={page_size}, limit={min(page_size, 10000)}")
                    
                    # IMPORTANT: Helius RPC 'total' field is the count of items RETURNED in this response,
                    # NOT the total collection size. To get actual total:
                    # - If no cursor AND items < limit: total = len(items)
                    # - If cursor exists: total is unknown (need to paginate to count)
                    # - If first request: try to get accurate total by checking if we got all items
                    limit = min(page_size, 10000)
                    actual_total = None
                    
                    # If this is the first request (no cursor), and we got fewer items than limit and no cursor,
                    # then we got all items and the total is len(items)
                    if not cursor:
                        if not page_cursor and len(items) < limit:
                            # We got all items in one request
                            actual_total = len(items)
                            logger.debug(f"First request: No cursor + items ({len(items)}) < limit ({limit}) -> actual_total = len(items) = {actual_total}")
                        elif page_cursor:
                            # There are more items, we don't know total yet
                            actual_total = None
                            logger.debug(f"First request: Has cursor -> actual_total = None (will paginate to find total)")
                        else:
                            # We got exactly limit items - might be more, use the total from API as estimate
                            actual_total = total_returned
                            logger.debug(f"First request: No cursor + items ({len(items)}) >= limit ({limit}) -> actual_total = total_returned = {actual_total}")
                    else:
                        # Not first request - we can't determine total from this response alone
                        actual_total = None
                        logger.debug(f"Subsequent request (cursor exists) -> actual_total = None")
                    
                    # Store total for later retrieval (first request only)
                    if actual_total is not None and (not hasattr(self, '_collection_total') or self._collection_total is None):
                        self._collection_total = actual_total
                        self._last_total = actual_total
                        logger.info(f"Collection total determined: {actual_total} (from first request with limit={limit}, items={len(items)}, cursor={bool(page_cursor)})")
                    elif not hasattr(self, '_collection_total') or self._collection_total is None:
                        # Store the returned total as a fallback estimate
                        if total_returned > 0:
                            self._collection_total = total_returned
                            self._last_total = total_returned
                            logger.info(f"Collection total estimate: {total_returned} (may be incomplete if cursor exists)")
                        else:
                            logger.debug(f"Helius RPC: total_returned={total_returned}, actual_total={actual_total} - not storing (both are 0/None)")
                    # Check if there are more items:
                    # 1. If cursor exists, there's definitely more
                    # 2. If we got a full page (reached limit), there's likely more
                    # 3. If total is known and we've scraped less than total, there's more
                    limit = min(page_size, 10000)
                    has_more = (
                        page_cursor is not None  # Cursor exists = more pages
                        or len(items) >= limit  # Got full page = likely more
                        or (total_returned > 0 and len(items) < total_returned)  # Total known and not reached
                    )
                except Exception as rpc_err:
                    logger.debug(f"RPC getAssetsByGroup failed: {rpc_err}, trying DAS API")
                    # Fallback to DAS API
                    params = {
                        "groupKey": "collection",
                        "groupValue": collection_address,
                        "limit": min(page_size, 10000),
                    }
                    if cursor:
                        params["page"] = cursor
                    response = await self._make_das_request("getAssetsByGroup", params)
                    items = response.get("items", [])
                    page_cursor = response.get("page") or response.get("cursor")
                    has_more = page_cursor is not None
            else:
                # It's likely a marketplace collection symbol - try to resolve via marketplace APIs
                logger.info(f"Collection symbol detected (not address): {collection_address}")
                logger.info("Attempting to resolve collection symbol to Solana address via marketplaces...")
                
                items = []
                collection_addr_found = None
                
                try:
                    # Try multiple marketplaces: Magic Eden, Nintondo, Froggy.market
                    async with aiohttp.ClientSession() as session:
                        # 1. Try Magic Eden API
                        if not collection_addr_found:
                            try:
                                me_listings_url = f"https://api-mainnet.magiceden.io/v2/collections/{collection_address}/listings?limit=1"
                                async with session.get(me_listings_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                                    if resp.status == 200:
                                        listings = await resp.json()
                                        if listings and len(listings) > 0:
                                            token_mint = listings[0].get("tokenMint") or listings[0].get("token", {}).get("mintAddress")
                                            if token_mint:
                                                collection_addr_found = await self._extract_collection_from_mint(token_mint)
                                                if collection_addr_found:
                                                    logger.info(f"Resolved collection via Magic Eden + Helius: {collection_addr_found}")
                            except Exception as me_err:
                                logger.debug(f"Magic Eden API error: {me_err}")
                        
                        # 2. Try Nintondo (check if they have listings endpoint)
                        if not collection_addr_found:
                            try:
                                # Nintondo may use similar structure - try common endpoints
                                nintondo_urls = [
                                    f"https://api.nintondo.io/v1/collections/{collection_address}/listings?limit=1",
                                    f"https://nintondo.io/api/collections/{collection_address}/listings?limit=1",
                                ]
                                for nintondo_url in nintondo_urls:
                                    try:
                                        async with session.get(nintondo_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                                            if resp.status == 200:
                                                data = await resp.json()
                                                # Try to extract token mint from various response formats
                                                listings: List[Any] = data if isinstance(data, list) else data.get("listings", []) or data.get("items", [])  # type: ignore[assignment]
                                                if listings and len(listings) > 0:  # type: ignore[arg-type]
                                                    first_listing = listings[0]  # type: ignore[index]
                                                    token_mint: Optional[str] = (  # type: ignore[assignment]
                                                        first_listing.get("tokenMint") if isinstance(first_listing, dict) else None  # type: ignore[union-attr]
                                                        or (first_listing.get("mint") if isinstance(first_listing, dict) else None)  # type: ignore[union-attr]
                                                        or (first_listing.get("mintAddress") if isinstance(first_listing, dict) else None)  # type: ignore[union-attr]
                                                        or (first_listing.get("token", {}).get("mintAddress") if isinstance(first_listing, dict) else None)  # type: ignore[union-attr]
                                                    )
                                                    if token_mint and isinstance(token_mint, str):  # type: ignore[redundant-expr, misc]
                                                        collection_addr_found = await self._extract_collection_from_mint(token_mint)
                                                        if collection_addr_found:
                                                            logger.info(f"Resolved collection via Nintondo + Helius: {collection_addr_found}")
                                                            break
                                    except Exception:
                                        continue
                            except Exception as nintondo_err:
                                logger.debug(f"Nintondo API error: {nintondo_err}")
                        
                        # 3. Try Froggy.market
                        if not collection_addr_found:
                            try:
                                froggy_urls = [
                                    f"https://api.froggy.market/v1/collections/{collection_address}/listings?limit=1",
                                    f"https://froggy.market/api/collections/{collection_address}/listings?limit=1",
                                    f"https://api.froggy.market/collections/{collection_address}?limit=1",
                                ]
                                for froggy_url in froggy_urls:
                                    try:
                                        async with session.get(froggy_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                                            if resp.status == 200:
                                                data = await resp.json()
                                                listings: List[Any] = data if isinstance(data, list) else data.get("listings", []) or data.get("items", []) or data.get("nfts", [])  # type: ignore[assignment]
                                                if listings and len(listings) > 0:  # type: ignore[arg-type]
                                                    first_listing = listings[0]  # type: ignore[index]
                                                    token_mint: Optional[str] = (  # type: ignore[assignment]
                                                        first_listing.get("tokenMint") if isinstance(first_listing, dict) else None  # type: ignore[union-attr]
                                                        or (first_listing.get("mint") if isinstance(first_listing, dict) else None)  # type: ignore[union-attr]
                                                        or (first_listing.get("mintAddress") if isinstance(first_listing, dict) else None)  # type: ignore[union-attr]
                                                        or (first_listing.get("token", {}).get("mintAddress") if isinstance(first_listing, dict) else None)  # type: ignore[union-attr]
                                                        or (first_listing.get("mint_address") if isinstance(first_listing, dict) else None)  # type: ignore[union-attr]
                                                    )
                                                    if token_mint and isinstance(token_mint, str):  # type: ignore[redundant-expr, misc]
                                                        collection_addr_found = await self._extract_collection_from_mint(token_mint)
                                                        if collection_addr_found:
                                                            logger.info(f"Resolved collection via Froggy.market + Helius: {collection_addr_found}")
                                                            break
                                    except Exception:
                                        continue
                            except Exception as froggy_err:
                                logger.debug(f"Froggy.market API error: {froggy_err}")
                    
                    # If Magic Eden API didn't work, try searching by name using Helius
                    if not collection_addr_found:
                        search_name = collection_address.replace("_", " ").replace("-", " ").strip()
                        search_variations = [
                            search_name.title(),
                            search_name.upper(),
                            collection_address.replace("_", " "),
                        ]
                        
                        for search_term in search_variations:
                            try:
                                # Try simpler search query
                                search_params = {
                                    "query": {
                                        "grouping": {
                                            "groupKey": "collection",
                                        }
                                    },
                                    "limit": min(100, page_size * 2),
                                }
                                
                                # Search for NFTs with matching name in metadata
                                # Get some NFTs and check their grouping for collection
                                search_resp = await self._make_das_request("searchAssets", search_params)
                                search_items = search_resp.get("items", [])
                                
                                # Filter items by checking if metadata name/symbol matches
                                for item in search_items[:50]:  # Check first 50
                                    content = item.get("content", {})
                                    metadata = content.get("metadata", {})
                                    name = metadata.get("name", "").lower()
                                    symbol = metadata.get("symbol", "").lower()
                                    search_lower = search_term.lower()
                                    
                                    if search_lower in name or search_lower in symbol or collection_address.lower() in name:
                                        # Found potential match, extract collection address
                                        grouping = item.get("grouping", [])
                                        for g in grouping:
                                            group_key = g.get("groupKey") or g.get("group_key")
                                            if group_key == "collection":
                                                collection_addr_found = g.get("groupValue") or g.get("group_value")
                                                logger.info(f"Found collection address via name search: {collection_addr_found}")
                                                break
                                    
                                    if collection_addr_found:
                                        break
                                
                                if collection_addr_found:
                                    break
                            except Exception as search_err:
                                logger.debug(f"Search failed for '{search_term}': {search_err}")
                                continue
                    
                except Exception as resolve_error:
                    logger.error(f"Error resolving collection symbol: {resolve_error}")
                
                # If we found a collection address, use it to get all NFTs
                page_cursor = None
                has_more = False
                
                if collection_addr_found:
                    logger.info(f"Using resolved collection address: {collection_addr_found}")
                    # Store resolved address for later use
                    self._current_collection = collection_addr_found
                    # Use RPC getAssetsByGroup instead of DAS API
                    try:
                        rpc_params = {
                            "groupKey": "collection",
                            "groupValue": collection_addr_found,
                            "limit": min(page_size, 10000),
                        }
                        if cursor:
                            rpc_params["cursor"] = cursor
                        
                        rpc_response = await self._make_rpc_request("getAssetsByGroup", rpc_params)
                        items = rpc_response.get("items", [])
                        # Extract pagination cursor from RPC response
                        page_cursor = rpc_response.get("cursor")
                        total_returned = rpc_response.get("total", 0)
                        
                        logger.debug(f"Helius RPC Response: items={len(items)}, total={total_returned}, cursor={'Yes' if page_cursor else 'None'}, is_first_request={not cursor}, page_size={page_size}")
                        
                        # Same logic as above for actual total calculation
                        limit = min(page_size, 10000)
                        actual_total = None
                        
                        if not cursor:
                            # First request
                            if not page_cursor and len(items) < limit:
                                actual_total = len(items)
                                logger.debug(f"First request: No cursor + items < limit -> actual_total = len(items) = {actual_total}")
                            elif page_cursor:
                                actual_total = None
                                logger.debug(f"First request: Has cursor -> actual_total = None (will be determined via pagination)")
                            else:
                                actual_total = total_returned
                                logger.debug(f"First request: No cursor + items >= limit -> actual_total = total_returned = {actual_total}")
                        else:
                            actual_total = None
                            logger.debug(f"Subsequent request (has cursor) -> actual_total = None")
                        
                        # Store total for later retrieval (first request only)
                        # IMPORTANT: Don't use total_returned when there's a cursor - it's just the page size, not the actual total
                        if actual_total is not None and (not hasattr(self, '_collection_total') or self._collection_total is None):
                            self._collection_total = actual_total
                            self._last_total = actual_total
                            logger.info(f"Collection total determined (resolved): {actual_total}")
                        elif not hasattr(self, '_collection_total') or self._collection_total is None:
                            # Only use total_returned if there's NO cursor (meaning we got all items)
                            # If there's a cursor, total_returned is just the page size, not the real total
                            if total_returned > 0 and not page_cursor and len(items) < limit:
                                # No cursor + got less than limit = this is the actual total
                                self._collection_total = total_returned
                                self._last_total = total_returned
                                logger.info(f"Collection total determined (no cursor, got all): {total_returned}")
                            elif total_returned > 0 and not page_cursor:
                                # No cursor but got full page - total_returned might be accurate
                                self._collection_total = total_returned
                                self._last_total = total_returned
                                logger.info(f"Collection total estimate (no cursor, full page): {total_returned}")
                            else:
                                # Has cursor = can't determine total from first page, need to paginate
                                logger.debug(f"Helius RPC: Cannot determine total from first page (has cursor={bool(page_cursor)}, total_returned={total_returned}). Will need to count via pagination.")
                        # Check if there are more items
                        limit = min(page_size, 10000)
                        has_more = (
                            page_cursor is not None  # Cursor exists = more pages
                            or len(items) >= limit  # Got full page = likely more
                            or (total_returned > 0 and len(items) < total_returned)  # Total known and not reached
                        )
                    except Exception as rpc_err:
                        logger.debug(f"RPC getAssetsByGroup failed: {rpc_err}, trying DAS API")
                        # Fallback to DAS API
                        params = {
                            "groupKey": "collection",
                            "groupValue": collection_addr_found,
                            "limit": min(page_size, 10000),
                        }
                        if cursor:
                            params["page"] = cursor
                        response = await self._make_das_request("getAssetsByGroup", params)
                        items = response.get("items", [])
                        page_cursor = response.get("page") or response.get("cursor")
                        has_more = page_cursor is not None
                else:
                    logger.warning(f"Could not resolve collection symbol '{collection_address}' to Solana address via marketplaces.")
                    logger.warning("Tried: Magic Eden, Nintondo, Froggy.market")
                    logger.warning("Please provide the collection's Solana address directly, or a specific NFT mint address from the collection.")
            
            # Return response with proper pagination
            # Default values if not set
            if 'page_cursor' not in locals():
                page_cursor = None
            if 'has_more' not in locals():
                has_more = page_cursor is not None
            
            # Get total from stored value if available
            collection_total = None
            if hasattr(self, '_collection_total') and self._collection_total:
                collection_total = self._collection_total
            elif hasattr(self, '_last_total') and self._last_total:
                collection_total = self._last_total
            
            # Ensure items is a list
            if not isinstance(items, list):
                items = []
            
            # Enrich metadata for all NFTs
            enriched_items: List[Dict[str, Any]] = []
            for item in items:  # type: ignore[assignment, misc]
                try:
                    if isinstance(item, dict):
                        enriched_item = await self._enrich_nft_metadata(item)  # type: ignore[arg-type, misc]
                        enriched_items.append(enriched_item)  # type: ignore[arg-type, misc]
                    else:
                        enriched_items.append(item)  # type: ignore[arg-type, misc]
                except Exception as enrich_err:
                    logger.debug(f"Error enriching NFT metadata: {enrich_err}")
                    enriched_items.append(item)  # type: ignore[arg-type, misc]  # Use original if enrichment fails
            
            items_typed = cast(List[Any], enriched_items)  # type: ignore[assignment]
            
            return {
                "nfts": items_typed,
                "page": page_cursor,  # Return cursor for pagination
                "cursor": page_cursor,  # Alias for compatibility
                "totalCount": len(items_typed),  # Items in this response
                "total": collection_total,  # Total collection size (from API)
                "has_more": has_more,
            }
        except Exception as e:
            logger.error(f"Helius get_collection_nfts error: {e}")
            # Return empty result instead of raising to allow fallback chains
            return {
                "nfts": [],
                "page": None,
                "totalCount": 0,
            }
    
    async def _extract_collection_from_mint(self, token_mint: str) -> Optional[str]:
        """Extract collection address from a token mint address"""
        try:
            rpc_params = {"id": token_mint}
            token_response = await self._make_rpc_request("getAsset", [rpc_params])
            
            if isinstance(token_response, dict):  # type: ignore[redundant-expr]
                grouping = token_response.get("grouping", [])
                for g in grouping:
                    group_key = g.get("group_key") or g.get("groupKey")
                    if group_key == "collection":
                        return g.get("group_value") or g.get("groupValue")
        except Exception as token_err:
            logger.debug(f"Error extracting collection from mint {token_mint}: {token_err}")
        return None
    
    async def _enrich_nft_metadata(self, nft_item: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich NFT metadata if missing fields"""
        try:
            # Check if metadata is already complete
            content = nft_item.get("content", {})
            metadata = content.get("metadata", {})
            
            # If metadata is missing or incomplete, try to fetch it
            if not metadata or not metadata.get("name"):
                asset_id = nft_item.get("id")
                if asset_id:
                    try:
                        # Fetch full asset data
                        rpc_params = {"id": asset_id}
                        asset_response = await self._make_rpc_request("getAsset", [rpc_params])
                        
                        if isinstance(asset_response, dict):  # type: ignore[redundant-expr]
                            # Merge the enriched data
                            enriched_content = asset_response.get("content", {})
                            enriched_metadata = enriched_content.get("metadata", {})
                            
                            # Update metadata if we got better data
                            if enriched_metadata:
                                if not metadata:
                                    nft_item["content"] = enriched_content
                                else:
                                    # Merge metadata, preferring existing but filling gaps
                                    for key, value in enriched_metadata.items():
                                        if not metadata.get(key) and value:
                                            metadata[key] = value
                                    nft_item["content"]["metadata"] = metadata
                    except Exception as enrich_err:
                        logger.debug(f"Error enriching metadata for {asset_id}: {enrich_err}")
            
            return nft_item
        except Exception as e:
            logger.debug(f"Error in _enrich_nft_metadata: {e}")
            return nft_item
    
    async def parse_transaction(
        self,
        transaction_signature: str,
    ) -> Dict[str, Any]:
        """Parse Solana transaction for NFT transfers"""
        try:
            params = {
                "transactions": [transaction_signature],
            }
            
            response = await self._make_das_request("parseTransactions", params)
            
            # Response can be list or dict
            if isinstance(response, list) and response:  # type: ignore[redundant-expr]
                first_item = response[0]  # type: ignore[index]
                if isinstance(first_item, dict):  # type: ignore[redundant-expr]
                    return first_item  # type: ignore[return-value]
                return {}
            if isinstance(response, dict):  # type: ignore[redundant-expr]
                return response  # type: ignore[return-value]
            return {}
        except Exception as e:
            logger.error(f"Helius parse_transaction error: {e}")
            return {}

