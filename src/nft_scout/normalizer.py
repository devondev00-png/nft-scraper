"""Normalize API responses to unified models"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

from pydantic import HttpUrl as PydanticHttpUrl
from loguru import logger
from .models import (
    NormalizedNFT,
    CollectionStats,
    TransferEvent,
    Trait,
    Chain,
)


def convert_ipfs_to_http(ipfs_url: str) -> Optional[str]:
    """Convert IPFS URL to HTTP gateway URL with reliable gateway"""
    if not ipfs_url or not isinstance(ipfs_url, str):
        return None
    
    # Already HTTP/HTTPS
    if ipfs_url.startswith(("http://", "https://")):
        return ipfs_url
    
    # IPFS protocol - preserve full path after hash
    if ipfs_url.startswith("ipfs://"):
        # Remove ipfs:// prefix, keep everything else (hash + path)
        ipfs_path = ipfs_url.replace("ipfs://", "").lstrip("/")
        # Use Cloudflare gateway (most reliable) as primary
        return f"https://cloudflare-ipfs.com/ipfs/{ipfs_path}"
    
    # If it's just an IPFS hash (Qm...) or hash with path
    if ipfs_url.startswith("Qm") and len(ipfs_url.split("/")[0]) > 40:
        return f"https://cloudflare-ipfs.com/ipfs/{ipfs_url}"
    
    return ipfs_url


class Normalizer:
    """Convert API-specific responses to normalized models"""
    
    @staticmethod
    def normalize_alchemy_nft(data: Dict[str, Any], chain: Chain) -> NormalizedNFT:
        """Normalize Alchemy NFT response"""
        contract = data.get("contract", {})
        metadata = data.get("metadata", {})
        
        # Extract traits
        attributes = []
        if "attributes" in metadata:
            for attr in metadata.get("attributes", []):
                attributes.append(Trait(
                    trait_type=attr.get("trait_type", ""),
                    value=attr.get("value"),
                    display_type=attr.get("display_type"),
                ))
        
        # Convert IPFS URLs to HTTP
        image_url_raw = metadata.get("image")
        image_url = None
        if image_url_raw:
            image_url_http = convert_ipfs_to_http(image_url_raw)
            if image_url_http:
                try:
                    image_url = PydanticHttpUrl(image_url_http)
                except Exception:
                    # Invalid URL format, skip
                    pass
        
        animation_url_raw = metadata.get("animation_url")
        animation_url = None
        if animation_url_raw:
            animation_url_http = convert_ipfs_to_http(animation_url_raw)
            if animation_url_http:
                try:
                    animation_url = PydanticHttpUrl(animation_url_http)
                except Exception:
                    # Invalid URL format, skip
                    pass
        
        external_url_raw = metadata.get("external_url")
        external_url = None
        if external_url_raw:
            external_url_http = convert_ipfs_to_http(external_url_raw)
            if external_url_http:
                try:
                    external_url = PydanticHttpUrl(external_url_http)
                except Exception:
                    # Invalid URL format, skip
                    pass
        
        return NormalizedNFT(
            token_id=str(data.get("id", {}).get("tokenId", "")),
            contract_address=contract.get("address", ""),
            chain=chain,
            name=metadata.get("name"),
            description=metadata.get("description"),
            image_url=image_url,
            animation_url=animation_url,
            external_url=external_url,
            raw_metadata=metadata,
            attributes=attributes,
            collection_name=contract.get("name"),
            token_standard=data.get("id", {}).get("tokenMetadata", {}).get("tokenType"),
            owner_address=data.get("owners", [None])[0] if data.get("owners") else None,
        )
    
    @staticmethod
    def normalize_helius_nft(data: Dict[str, Any], chain: Chain = Chain.SOLANA) -> NormalizedNFT:
        """Normalize Helius/Solana NFT response"""
        content = data.get("content", {})
        metadata = content.get("metadata", {})
        files = content.get("files", [])
        
        # Extract traits
        attributes = []
        if "attributes" in metadata:
            for attr in metadata.get("attributes", []):
                attributes.append(Trait(
                    trait_type=attr.get("trait_type", ""),
                    value=attr.get("value"),
                    display_type=attr.get("display_type"),
                ))
        
        # Get image from files or metadata - check multiple sources
        image_url = None
        if files and len(files) > 0:
            # Prefer CDN URI if available, otherwise regular URI
            first_file = files[0]
            image_url = first_file.get("cdn_uri") or first_file.get("uri")
        elif metadata.get("image"):
            image_url = metadata.get("image")
        
        # Also check content.links for image
        if not image_url:
            links = content.get("links", {})
            if links.get("image"):
                image_url = links.get("image")
        
        # Extract collection info
        # Helius DAS API uses camelCase: grouping array with groupKey, groupValue
        group = data.get("grouping", [])
        collection_address = None
        collection_name = None
        if group:
            for g in group:
                # Check both snake_case and camelCase for compatibility
                group_key = g.get("groupKey") or g.get("group_key")
                if group_key == "collection":
                    collection_address = g.get("groupValue") or g.get("group_value")
                    # Collection metadata might be nested differently
                    collection_meta = g.get("collectionMetadata") or g.get("collection_metadata") or {}
                    collection_name = collection_meta.get("name") if isinstance(collection_meta, dict) else None
        
        # Extract token ID - could be in id field or as part of asset ID
        token_id = data.get("id", "")
        if not token_id:
            # Try to extract from content metadata name/tokenId
            token_id = metadata.get("tokenId") or metadata.get("name") or ""
        
        # Extract owner - check ownership object (camelCase)
        ownership = data.get("ownership", {})
        owner_address = ownership.get("owner") or ownership.get("ownerAddress") if ownership else None
        
        return NormalizedNFT(
            token_id=str(token_id),
            contract_address=collection_address or data.get("id", ""),
            chain=chain,
            name=metadata.get("name"),
            description=metadata.get("description"),
            image_url=image_url,
            animation_url=content.get("animation_url") or metadata.get("animation_url"),
            external_url=metadata.get("external_url"),
            raw_metadata=data,
            attributes=attributes,
            collection_name=collection_name or metadata.get("name"),
            token_standard=data.get("interface", "SPL"),
            owner_address=owner_address,
        )
    
    @staticmethod
    def normalize_moralis_nft(data: Dict[str, Any], chain: Chain) -> NormalizedNFT:
        """Normalize Moralis NFT response"""
        metadata = data.get("metadata", {})
        if isinstance(metadata, str):
            import json
            try:
                metadata = json.loads(metadata) if metadata else {}
            except Exception:
                # Field not found or invalid, continue
                metadata = {}
        
        # Extract traits
        attributes = []
        if "attributes" in metadata:
            for attr in metadata.get("attributes", []):
                attributes.append(Trait(
                    trait_type=attr.get("trait_type", ""),
                    value=attr.get("value"),
                    display_type=attr.get("display_type"),
                ))
        
        return NormalizedNFT(
            token_id=data.get("token_id", ""),
            contract_address=data.get("token_address", ""),
            chain=chain,
            name=metadata.get("name") or data.get("name"),
            description=metadata.get("description"),
            image_url=metadata.get("image") if metadata.get("image") else None,
            animation_url=metadata.get("animation_url"),
            external_url=metadata.get("external_url"),
            raw_metadata=metadata,
            attributes=attributes,
            collection_name=data.get("name"),
            token_standard=data.get("contract_type"),
        )
    
    @staticmethod
    def normalize_alchemy_collection(data: Dict[str, Any], chain: Chain) -> CollectionStats:
        """Normalize Alchemy collection response"""
        from loguru import logger
        
        # Alchemy getContractMetadata returns name in different locations
        collection_name = None
        if isinstance(data, dict):
            # Check multiple locations for name
            collection_name = (data.get("name") or 
                             data.get("contractMetadata", {}).get("name") or
                             data.get("openSea", {}).get("collectionName") or
                             data.get("openSea", {}).get("name"))
            
            if collection_name:
                logger.debug(f"Found Alchemy name: {collection_name}")
            else:
                logger.debug(f"No name in Alchemy data. Keys: {list(data.keys())}")
        
        return CollectionStats(
            contract_address=data.get("address", ""),
            chain=chain,
            name=collection_name,
            symbol=data.get("symbol") or data.get("contractMetadata", {}).get("symbol"),
            verified=data.get("openSea", {}).get("safelistRequestStatus") == "verified",
        )
    
    @staticmethod
    def normalize_helius_collection(data: Dict[str, Any], chain: Chain = Chain.SOLANA) -> CollectionStats:
        """Normalize Helius collection response"""
        return CollectionStats(
            contract_address=data.get("collection_address", ""),
            chain=chain,
            name=data.get("name"),
            description=data.get("description"),
            image_url=data.get("image"),
            total_supply=data.get("totalSupply"),
        )
    
    @staticmethod
    def normalize_magiceden_collection(stats_data: Dict[str, Any], info_data: Dict[str, Any], contract_address: str, chain: Chain = Chain.SOLANA) -> CollectionStats:
        """Normalize Magic Eden collection response"""
        # Extract floor price (in SOL)
        floor_price = None
        if stats_data.get("floorPrice"):
            floor_price = float(stats_data["floorPrice"]) / 1e9  # Convert lamports to SOL
        
        # Extract volume (in SOL) - Magic Eden uses volumeAll for total volume
        volume_24h = None
        volume_7d = None
        volume_30d = None
        total_volume = None
        if stats_data.get("volume24h"):
            volume_24h = float(stats_data["volume24h"]) / 1e9
        if stats_data.get("volume7d"):
            volume_7d = float(stats_data["volume7d"]) / 1e9
        if stats_data.get("volume30d"):
            volume_30d = float(stats_data["volume30d"]) / 1e9
        if stats_data.get("volumeAll"):
            total_volume = float(stats_data["volumeAll"]) / 1e9
            # If we don't have specific volumes, use total as 30d estimate
            if not volume_30d:
                volume_30d = total_volume
        
        # Extract average price (24hr)
        average_price = None
        if stats_data.get("avgPrice24hr"):
            average_price = float(stats_data["avgPrice24hr"]) / 1e9  # Convert lamports to SOL
        
        # Extract sales (Magic Eden doesn't always provide these in stats)
        sales_24h = stats_data.get("sales24h")
        sales_7d = stats_data.get("sales7d")
        sales_30d = stats_data.get("sales30d")
        
        # Extract social links from info_data
        twitter = None
        discord = None
        website = None
        if info_data:
            twitter = info_data.get("twitter")
            discord = info_data.get("discord")
            website_str = info_data.get("website")
            if website_str:
                try:
                    website = PydanticHttpUrl(website_str)
                except Exception:
                    website = None
        
        # Extract image URL
        image_url = None
        if info_data and info_data.get("image"):
            try:
                image_url = PydanticHttpUrl(info_data["image"])
            except Exception:
                pass
        
        # Extract total supply - check multiple sources with more comprehensive field checking
        total_supply = None
        
        # Priority 1: Check stats_data (most reliable for Magic Eden)
        for field in ["totalSupply", "supply", "items", "tokenCount", "totalItems", "itemCount", "count", "total"]:
            if stats_data.get(field):
                try:
                    total_supply = int(stats_data[field])
                    logger.debug(f"Magic Eden: Found total_supply from stats_data.{field} = {total_supply}")
                    break
                except (ValueError, TypeError):
                    continue
        
        # Priority 2: Check info_data (collection metadata)
        if not total_supply and info_data:
            for field in ["totalSupply", "supply", "items", "tokenCount", "totalItems", "itemCount", "count", "total", "numberOfItems"]:
                if info_data.get(field):
                    try:
                        total_supply = int(info_data[field])
                        logger.debug(f"Magic Eden: Found total_supply from info_data.{field} = {total_supply}")
                        break
                    except (ValueError, TypeError):
                        continue
        
        # Priority 3: Check nested structures
        if not total_supply:
            # Check stats_data nested
            if stats_data.get("collection") and isinstance(stats_data["collection"], dict):
                for field in ["totalSupply", "supply", "items", "tokenCount"]:
                    if stats_data["collection"].get(field):
                        try:
                            total_supply = int(stats_data["collection"][field])
                            logger.debug(f"Magic Eden: Found total_supply from stats_data.collection.{field} = {total_supply}")
                            break
                        except (ValueError, TypeError):
                            continue
            
            # Check info_data nested
            if not total_supply and info_data and info_data.get("collection") and isinstance(info_data["collection"], dict):
                for field in ["totalSupply", "supply", "items", "tokenCount"]:
                    if info_data["collection"].get(field):
                        try:
                            total_supply = int(info_data["collection"][field])
                            logger.debug(f"Magic Eden: Found total_supply from info_data.collection.{field} = {total_supply}")
                            break
                        except (ValueError, TypeError):
                            continue
        
        return CollectionStats(
            contract_address=contract_address,
            chain=chain,
            name=info_data.get("name") if info_data else None,
            description=info_data.get("description") if info_data else None,
            image_url=image_url,
            total_supply=total_supply,
            floor_price=floor_price,
            floor_price_currency="SOL",
            average_price=average_price,
            volume_24h=volume_24h,
            volume_7d=volume_7d,
            volume_30d=volume_30d,
            total_volume=total_volume or volume_30d,  # Use total_volume or 30d as fallback
            sales_24h=sales_24h,
            sales_7d=sales_7d,
            sales_30d=sales_30d,
            twitter=twitter,
            discord=discord,
            website=website,
            verified=info_data.get("isVerified", False) if info_data else False,
        )
    
    @staticmethod
    def normalize_moralis_collection(data: Dict[str, Any], chain: Chain) -> CollectionStats:
        """Normalize Moralis collection response"""
        # Moralis metadata endpoint doesn't provide total_supply
        # contract_type is "ERC721" or "ERC1155", NOT total_supply
        total_supply = None
        # Try to extract from various fields if available
        if "total_supply" in data:
            try:
                total_supply = int(data["total_supply"])
            except (ValueError, TypeError):
                pass
        
        return CollectionStats(
            contract_address=data.get("token_address", ""),
            chain=chain,
            name=data.get("name"),
            symbol=data.get("symbol"),
            description=data.get("metadata", {}).get("description") if isinstance(data.get("metadata"), dict) else None,
            image_url=data.get("metadata", {}).get("image") if isinstance(data.get("metadata"), dict) else None,
            total_supply=total_supply,  # Will be None - needs to be counted separately
        )
    
    @staticmethod
    def normalize_quicknode_collection(data: Dict[str, Any], chain: Chain) -> CollectionStats:
        """Normalize QuickNode collection response"""
        return CollectionStats(
            contract_address=data.get("address", ""),
            chain=chain,
            name=data.get("name"),
            symbol=data.get("symbol"),
            description=data.get("description"),
            image_url=data.get("image"),
            total_supply=data.get("totalSupply"),
        )
    
    @staticmethod
    def normalize_reservoir_collection(data: Dict[str, Any], contract_address: str, chain: Chain) -> CollectionStats:
        """Normalize Reservoir collection response"""
        # DEBUG: Log the raw data structure
        from loguru import logger
        logger.debug(f"Reservoir data keys: {list(data.keys())}")
        logger.debug(f"Reservoir collection keys: {list(data.get('collection', {}).keys())}")
        logger.debug(f"Reservoir metadata keys: {list(data.get('collection', {}).get('metadata', {}).keys())}")
        
        # Extract floor price
        floor_price = None
        currency = "ETH"  # Default currency
        floor_ask = data.get("floorAsk", {})
        if floor_ask.get("price"):
            # Price is in wei/smallest unit, need to convert
            price_raw = floor_ask.get("price", {})
            price_amount = price_raw.get("amount", {}).get("raw")
            if price_amount:
                # Convert from raw amount to ETH (divide by 1e18)
                floor_price = float(price_amount) / 1e18
                # Get currency
                currency = price_raw.get("currency", {}).get("symbol", "ETH")
        
        # Extract volume
        volume_24h = data.get("volume", {}).get("1day")
        volume_7d = data.get("volume", {}).get("7day")
        volume_30d = data.get("volume", {}).get("30day")
        total_volume = data.get("volume", {}).get("allTime")
        
        # Extract sales
        sales_24h = data.get("salesCount", {}).get("1day")
        sales_7d = data.get("salesCount", {}).get("7day")
        sales_30d = data.get("salesCount", {}).get("30day")
        
        # Extract owners
        total_owners = data.get("ownerCount")
        
        # Extract metadata - check multiple locations
        collection_data = data.get("collection", {})
        metadata = collection_data.get("metadata", {})
        
        # Also check if metadata is at top level
        if not metadata and data.get("metadata"):
            metadata = data.get("metadata", {})
        
        # Extract image URL
        image_url = None
        image_str = metadata.get("imageUrl") or metadata.get("image")
        if image_str:
            try:
                image_url = PydanticHttpUrl(image_str)
            except Exception:
                pass
        
        # Extract website URL
        website = None
        website_str = metadata.get("website") or collection_data.get("website")
        if website_str:
            try:
                website = PydanticHttpUrl(website_str)
            except Exception:
                pass
        
        # Extract total supply - check multiple sources with comprehensive search
        total_supply = None
        # Priority 1: tokenCount in multiple locations
        if data.get("tokenCount"):
            try:
                total_supply = int(data["tokenCount"])
            except (ValueError, TypeError):
                pass
        elif collection_data.get("tokenCount"):
            try:
                total_supply = int(collection_data["tokenCount"])
            except (ValueError, TypeError):
                pass
        # Priority 2: supply field
        elif data.get("supply"):
            try:
                total_supply = int(data["supply"])
            except (ValueError, TypeError):
                pass
        elif collection_data.get("supply"):
            try:
                total_supply = int(collection_data["supply"])
            except (ValueError, TypeError):
                pass
        # Priority 3: Check nested locations
        elif data.get("collection", {}).get("tokenCount"):
            try:
                total_supply = int(data["collection"]["tokenCount"])
            except (ValueError, TypeError):
                pass
        # Priority 4: Check metadata for supply info
        elif metadata.get("tokenCount"):
            try:
                total_supply = int(metadata["tokenCount"])
            except (ValueError, TypeError):
                pass
        elif metadata.get("supply"):
            try:
                total_supply = int(metadata["supply"])
            except (ValueError, TypeError):
                pass
        # Priority 5: Check collection metadata
        elif collection_data.get("metadata", {}).get("tokenCount"):
            try:
                total_supply = int(collection_data["metadata"]["tokenCount"])
            except (ValueError, TypeError):
                pass
        
        # Calculate market cap if we have floor price
        market_cap = None
        if floor_price and total_supply:
            market_cap = floor_price * total_supply
        
        # Calculate owners percentage
        owners_percentage = None
        if total_owners and total_supply:
            owners_percentage = (total_owners / total_supply) * 100
        
        # Extract name - check multiple sources with priority
        collection_name = None
        # Priority 1: metadata.name (most common)
        if metadata and metadata.get("name"):
            collection_name = metadata.get("name")
            logger.debug(f"Found name in metadata.name: {collection_name}")
        # Priority 2: collection.name
        elif collection_data and collection_data.get("name"):
            collection_name = collection_data.get("name")
            logger.debug(f"Found name in collection.name: {collection_name}")
        # Priority 3: Check top-level name
        elif data.get("name"):
            collection_name = data.get("name")
            logger.debug(f"Found name in top-level name: {collection_name}")
        # Priority 4: Check metadata.name in different location
        elif collection_data and collection_data.get("metadata", {}).get("name"):
            collection_name = collection_data.get("metadata", {}).get("name")
            logger.debug(f"Found name in collection.metadata.name: {collection_name}")
        # Priority 5: Check collectionName field
        elif data.get("collectionName"):
            collection_name = data.get("collectionName")
            logger.debug(f"Found name in collectionName: {collection_name}")
        elif collection_data and collection_data.get("collectionName"):
            collection_name = collection_data.get("collectionName")
            logger.debug(f"Found name in collection.collectionName: {collection_name}")
        
        if not collection_name:
            logger.warning(f"No collection name found in Reservoir data for {contract_address}")
            logger.debug(f"Available keys in data: {list(data.keys())}")
            logger.debug(f"Available keys in collection_data: {list(collection_data.keys()) if collection_data else 'None'}")
            logger.debug(f"Available keys in metadata: {list(metadata.keys()) if metadata else 'None'}")
        
        return CollectionStats(
            contract_address=contract_address,
            chain=chain,
            name=collection_name,  # Use extracted name, not contract address
            description=metadata.get("description") or collection_data.get("description"),
            image_url=image_url,
            total_supply=total_supply,
            total_owners=total_owners,
            floor_price=floor_price,
            floor_price_currency=currency if floor_price else "ETH",
            total_volume=total_volume,
            volume_24h=volume_24h,
            volume_7d=volume_7d,
            volume_30d=volume_30d,
            sales_24h=sales_24h,
            sales_7d=sales_7d,
            sales_30d=sales_30d,
            market_cap=market_cap,
            owners_percentage=owners_percentage,
            website=website,
            twitter=metadata.get("twitter"),
            discord=metadata.get("discord"),
            verified=collection_data.get("isSpam") == False,
        )
    
    @staticmethod
    def normalize_alchemy_transfer(data: Dict[str, Any], chain: Chain) -> TransferEvent:
        """Normalize Alchemy transfer event"""
        block_timestamp = None
        if data.get("blockNum"):
            # Convert hex block number to timestamp (simplified)
            block_timestamp = datetime.now()  # Would need actual block time lookup
        
        return TransferEvent(
            transaction_hash=data.get("hash", ""),
            chain=chain,
            contract_address=data.get("asset", ""),
            token_id=str(data.get("tokenId", "")),
            from_address=data.get("from", ""),
            to_address=data.get("to", ""),
            transfer_type="transfer",
            block_number=int(data.get("blockNum", "0x0"), 16) if data.get("blockNum") else None,
            block_timestamp=block_timestamp or datetime.now(),
            raw_data=data,
        )
    
    @staticmethod
    def normalize_nft_from_source(
        data: Dict[str, Any],
        source: str,
        chain: Chain,
    ) -> NormalizedNFT:
        """Normalize NFT from any source"""
        if source == "alchemy":
            return Normalizer.normalize_alchemy_nft(data, chain)
        elif source == "helius":
            return Normalizer.normalize_helius_nft(data, chain)
        elif source == "moralis":
            return Normalizer.normalize_moralis_nft(data, chain)
        else:
            raise ValueError(f"Unknown source: {source}")

