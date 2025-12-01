"""
Normalized Pydantic models for NFT data
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl, validator


class Chain(str, Enum):
    """Supported blockchain networks"""
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BASE = "base"
    SOLANA = "solana"
    
    @classmethod
    def from_string(cls, chain_str: str) -> "Chain":
        """Convert string to Chain enum"""
        chain_str = chain_str.lower().strip()
        mapping = {
            "eth": cls.ETHEREUM,
            "ethereum": cls.ETHEREUM,
            "polygon": cls.POLYGON,
            "matic": cls.POLYGON,
            "arbitrum": cls.ARBITRUM,
            "arb": cls.ARBITRUM,
            "optimism": cls.OPTIMISM,
            "op": cls.OPTIMISM,
            "base": cls.BASE,
            "solana": cls.SOLANA,
            "sol": cls.SOLANA,
        }
        return mapping.get(chain_str, cls.ETHEREUM)


class Trait(BaseModel):
    """NFT trait/attribute"""
    trait_type: str
    value: Union[str, int, float]
    display_type: Optional[str] = None


class NormalizedNFT(BaseModel):
    """Normalized NFT model across all chains"""
    
    # Core identifiers
    token_id: str
    contract_address: str
    chain: Chain
    name: Optional[str] = None
    description: Optional[str] = None
    
    # Media
    image_url: Optional[HttpUrl] = None
    animation_url: Optional[HttpUrl] = None
    external_url: Optional[HttpUrl] = None
    
    # Ownership
    owner_address: Optional[str] = None
    owner_ens: Optional[str] = None
    
    # Metadata
    raw_metadata: Optional[Dict[str, Any]] = None
    attributes: List[Trait] = Field(default_factory=list)
    
    # Collection info
    collection_name: Optional[str] = None
    collection_slug: Optional[str] = None
    collection_verified: bool = False
    
    # Token standard
    token_standard: Optional[str] = None  # ERC721, ERC1155, SPL, etc.
    
    # Pricing (if available)
    floor_price: Optional[float] = None
    last_sale_price: Optional[float] = None
    last_sale_currency: Optional[str] = None
    
    # Dates
    minted_at: Optional[datetime] = None
    last_transferred_at: Optional[datetime] = None
    
    # Rarity (if available)
    rarity_rank: Optional[int] = None
    rarity_score: Optional[float] = None
    
    # Additional data
    metadata_cached: bool = False
    metadata_cache_date: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            HttpUrl: str,
        }
    
    def dict(self, **kwargs):
        """Override dict to ensure HttpUrl fields are converted to strings"""
        data = super().dict(**kwargs)
        # Convert HttpUrl objects to strings
        url_fields = ["image_url", "animation_url", "external_url"]
        for key in url_fields:
            if key in data and data[key] is not None:
                if not isinstance(data[key], str):
                    data[key] = str(data[key])
        return data
    
    def model_dump(self, **kwargs):
        """Pydantic v2 method - convert HttpUrl to strings"""
        if hasattr(super(), 'model_dump'):
            data = super().model_dump(**kwargs)
        else:
            data = self.dict(**kwargs)
        # Convert HttpUrl objects to strings
        url_fields = ["image_url", "animation_url", "external_url"]
        for key in url_fields:
            if key in data and data[key] is not None:
                if not isinstance(data[key], str):
                    data[key] = str(data[key])
        return data


class CollectionStats(BaseModel):
    """Collection statistics"""
    
    contract_address: str
    chain: Chain
    name: Optional[str] = None
    symbol: Optional[str] = None
    description: Optional[str] = None
    
    # Counts
    total_supply: Optional[int] = None
    total_owners: Optional[int] = None
    
    # Pricing
    floor_price: Optional[float] = None
    floor_price_currency: str = "ETH"
    average_price: Optional[float] = None
    
    # Volume
    total_volume: Optional[float] = None
    volume_24h: Optional[float] = None
    volume_7d: Optional[float] = None
    volume_30d: Optional[float] = None
    
    # Sales
    sales_24h: Optional[int] = None
    sales_7d: Optional[int] = None
    sales_30d: Optional[int] = None
    
    # Market data
    market_cap: Optional[float] = None
    owners_percentage: Optional[float] = None  # unique owners / total supply
    
    # Verification
    verified: bool = False
    
    # Social links
    website: Optional[HttpUrl] = None
    twitter: Optional[str] = None
    discord: Optional[str] = None
    
    # Image
    image_url: Optional[HttpUrl] = None
    banner_url: Optional[HttpUrl] = None
    
    # Dates
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            HttpUrl: str,
        }
    
    def dict(self, **kwargs):
        """Override dict to ensure HttpUrl fields are converted to strings"""
        data = super().dict(**kwargs)
        # Convert HttpUrl objects to strings
        for key in ["image_url", "banner_url", "website"]:
            if key in data and data[key] is not None:
                data[key] = str(data[key])
        return data


class TransferEvent(BaseModel):
    """NFT transfer/sale event"""
    
    transaction_hash: str
    chain: Chain
    contract_address: str
    token_id: str
    
    # Parties
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    
    # Transfer type
    transfer_type: str = "transfer"  # transfer, sale, mint, burn
    
    # Pricing (for sales)
    price: Optional[float] = None
    price_currency: Optional[str] = None
    marketplace: Optional[str] = None
    
    # Dates
    block_number: Optional[int] = None
    block_timestamp: datetime
    
    # Token info (cached)
    token_name: Optional[str] = None
    token_image: Optional[HttpUrl] = None
    
    # Additional data
    raw_data: Optional[Dict[str, Any]] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            HttpUrl: str,
        }
    
    def dict(self, **kwargs):
        """Override dict to ensure HttpUrl fields are converted to strings"""
        data = super().dict(**kwargs)
        # Convert HttpUrl objects to strings
        for key in ["token_image", "token_image_url"]:
            if key in data and data[key] is not None:
                data[key] = str(data[key])
        return data


class WalletNFTResponse(BaseModel):
    """Response for wallet NFTs query"""
    wallet_address: str
    chain: Chain
    total_count: int
    nfts: List[NormalizedNFT]
    cursor: Optional[str] = None  # For pagination
    has_more: bool = False


class CollectionNFTResponse(BaseModel):
    """Response for collection NFTs query"""
    contract_address: str
    chain: Chain
    total_count: int  # Count of NFTs in this response
    total: Optional[int] = None  # Total collection size (from API)
    nfts: List[NormalizedNFT]
    cursor: Optional[str] = None
    has_more: bool = False

