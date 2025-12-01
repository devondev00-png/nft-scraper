"""
Configuration management for NFT Scout
"""

import os
from typing import List, Optional
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


@dataclass
class APIConfig:
    """API configuration for a provider"""
    keys: List[str]
    base_url: str
    rate_limit: int = 100  # requests per second
    
    def get_key(self, index: int = 0) -> str:
        """Get API key by index (for rotation)"""
        return self.keys[index % len(self.keys)]


@dataclass
class Config:
    """Main configuration class"""
    
    # Required fields first
    alchemy_api_keys: List[str]
    moralis_api_keys: List[str]
    helius_api_keys: List[str]
    quicknode_api_keys: List[str]
    
    # Fields with defaults
    alchemy_base_url: str = "https://{chain}-mainnet.g.alchemy.com"
    moralis_base_url: str = "https://deep-index.moralis.io/api/v2"
    helius_base_url: str = "https://api.helius.xyz"
    helius_rpc_url: str = "https://mainnet.helius-rpc.com"
    quicknode_base_url: str = "https://{chain}.quiknode.pro"
    quicknode_rpc_url: Optional[str] = None
    
    # Cache settings
    cache_ttl: int = 900  # 15 minutes
    cache_type: str = "memory"  # "memory" or "redis"
    redis_url: Optional[str] = None
    
    # Webhook settings
    webhook_secret: Optional[str] = None
    webhook_port: int = 8000
    
    # Request settings
    max_retries: int = 3
    timeout: int = 30
    batch_size: int = 100
    max_workers: int = 10  # Maximum concurrent workers for parallel API calls
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables"""
        
        def get_keys(key_name: str) -> List[str]:
            """Get multiple API keys (comma-separated)"""
            keys_str = os.getenv(key_name, "")
            if not keys_str:
                return []
            return [k.strip() for k in keys_str.split(",") if k.strip()]
        
        return cls(
            alchemy_api_keys=get_keys("ALCHEMY_API_KEY"),
            moralis_api_keys=get_keys("MORALIS_API_KEY"),
            helius_api_keys=get_keys("HELIUS_API_KEY"),
            quicknode_api_keys=get_keys("QUICKNODE_API_KEY"),
            helius_rpc_url=os.getenv("HELIUS_RPC_URL", "https://mainnet.helius-rpc.com"),
            quicknode_rpc_url=os.getenv("QUICKNODE_RPC_URL"),
            redis_url=os.getenv("REDIS_URL"),
            webhook_secret=os.getenv("WEBHOOK_SECRET"),
            webhook_port=int(os.getenv("WEBHOOK_PORT", "8000")),
            cache_ttl=int(os.getenv("CACHE_TTL", "900")),
            cache_type=os.getenv("CACHE_TYPE", "memory"),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            timeout=int(os.getenv("TIMEOUT", "30")),
            batch_size=int(os.getenv("BATCH_SIZE", "100")),
            max_workers=int(os.getenv("MAX_WORKERS", "10")),
        )
    
    def get_alchemy_config(self) -> APIConfig:
        """Get Alchemy API config"""
        if not self.alchemy_api_keys:
            raise ValueError("Alchemy API keys not configured")
        return APIConfig(
            keys=self.alchemy_api_keys,
            base_url=self.alchemy_base_url,
            rate_limit=330  # Alchemy's limit
        )
    
    def get_moralis_config(self) -> APIConfig:
        """Get Moralis API config"""
        if not self.moralis_api_keys:
            raise ValueError("Moralis API keys not configured")
        return APIConfig(
            keys=self.moralis_api_keys,
            base_url=self.moralis_base_url,
            rate_limit=200
        )
    
    def get_helius_config(self) -> APIConfig:
        """Get Helius API config"""
        if not self.helius_api_keys:
            raise ValueError("Helius API keys not configured")
        return APIConfig(
            keys=self.helius_api_keys,
            base_url=self.helius_base_url,
            rate_limit=1000
        )
    
    def get_quicknode_config(self) -> APIConfig:
        """Get QuickNode API config"""
        if not self.quicknode_api_keys:
            return None
        return APIConfig(
            keys=self.quicknode_api_keys,
            base_url=self.quicknode_base_url,
            rate_limit=100
        )


# Global config instance
config = Config.from_env()

