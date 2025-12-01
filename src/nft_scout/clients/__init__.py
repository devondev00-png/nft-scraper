"""API clients for NFT data providers"""

from .alchemy import AlchemyClient
from .moralis import MoralisClient
from .helius import HeliusClient
from .quicknode import QuickNodeClient
from .magiceden import MagicEdenClient
from .reservoir import ReservoirClient

try:
    from .selenium_scraper import SeleniumScraper
    __all__ = ["AlchemyClient", "MoralisClient", "HeliusClient", "QuickNodeClient", "MagicEdenClient", "ReservoirClient", "SeleniumScraper"]
except ImportError:
    __all__ = ["AlchemyClient", "MoralisClient", "HeliusClient", "QuickNodeClient", "MagicEdenClient", "ReservoirClient"]

