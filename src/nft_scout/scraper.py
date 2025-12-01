"""
Main NFT Scout scraper class
"""

import asyncio
import os
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from loguru import logger

from .config import Config, config
from .models import (
    NormalizedNFT,
    CollectionStats,
    TransferEvent,
    WalletNFTResponse,
    CollectionNFTResponse,
    Chain,
)
from .clients.alchemy import AlchemyClient
from .clients.moralis import MoralisClient
from .clients.helius import HeliusClient
from .clients.quicknode import QuickNodeClient
from .clients.magiceden import MagicEdenClient
from .clients.reservoir import ReservoirClient

try:
    from .clients.selenium_scraper import SeleniumScraper
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    SeleniumScraper = None
from .normalizer import Normalizer
from .storage import get_storage_adapter


class NFTScout:
    """Main NFT scraper class"""
    
    def __init__(self, config_instance: Optional[Config] = None):
        self.config = config_instance or config
        
        # Initialize clients
        self.alchemy = None
        self.moralis = None
        self.helius = None
        self.quicknode = None
        self.magiceden = None
        self.reservoir = None
        self.selenium_scraper = None
        
        # Initialize storage
        self.storage = get_storage_adapter(self.config)
        
        # Initialize normalizer
        self.normalizer = Normalizer()
        
        # Initialize worker semaphore for concurrency control
        self._worker_semaphore = asyncio.Semaphore(self.config.max_workers)
        
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize API clients"""
        try:
            alchemy_config = self.config.get_alchemy_config()
            self.alchemy = AlchemyClient(
                api_keys=alchemy_config.keys,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
            )
            logger.info("Alchemy client initialized")
        except Exception as e:
            logger.warning(f"Alchemy client not available: {e}")
        
        try:
            moralis_config = self.config.get_moralis_config()
            self.moralis = MoralisClient(
                api_keys=moralis_config.keys,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
            )
            logger.info("Moralis client initialized")
        except Exception as e:
            logger.warning(f"Moralis client not available: {e}")
        
        try:
            helius_config = self.config.get_helius_config()
            self.helius = HeliusClient(
                api_keys=helius_config.keys,
                rpc_url=self.config.helius_rpc_url,
                rate_limit=helius_config.rate_limit,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
            )
            logger.info("Helius client initialized")
        except Exception as e:
            logger.warning(f"Helius client not available: {e}")
        
        try:
            quicknode_config = self.config.get_quicknode_config()
            if quicknode_config:
                self.quicknode = QuickNodeClient(
                    api_keys=quicknode_config.keys,
                    timeout=self.config.timeout,
                    max_retries=self.config.max_retries,
                )
                logger.info("QuickNode client initialized")
        except Exception as e:
            logger.debug(f"QuickNode client not available: {e}")
        
        # Initialize Magic Eden client (with API key if available)
        try:
            import os
            magiceden_api_key = os.getenv("MAGICEDEN_PUBLIC_API_KEY") or os.getenv("MAGICEDEN_API_KEY")
            self.magiceden = MagicEdenClient(api_key=magiceden_api_key, rate_limit=1.0)
            if magiceden_api_key:
                logger.info("Magic Eden client initialized with API key")
            else:
                logger.info("Magic Eden client initialized (no API key)")
        except Exception as e:
            logger.warning(f"Magic Eden client not available: {e}")
        
        # Initialize Reservoir client (optional API key for higher limits)
        try:
            reservoir_api_key = os.getenv("RESERVOIR_API_KEY")
            self.reservoir = ReservoirClient(api_key=reservoir_api_key, rate_limit=2.0)
            logger.info("Reservoir client initialized")
        except Exception as e:
            logger.warning(f"Reservoir client not available: {e}")
        
        # Initialize Selenium scraper (fallback)
        if SELENIUM_AVAILABLE and SeleniumScraper:
            try:
                self.selenium_scraper = SeleniumScraper(headless=True)
                logger.info("Selenium scraper initialized")
            except Exception as e:
                logger.warning(f"Selenium scraper not available: {e}")
    
    def _get_client_for_chain(self, chain: Chain):
        """Get appropriate client for chain"""
        if chain == Chain.SOLANA:
            return self.helius
        else:
            # For EVM chains, prefer Alchemy, fallback to Moralis
            if self.alchemy:
                return self.alchemy
            elif self.moralis:
                return self.moralis
            else:
                return self.quicknode
    
    async def get_wallet_nfts(
        self,
        wallet_address: str,
        chains: Union[Chain, List[Chain]],
        include_transfers: bool = False,
        cursor: Optional[str] = None,
        page_size: int = 100,
    ) -> WalletNFTResponse:
        """Get all NFTs owned by a wallet across chains"""
        if isinstance(chains, Chain):
            chains = [chains]
        
        all_nfts: List[NormalizedNFT] = []
        total_count = 0
        last_response = {}
        
        # Fetch from all chains in parallel with worker limit
        async def fetch_chain_nfts(chain: Chain):
            async with self._worker_semaphore:
                try:
                    client = self._get_client_for_chain(chain)
                    if not client:
                        logger.warning(f"No client available for {chain}")
                        return [], None
                    
                    # Check cache first
                    cache_key = f"wallet:{wallet_address}:{chain.value}"
                    cached = await self.storage.get_cache(cache_key)
                    if cached:
                        logger.debug(f"Cache hit for {cache_key}")
                        return cached, None
                    
                    # Fetch from API
                    if chain == Chain.SOLANA:
                        response = await client.get_wallet_nfts(
                            wallet_address, chain.value, cursor, page_size
                        )
                        nfts_data = response.get("ownedNfts", [])
                    else:
                        response = await client.get_wallet_nfts(
                            wallet_address, chain.value, cursor, page_size
                        )
                        nfts_data = response.get("ownedNfts", [])
                    
                    # Normalize NFTs
                    source = "helius" if chain == Chain.SOLANA else ("alchemy" if isinstance(client, AlchemyClient) else "moralis")
                    normalized = [
                        self.normalizer.normalize_nft_from_source(nft_data, source, chain)
                        for nft_data in nfts_data
                    ]
                    
                    return normalized, response
                except Exception as e:
                    logger.error(f"Error fetching wallet NFTs from {chain}: {e}")
                    return [], None
        
        # Execute all chain fetches in parallel
        chain_results = await asyncio.gather(*[fetch_chain_nfts(chain) for chain in chains], return_exceptions=True)
        
        for i, result in enumerate(chain_results):
            if isinstance(result, Exception):
                logger.error(f"Error fetching from {chains[i]}: {result}")
                continue
            
            normalized, response = result
            if normalized:
                all_nfts.extend(normalized)
                total_count += len(normalized)
                
                # Cache results
                cache_key = f"wallet:{wallet_address}:{chains[i].value}"
                await self.storage.set_cache(cache_key, normalized, ttl=self.config.cache_ttl)
                
                logger.info(f"Fetched {len(normalized)} NFTs from {chains[i].value} for {wallet_address}")
            
            if response:
                last_response = response
        
        return WalletNFTResponse(
            wallet_address=wallet_address,
            chain=chains[0] if len(chains) == 1 else Chain.ETHEREUM,  # Default for multi-chain
            total_count=total_count,
            nfts=all_nfts,
            cursor=last_response.get("pageKey") or last_response.get("cursor") or last_response.get("page"),
            has_more=bool(last_response.get("pageKey") or last_response.get("cursor") or last_response.get("page")),
        )
    
    async def get_collection_nfts(
        self,
        contract_address: str,
        chain: Chain,
        cursor: Optional[str] = None,
        page_size: int = 100,
    ) -> CollectionNFTResponse:
        """Get all NFTs in a collection"""
        client = self._get_client_for_chain(chain)
        if not client:
            raise ValueError(f"No client available for {chain}")
        
        # Check cache - but only use it if we're not starting from the beginning (cursor exists)
        # This allows fresh scraping while still using cache for pagination
        cache_key = f"collection:{contract_address}:{chain.value}"
        cached = None
        # DISABLED: Cache interferes with pagination counting
        # Always fetch fresh data to ensure accurate counting
        # if cursor:  # Only use cache if we're paginating (not starting fresh)
        #     cached = await self.storage.get_cache(cache_key)
        #     if cached:
        #         logger.debug(f"Cache hit for {cache_key} during pagination - {len(cached)} NFTs in cache")
        #         # For pagination, we still need to fetch from API to get next page
        #         # Cache is not reliable for pagination, so continue to API fetch
        #         cached = None
        
        # Only use cache if no cursor (meaning we're starting fresh AND have cache)
        # BUT we should still fetch fresh to ensure we get the latest data
        # Commented out cache usage on first request to ensure fresh scraping
        # if not cursor:
        #     cached = await self.storage.get_cache(cache_key)
        #     if cached:
        #         logger.debug(f"Cache hit for {cache_key} - {len(cached)} NFTs in cache")
        #         # Even on cache hit, try to get total from Helius client if available
        #         collection_total = None
        #         if chain == Chain.SOLANA and isinstance(client, HeliusClient):
        #             helius_last_total = getattr(client, '_last_total', None)
        #             helius_collection_total = getattr(client, '_collection_total', None)
        #             logger.debug(f"Cache hit - Checking Helius totals: _last_total={helius_last_total}, _collection_total={helius_collection_total}")
        #             
        #             if hasattr(client, '_last_total') and client._last_total:
        #                 collection_total = client._last_total
        #                 logger.debug(f"Cache hit - Using _last_total: {collection_total}")
        #             elif hasattr(client, '_collection_total') and client._collection_total:
        #                 collection_total = client._collection_total
        #                 logger.debug(f"Cache hit - Using _collection_total: {collection_total}")
        #             else:
        #                 logger.debug(f"Cache hit - Both Helius totals are None")
        #         
        #         return CollectionNFTResponse(
        #             contract_address=contract_address,
        #             chain=chain,
        #             total_count=len(cached),
        #             total=collection_total,  # Include total if available from client
        #             nfts=cached,
        #             has_more=False,
        #         )
        
        # Fetch from API
        response = None
        if chain == Chain.SOLANA and isinstance(client, HeliusClient):
            response = await client.get_collection_nfts(
                contract_address, chain.value, cursor, page_size
            )
            nfts_data = response.get("nfts", [])
        elif isinstance(client, AlchemyClient):
            response = await client.get_contract_nfts(
                contract_address, chain.value, cursor, page_size
            )
            nfts_data = response.get("nfts", [])
            # Store raw response for debugging pageKey extraction
            if chain != Chain.SOLANA and len(nfts_data) == page_size:
                logger.debug(f"[Alchemy] Raw response keys: {list(response.keys())}, pageKey={response.get('pageKey')}, nextToken={response.get('nextToken')}")
        elif isinstance(client, MoralisClient):
            response = await client.get_contract_nfts(
                contract_address, chain.value, cursor, page_size
            )
            nfts_data = response.get("nfts", [])
        else:
            # Fallback: fetch one by one (slow)
            logger.warning("Batch fetching not available, fetching individually")
            nfts_data = []
            response = {"nfts": [], "pageKey": None, "page": None, "cursor": None}
        
        # Normalize NFTs
        source = "helius" if chain == Chain.SOLANA else ("alchemy" if isinstance(client, AlchemyClient) else "moralis")
        normalized = [
            self.normalizer.normalize_nft_from_source(nft_data, source, chain)
            for nft_data in nfts_data
        ]
        
        # Cache results
        await self.storage.set_cache(cache_key, normalized, ttl=self.config.cache_ttl)
        
        # Safe cursor extraction - response should always be a dict
        cursor = None
        has_more = False
        collection_total = None
        if isinstance(response, dict):
            # For Alchemy, check pageKey first, then nextToken, then page, then cursor
            cursor = response.get("pageKey") or response.get("nextToken") or response.get("page") or response.get("cursor")
            # Log what we found for debugging
            if chain != Chain.SOLANA and len(normalized) == page_size:
                logger.debug(f"[Alchemy] Response keys: {list(response.keys())}, pageKey={response.get('pageKey')}, nextToken={response.get('nextToken')}, cursor extracted={cursor}")
            
            # Check has_more field or infer from cursor and page size
            # If has_more is explicitly set, use it; otherwise infer:
            # - If cursor exists, there's likely more
            # - If we got a full page (reached limit), there's likely more
            if "has_more" in response:
                has_more = response.get("has_more", False)
            else:
                # Infer from cursor or page size
                has_more = cursor is not None or len(normalized) >= page_size
            
            # Extract total collection size if available (from Helius API)
            collection_total = response.get("total") or response.get("totalCount") or response.get("totalSupply")
            logger.debug(f"Extracting total from response: total={response.get('total')}, totalCount={response.get('totalCount')}, totalSupply={response.get('totalSupply')}, extracted={collection_total}")
            
            # Also check Helius client for stored total
            if not collection_total and chain == Chain.SOLANA and isinstance(client, HeliusClient):
                helius_last_total = getattr(client, '_last_total', None)
                helius_collection_total = getattr(client, '_collection_total', None)
                logger.debug(f"Response had no total, checking Helius client: _last_total={helius_last_total}, _collection_total={helius_collection_total}")
                
                if hasattr(client, '_last_total') and client._last_total:
                    collection_total = client._last_total
                    logger.debug(f"Using Helius _last_total: {collection_total}")
                elif hasattr(client, '_collection_total') and client._collection_total:
                    collection_total = client._collection_total
                    logger.debug(f"Using Helius _collection_total: {collection_total}")
                else:
                    logger.debug(f"Helius client also has no total - collection_total remains None")
        
        return CollectionNFTResponse(
            contract_address=contract_address,
            chain=chain,
            total_count=len(normalized),
            total=collection_total,  # Total collection size from API
            nfts=normalized,
            cursor=cursor,
            has_more=has_more,
        )
    
    async def get_collection_stats(
        self,
        contract_address: str,
        chain: Chain,
        magic_eden_symbol: Optional[str] = None,
        collection_url: Optional[str] = None,
    ) -> CollectionStats:
        """
        Get collection statistics by running ALL APIs in parallel
        Aggregates data from: Helius, Alchemy, Moralis, Magic Eden, Reservoir, Selenium
        """
        # Check cache
        cache_key = f"collection_stats:{contract_address}:{chain.value}"
        cached = await self.storage.get_cache(cache_key)
        if cached:
            return CollectionStats(**cached)
        
        # Prepare tasks for parallel execution
        tasks = {}
        results = {}
        
        client = self._get_client_for_chain(chain)
        
        # === SOLANA CHAIN ===
        if chain == Chain.SOLANA:
            # Task 1: Helius (base metadata)
            if isinstance(client, HeliusClient):
                tasks["helius"] = client.get_collection_metadata(contract_address, chain.value)
            
            # Task 2: Magic Eden stats
            if self.magiceden:
                me_symbol = magic_eden_symbol
                if not me_symbol and isinstance(contract_address, str):
                    if len(contract_address) < 32 or not all(c.isalnum() or c in '-_' for c in contract_address):
                        me_symbol = contract_address
                
                if me_symbol:
                    tasks["magiceden_stats"] = self.magiceden.get_collection_stats(me_symbol)
                    tasks["magiceden_info"] = self.magiceden.get_collection_info(me_symbol)
            
            # Task 3: Moralis (if available for Solana)
            if self.moralis:
                tasks["moralis"] = self.moralis.get_collection_metadata(contract_address, chain.value)
        
        # === EVM CHAINS ===
        else:
            # Task 1: Alchemy (primary for EVM)
            if isinstance(client, AlchemyClient):
                tasks["alchemy"] = client.get_collection_metadata(contract_address, chain.value)
            
            # Task 2: Moralis
            if self.moralis:
                tasks["moralis"] = self.moralis.get_collection_metadata(contract_address, chain.value)
            
            # Task 3: Reservoir (marketplace data)
            if self.reservoir:
                tasks["reservoir"] = self.reservoir.get_collection_stats(contract_address, chain.value)
            
            # Task 4: QuickNode (fallback)
            if self.quicknode:
                tasks["quicknode"] = self.quicknode.get_collection_metadata(contract_address, chain.value)
        
        # Task 5: Selenium scraper (if URL provided) - with timeout to prevent hanging
        # Note: Selenium already has timeout built in, but we add it here as safety
        if self.selenium_scraper and collection_url:
            tasks["selenium"] = self.selenium_scraper.get_collection_info_from_url(collection_url)
        
        # Execute ALL tasks in parallel with worker limit
        logger.info(f"Fetching collection stats from {len(tasks)} sources in parallel (max {self.config.max_workers} workers)...")
        if tasks:
            try:
                # Wrap tasks with semaphore to limit concurrency
                async def limited_task(task_key, task_coro):
                    async with self._worker_semaphore:
                        logger.debug(f"Starting {task_key} API call...")
                        try:
                            result = await task_coro
                            logger.debug(f"{task_key} API call completed. Result type: {type(result)}, Keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
                            return task_key, result
                        except Exception as e:
                            logger.debug(f"{task_key} API call failed: {type(e).__name__}: {str(e)}")
                            return task_key, Exception(f"{type(e).__name__}: {str(e)}")
                
                # Create limited tasks
                limited_tasks = [
                    limited_task(key, task_coro)
                    for key, task_coro in tasks.items()
                ]
                
                task_results = await asyncio.gather(*limited_tasks, return_exceptions=True)
                for result in task_results:
                    if isinstance(result, Exception):
                        logger.debug(f"Task result exception: {result}")
                        continue
                    if isinstance(result, tuple) and len(result) == 2:
                        key, value = result
                        if isinstance(value, Exception):
                            logger.debug(f"{key} fetch failed: {value}")
                        else:
                            results[key] = value
                            logger.debug(f"{key} result stored. Type: {type(value)}, Is empty: {not value if isinstance(value, (dict, list)) else value is None}")
                    else:
                        logger.debug(f"Unexpected task result format: {result}")
            except Exception as e:
                logger.error(f"Error in parallel task execution: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                # Continue with whatever results we got
        
        # === MERGE RESULTS ===
        stats = None
        
        if chain == Chain.SOLANA:
            # Start with Helius base data
            if "helius" in results:
                helius_data = results["helius"]
                stats = self.normalizer.normalize_helius_collection(helius_data, chain)
            
            # Merge Magic Eden data (marketplace stats are most accurate)
            if "magiceden_stats" in results or "magiceden_info" in results:
                me_stats_data = results.get("magiceden_stats", {})
                me_info_data = results.get("magiceden_info", {})
                
                if me_stats_data or me_info_data:
                    me_stats = self.normalizer.normalize_magiceden_collection(
                        me_stats_data,
                        me_info_data,
                        contract_address,
                        chain
                    )
                    
                    if stats:
                        # Merge: prefer Magic Eden for marketplace data, Helius for on-chain data
                        # IMPORTANT: Magic Eden total_supply is most accurate for Solana collections
                        if me_stats.total_supply:
                            stats.total_supply = me_stats.total_supply
                            logger.info(f"Using Magic Eden total_supply: {me_stats.total_supply:,}")
                        if me_stats.floor_price:
                            stats.floor_price = me_stats.floor_price
                        if me_stats.floor_price_currency:
                            stats.floor_price_currency = me_stats.floor_price_currency
                        if me_stats.total_volume:
                            stats.total_volume = me_stats.total_volume
                        if me_stats.volume_24h:
                            stats.volume_24h = me_stats.volume_24h
                        if me_stats.total_owners:
                            stats.total_owners = me_stats.total_owners
                        if me_stats.description:
                            stats.description = me_stats.description
                        if me_stats.image_url:
                            stats.image_url = me_stats.image_url
                        if me_stats.twitter:
                            stats.twitter = me_stats.twitter
                        if me_stats.discord:
                            stats.discord = me_stats.discord
                        if me_stats.website:
                            stats.website = me_stats.website
                        # ALWAYS prefer Magic Eden total_supply for Solana (most accurate for marketplace data)
                        if me_stats.total_supply:
                            old_total = stats.total_supply
                            stats.total_supply = me_stats.total_supply
                            if old_total and old_total != me_stats.total_supply:
                                logger.info(f"Replaced Helius total_supply ({old_total:,}) with Magic Eden total_supply ({me_stats.total_supply:,})")
                            elif not old_total:
                                logger.info(f"Using Magic Eden total_supply: {me_stats.total_supply:,}")
                        elif not stats.total_supply:
                            # Only use Helius if Magic Eden doesn't have it
                            logger.debug("Magic Eden has no total_supply, keeping Helius value if available")
                    else:
                        stats = me_stats
            
            # Merge Moralis data (fill gaps)
            if "moralis" in results and stats:
                try:
                    moralis_stats = self.normalizer.normalize_moralis_collection(
                        results["moralis"], chain
                    )
                    # Fill missing fields
                    if not stats.name and moralis_stats.name:
                        stats.name = moralis_stats.name
                    if not stats.description and moralis_stats.description:
                        stats.description = moralis_stats.description
                    if not stats.image_url and moralis_stats.image_url:
                        stats.image_url = moralis_stats.image_url
                except Exception as e:
                    logger.debug(f"Moralis normalization failed: {e}")
        
        else:  # EVM chains
            # For EVM chains, try Alchemy first for name (more reliable)
            # Start with Alchemy base data
            if "alchemy" in results:
                alchemy_data = results["alchemy"]
                stats = self.normalizer.normalize_alchemy_collection(alchemy_data, chain)
                # Alchemy contract metadata should have name
                if not stats.name and alchemy_data:
                    # Try to get name from Alchemy contract metadata
                    if isinstance(alchemy_data, dict):
                        stats.name = alchemy_data.get("name") or alchemy_data.get("contractMetadata", {}).get("name")
                        if stats.name:
                            logger.info(f"✅ Got name from Alchemy: {stats.name}")
                # If still no name, use contract address as fallback
                if not stats.name:
                    stats.name = contract_address
                    logger.warning(f"⚠️ No name found in Alchemy, using contract address")
            
            # Merge Reservoir data (best marketplace data for EVM)
            if "reservoir" in results and stats:
                reservoir_data = results["reservoir"]
                if reservoir_data:
                    reservoir_stats = self.normalizer.normalize_reservoir_collection(
                        reservoir_data,
                        contract_address,
                        chain
                    )
                    # Reservoir has the best marketplace data - use it
                    if reservoir_stats.floor_price:
                        stats.floor_price = reservoir_stats.floor_price
                    if reservoir_stats.floor_price_currency:
                        stats.floor_price_currency = reservoir_stats.floor_price_currency
                    if reservoir_stats.total_volume:
                        stats.total_volume = reservoir_stats.total_volume
                    if reservoir_stats.volume_24h:
                        stats.volume_24h = reservoir_stats.volume_24h
                    if reservoir_stats.volume_7d:
                        stats.volume_7d = reservoir_stats.volume_7d
                    if reservoir_stats.volume_30d:
                        stats.volume_30d = reservoir_stats.volume_30d
                    if reservoir_stats.sales_24h:
                        stats.sales_24h = reservoir_stats.sales_24h
                    if reservoir_stats.sales_7d:
                        stats.sales_7d = reservoir_stats.sales_7d
                    if reservoir_stats.sales_30d:
                        stats.sales_30d = reservoir_stats.sales_30d
                    if reservoir_stats.total_owners:
                        stats.total_owners = reservoir_stats.total_owners
                    if reservoir_stats.market_cap:
                        stats.market_cap = reservoir_stats.market_cap
                    if reservoir_stats.owners_percentage:
                        stats.owners_percentage = reservoir_stats.owners_percentage
                    # Fill metadata gaps
                    if not stats.description and reservoir_stats.description:
                        stats.description = reservoir_stats.description
                    if not stats.image_url and reservoir_stats.image_url:
                        stats.image_url = reservoir_stats.image_url
                    if not stats.twitter and reservoir_stats.twitter:
                        stats.twitter = reservoir_stats.twitter
                    if not stats.discord and reservoir_stats.discord:
                        stats.discord = reservoir_stats.discord
                    if not stats.website and reservoir_stats.website:
                        stats.website = reservoir_stats.website
                    # Use Reservoir's name if Alchemy didn't provide one, or if Reservoir has a better one
                    if reservoir_stats.name and (not stats.name or stats.name == contract_address):
                        stats.name = reservoir_stats.name
                        logger.info(f"✅ Using Reservoir name: {reservoir_stats.name}")
                    # ALWAYS use Reservoir's total_supply (most accurate for EVM)
                    if reservoir_stats.total_supply:
                        stats.total_supply = reservoir_stats.total_supply
                        logger.info(f"✅ Using Reservoir total_supply: {reservoir_stats.total_supply}")
                    else:
                        logger.warning(f"⚠️ Reservoir total_supply is None for {contract_address}")
            
            # Merge Moralis data (fill gaps)
            if "moralis" in results and stats:
                try:
                    moralis_stats = self.normalizer.normalize_moralis_collection(
                        results["moralis"], chain
                    )
                    # Fill missing fields
                    if not stats.name and moralis_stats.name:
                        stats.name = moralis_stats.name
                    if not stats.description and moralis_stats.description:
                        stats.description = moralis_stats.description
                    if not stats.image_url and moralis_stats.image_url:
                        stats.image_url = moralis_stats.image_url
                    if not stats.total_supply and moralis_stats.total_supply:
                        stats.total_supply = moralis_stats.total_supply
                except Exception as e:
                    logger.debug(f"Moralis normalization failed: {e}")
            
            # Merge QuickNode data (fallback)
            if "quicknode" in results and stats:
                try:
                    qn_stats = self.normalizer.normalize_quicknode_collection(
                        results["quicknode"], chain
                    )
                    # Fill any remaining gaps
                    if not stats.name and qn_stats.name:
                        stats.name = qn_stats.name
                    if not stats.description and qn_stats.description:
                        stats.description = qn_stats.description
                except Exception as e:
                    logger.debug(f"QuickNode normalization failed: {e}")
        
        # Merge Selenium data (final fallback, fills any remaining gaps)
        if "selenium" in results and stats:
            selenium_data = results["selenium"]
            if selenium_data:
                # Fill any missing critical fields
                if not stats.name and selenium_data.get("name"):
                    stats.name = selenium_data["name"]
                if not stats.description and selenium_data.get("description"):
                    stats.description = selenium_data["description"]
                if not stats.image_url and selenium_data.get("image_url"):
                    stats.image_url = selenium_data.get("image_url")
                if not stats.floor_price and selenium_data.get("floor_price"):
                    stats.floor_price = selenium_data.get("floor_price")
                if not stats.total_supply and selenium_data.get("total_supply"):
                    stats.total_supply = selenium_data.get("total_supply")
                if not stats.total_volume and selenium_data.get("total_volume"):
                    stats.total_volume = selenium_data.get("total_volume")
                if not stats.total_owners and selenium_data.get("total_owners"):
                    stats.total_owners = selenium_data.get("total_owners")
        
        # If we still don't have stats, create a minimal one
        if not stats:
            stats = CollectionStats(
                contract_address=contract_address,
                chain=chain,
                name=contract_address,
            )
        
        # Cache results
        await self.storage.set_cache(
            cache_key,
            stats.dict(),
            ttl=self.config.cache_ttl,
        )
        
        logger.info(f"✅ Aggregated collection stats from {len([k for k in results if results[k]])} sources")
        
        return stats
    
    async def get_recent_transfers(
        self,
        wallet_address: Optional[str] = None,
        contract_address: Optional[str] = None,
        chain: Chain = Chain.ETHEREUM,
        limit: int = 100,
    ) -> List[TransferEvent]:
        """Get recent NFT transfers"""
        client = self._get_client_for_chain(chain)
        if not client:
            raise ValueError(f"No client available for {chain}")
        
        transfers: List[TransferEvent] = []
        
        if wallet_address and isinstance(client, AlchemyClient):
            response = await client.get_transfers_for_wallet(wallet_address, chain.value)
            transfers_data = response.get("transfers", [])
            
            transfers = [
                self.normalizer.normalize_alchemy_transfer(t, chain)
                for t in transfers_data[:limit]
            ]
        
        return transfers
    
    async def stream_collection(
        self,
        contract_address: str,
        chain: Chain,
        callback: callable,
        interval: int = 60,
    ):
        """Stream collection updates in real-time"""
        logger.info(f"Starting to stream collection {contract_address} on {chain}")
        
        last_count = 0
        
        while True:
            try:
                response = await self.get_collection_nfts(contract_address, chain)
                current_count = response.total_count
                
                if current_count > last_count:
                    new_nfts = response.nfts[last_count:]
                    for nft in new_nfts:
                        await callback(nft)
                    last_count = current_count
                
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Error in stream_collection: {e}")
                await asyncio.sleep(interval)

