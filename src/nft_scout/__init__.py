"""
NFT Scout - Multi-chain NFT data scraper
"""

__version__ = "1.0.0"
__author__ = "NFT Scout Team"

from .scraper import NFTScout
from .models import NormalizedNFT, CollectionStats, TransferEvent, Chain

__all__ = ["NFTScout", "NormalizedNFT", "CollectionStats", "TransferEvent", "Chain"]

