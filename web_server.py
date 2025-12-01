#!/usr/bin/env python3
"""
Web UI server for NFT Scout with live scraping
"""

import asyncio
import re
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from typing import List, Optional
from loguru import logger
from pydantic import HttpUrl
import os

from src.nft_scout import NFTScout, Chain
from src.nft_scout.models import NormalizedNFT
from src.nft_scout.utils import (
    validate_contract_address,
    sanitize_input,
    validate_url,
    validate_chain
)
from src.nft_scout.security import (
    sanitize_blockchain_address,
    validate_url_safe,
    prevent_private_key_exposure,
    validate_transaction_hash
)

app = FastAPI(title="NFT Scout Web UI", version="1.0.0")

# Security: Configure CORS properly
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
if ALLOWED_ORIGINS == ["*"]:
    logger.warning("⚠️ CORS is set to allow all origins. Consider restricting in production.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)

# Security: Add trusted host middleware
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

# Security: Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Only add CSP if not already set
    if "Content-Security-Policy" not in response.headers:
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';"
    return response

# Serve static files (background image, videos, fonts, etc.)
import os
static_dir = os.path.join(os.path.dirname(__file__), "static")
# Create static directory if it doesn't exist
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                # Connection closed or error, remove it
                logger.debug(f"Error broadcasting to connection: {e}")
                if connection in self.active_connections:
                    self.active_connections.remove(connection)

manager = ConnectionManager()

# Initialize NFT Scout
scout = NFTScout()


async def fetch_nintondo_contract_address(url: str) -> Optional[str]:
    """Fetch contract address from Nintondo page using multiple methods (with SSRF protection)"""
    try:
        # SSRF Protection: Validate URL is safe
        from src.nft_scout.security import validate_url_safe
        is_safe, error_msg = validate_url_safe(url)
        if not is_safe:
            logger.error(f"SSRF protection: Blocked unsafe URL: {url} - {error_msg}")
            return None
        
        # Additional validation: Only allow specific domains
        allowed_domains = ["nintondo.io", "nintondo.com"]
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.hostname and not any(domain in parsed.hostname.lower() for domain in allowed_domains):
            logger.error(f"SSRF protection: Blocked non-Nintondo domain: {parsed.hostname}")
            return None
        
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # Try to fetch the page with timeout and size limit
            async with session.get(
                url, 
                timeout=aiohttp.ClientTimeout(total=15),
                max_field_size=1024 * 1024,  # 1MB max header size
                headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            ) as resp:
                if resp.status == 200:
                    # Limit response size to prevent memory exhaustion (SSRF protection)
                    max_size = 10 * 1024 * 1024  # 10MB max
                    html = await resp.text()
                    if len(html) > max_size:
                        logger.warning(f"Response too large ({len(html)} bytes), truncating to {max_size} bytes")
                        html = html[:max_size]
                    import re
                    
                    # Method 1: Look for contract address patterns in HTML
                    contract_pattern = r'0x[a-fA-F0-9]{40}'
                    matches = re.findall(contract_pattern, html)
                    if matches:
                        # Filter to find the most likely contract address
                        # Usually contract addresses appear in specific contexts
                        for match in matches:
                            # Check if it's in a contract-related context
                            idx = html.find(match)
                            context = html[max(0, idx-50):min(len(html), idx+90)].lower()
                            if any(keyword in context for keyword in ['contract', 'address', 'collection', 'nft', 'token']):
                                return match
                        # If no context match, return first one
                        return matches[0]
                    
                    # Method 2: Look in JSON-LD structured data
                    json_ld_patterns = [
                        r'"contractAddress"\s*:\s*"([^"]+)"',
                        r'"contract"\s*:\s*"([^"]+)"',
                        r'"address"\s*:\s*"([^"]+)"',
                        r'contract[_-]?address["\']?\s*[:=]\s*["\']([^"\']+)',
                    ]
                    for pattern in json_ld_patterns:
                        json_matches = re.findall(pattern, html, re.IGNORECASE)
                        for match in json_matches:
                            if match.startswith('0x') and len(match) == 42:
                                return match
                    
                    # Method 3: Look in script tags with JSON data
                    script_pattern = r'<script[^>]*>(.*?)</script>'
                    scripts = re.findall(script_pattern, html, re.DOTALL | re.IGNORECASE)
                    for script in scripts:
                        # Look for contract addresses in script content
                        script_matches = re.findall(contract_pattern, script)
                        if script_matches:
                            for match in script_matches:
                                if match.startswith('0x') and len(match) == 42:
                                    return match
                    
                    # Method 4: Try to find in data attributes
                    data_pattern = r'data-contract[=:]\s*["\']([^"\']+)'
                    data_matches = re.findall(data_pattern, html, re.IGNORECASE)
                    for match in data_matches:
                        if match.startswith('0x') and len(match) == 42:
                            return match
                    
                    logger.warning(f"Could not find contract address in Nintondo page HTML")
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching Nintondo page: {e}")
    except Exception as e:
        logger.error(f"Error fetching Nintondo contract address: {e}")
    return None


def extract_collection_info(collection_url: str) -> tuple:
    """Extract contract address and chain from URL or address"""
    if not collection_url:
        raise ValueError("Collection URL cannot be empty or None")
    collection_url = str(collection_url).strip()
    if not collection_url:
        raise ValueError("Collection URL cannot be empty")
    
    # Nintondo URLs - need to extract contract address
    if "nintondo.io" in collection_url.lower() or "nintondo.com" in collection_url.lower():
        # Extract potential contract address from URL path
        # URL format: https://nintondo.io/pepe/mainnet/profile/classicpepe
        # Try to find contract address in URL or return URL for async fetching
        import re
        # Check if URL already contains a contract address
        contract_in_url = re.search(r'0x[a-fA-F0-9]{40}', collection_url)
        if contract_in_url:
            contract = contract_in_url.group()
            # Determine chain from URL
            url_lower = collection_url.lower()
            if "mainnet" in url_lower or "ethereum" in url_lower or "eth" in url_lower:
                return contract, Chain.ETHEREUM
            elif "polygon" in url_lower or "matic" in url_lower:
                return contract, Chain.POLYGON
            elif "arbitrum" in url_lower or "arb" in url_lower:
                return contract, Chain.ARBITRUM
            elif "optimism" in url_lower or "op" in url_lower:
                return contract, Chain.OPTIMISM
            elif "base" in url_lower:
                return contract, Chain.BASE
            else:
                return contract, Chain.ETHEREUM  # Default to Ethereum
        # If no contract in URL, return special marker to fetch it
        # We'll handle this in the async scraping function
        url_lower = collection_url.lower()
        if "mainnet" in url_lower or "ethereum" in url_lower or "eth" in url_lower:
            return collection_url, Chain.ETHEREUM  # Will be resolved async
        elif "polygon" in url_lower or "matic" in url_lower:
            return collection_url, Chain.POLYGON
        elif "arbitrum" in url_lower or "arb" in url_lower:
            return collection_url, Chain.ARBITRUM
        elif "optimism" in url_lower or "op" in url_lower:
            return collection_url, Chain.OPTIMISM
        elif "base" in url_lower:
            return collection_url, Chain.BASE
        else:
            return collection_url, Chain.ETHEREUM  # Default to Ethereum
    
    # Magic Eden - check for chain in URL first (ethereum, solana, etc.)
    if "magiceden" in collection_url.lower():
        parts = collection_url.split("/")
        url_lower = collection_url.lower()
        
        # Check for chain in URL: /collections/ethereum/... or /collections/solana/...
        if "/collections/" in url_lower:
            try:
                collections_idx = [i for i, part in enumerate(parts) if part.lower() == "collections"][0]
                if collections_idx + 1 < len(parts):
                    chain_name = parts[collections_idx + 1].lower()
                    if collections_idx + 2 < len(parts):
                        contract_address = parts[collections_idx + 2]
                        
                        # Map chain names
                        if chain_name == "ethereum" or chain_name == "eth":
                            if contract_address.startswith("0x") and len(contract_address) == 42:
                                return contract_address, Chain.ETHEREUM
                        elif chain_name == "polygon":
                            if contract_address.startswith("0x") and len(contract_address) == 42:
                                return contract_address, Chain.POLYGON
                        elif chain_name == "arbitrum":
                            if contract_address.startswith("0x") and len(contract_address) == 42:
                                return contract_address, Chain.ARBITRUM
                        elif chain_name == "optimism":
                            if contract_address.startswith("0x") and len(contract_address) == 42:
                                return contract_address, Chain.OPTIMISM
                        elif chain_name == "base":
                            if contract_address.startswith("0x") and len(contract_address) == 42:
                                return contract_address, Chain.BASE
                        elif chain_name == "solana" or chain_name == "sol":
                            # Solana address or symbol
                            return contract_address, Chain.SOLANA
            except (IndexError, ValueError):
                pass
        
        # Check for marketplace/collection-name pattern (Solana)
        if "marketplace" in parts:
            idx = parts.index("marketplace")
            if idx + 1 < len(parts):
                collection_symbol = parts[idx + 1]
                if collection_symbol:
                    return collection_symbol, Chain.SOLANA
        
        # Fallback: use last part (assume Solana for old-style URLs)
        collection_symbol = parts[-1] if parts else None
        if collection_symbol and collection_symbol not in ["", "magiceden.io", "magiceden.us"]:
            # If it looks like an Ethereum address, use Ethereum
            if collection_symbol.startswith("0x") and len(collection_symbol) == 42:
                return collection_symbol, Chain.ETHEREUM
            return collection_symbol, Chain.SOLANA
    
    if "solanart.io" in collection_url.lower():
        parts = collection_url.split("/")
        collection_symbol = parts[-1] if parts else None
        if collection_symbol:
            return collection_symbol, Chain.SOLANA
    
    # OpenSea - detect chain from URL
    if "opensea.io" in collection_url.lower():
        # Check for chain in URL (e.g., opensea.io/assets/polygon/...)
        url_lower = collection_url.lower()
        if "/polygon/" in url_lower or "polygon" in url_lower:
            parts = collection_url.split("/")
            # Try to extract contract address
            if "assets" in parts:
                idx = parts.index("assets")
                if idx + 2 < len(parts):
                    contract = parts[idx + 2]
                    if contract.startswith("0x"):
                        return contract, Chain.POLYGON
            return collection_url, Chain.POLYGON
        elif "/arbitrum/" in url_lower or "arbitrum" in url_lower:
            parts = collection_url.split("/")
            if "assets" in parts:
                idx = parts.index("assets")
                if idx + 2 < len(parts):
                    contract = parts[idx + 2]
                    if contract.startswith("0x"):
                        return contract, Chain.ARBITRUM
            return collection_url, Chain.ARBITRUM
        elif "/optimism/" in url_lower or "optimism" in url_lower:
            parts = collection_url.split("/")
            if "assets" in parts:
                idx = parts.index("assets")
                if idx + 2 < len(parts):
                    contract = parts[idx + 2]
                    if contract.startswith("0x"):
                        return contract, Chain.OPTIMISM
            return collection_url, Chain.OPTIMISM
        elif "/base/" in url_lower or "base" in url_lower:
            parts = collection_url.split("/")
            if "assets" in parts:
                idx = parts.index("assets")
                if idx + 2 < len(parts):
                    contract = parts[idx + 2]
                    if contract.startswith("0x"):
                        return contract, Chain.BASE
            return collection_url, Chain.BASE
        else:
            # Default OpenSea to Ethereum
            parts = collection_url.split("/")
            if "assets" in parts:
                idx = parts.index("assets")
                if idx + 2 < len(parts):
                    contract = parts[idx + 2]
                    if contract.startswith("0x"):
                        return contract, Chain.ETHEREUM
            if len(parts) >= 4 and parts[-2] == "collection":
                collection_slug = parts[-1]
                return collection_slug, Chain.ETHEREUM
            return collection_url, Chain.ETHEREUM
    
    # Check for Solana keywords BEFORE checking Ethereum addresses
    # This prevents Magic Eden URLs from being misidentified
    url_lower = collection_url.lower()
    if "solana" in url_lower or "sol" in url_lower or "magiceden" in url_lower or "solanart" in url_lower:
        # Extract address if present, otherwise use as-is
        solana_addr = re.search(r'[1-9A-HJ-NP-Za-km-z]{32,44}', collection_url)
        if solana_addr:
            return solana_addr.group(), Chain.SOLANA
        # If it's a Magic Eden collection symbol
        if "magiceden" in url_lower or "marketplace" in url_lower:
            parts = collection_url.split("/")
            if "marketplace" in parts:
                idx = parts.index("marketplace")
                if idx + 1 < len(parts):
                    return parts[idx + 1], Chain.SOLANA
        return collection_url, Chain.SOLANA
    
    # Direct Ethereum contract address (0x...)
    if collection_url.startswith("0x") and len(collection_url) == 42:
        # Could be any EVM chain, default to Ethereum but we'll try all
        return collection_url, Chain.ETHEREUM
    
    # Solana address (base58) - typically 32-44 characters, no 0x prefix
    if len(collection_url) >= 32 and len(collection_url) <= 44 and not collection_url.startswith("0x"):
        # Check if it looks like base58 (alphanumeric, no ambiguous chars)
        if re.match(r'^[1-9A-HJ-NP-Za-km-z]+$', collection_url):
            return collection_url, Chain.SOLANA
    
    # Try to detect from keywords in the input
    url_lower = collection_url.lower()
    if "polygon" in url_lower or "matic" in url_lower:
        # Extract address if present
        eth_addr = re.search(r'0x[a-fA-F0-9]{40}', collection_url)
        if eth_addr:
            return eth_addr.group(), Chain.POLYGON
        return collection_url, Chain.POLYGON
    elif "arbitrum" in url_lower or "arb" in url_lower:
        eth_addr = re.search(r'0x[a-fA-F0-9]{40}', collection_url)
        if eth_addr:
            return eth_addr.group(), Chain.ARBITRUM
        return collection_url, Chain.ARBITRUM
    elif "optimism" in url_lower or "op" in url_lower:
        eth_addr = re.search(r'0x[a-fA-F0-9]{40}', collection_url)
        if eth_addr:
            return eth_addr.group(), Chain.OPTIMISM
        return collection_url, Chain.OPTIMISM
    elif "base" in url_lower:
        eth_addr = re.search(r'0x[a-fA-F0-9]{40}', collection_url)
        if eth_addr:
            return eth_addr.group(), Chain.BASE
        return collection_url, Chain.BASE
    
    # Default: try as Ethereum address, or return as-is for the scraper to handle
    return collection_url, Chain.ETHEREUM


@app.get("/", response_class=HTMLResponse)
async def get_ui():
    """Serve the main UI"""
    import os
    ui_path = os.path.join(os.path.dirname(__file__), "ui", "index.html")
    try:
        with open(ui_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Explicitly set Content-Type header to ensure browser renders HTML
        return HTMLResponse(
            content=content,
            headers={"Content-Type": "text/html; charset=utf-8"}
        )
    except FileNotFoundError:
        logger.error(f"index.html not found at: {ui_path}")
        return HTMLResponse(
            content="<h1>Error: index.html not found</h1><p>Please check that ui/index.html exists.</p>",
            status_code=404
        )


@app.get("/favicon.ico")
async def favicon():
    """Return 204 No Content for favicon"""
    from fastapi.responses import Response
    return Response(status_code=204)


@app.post("/api/scrape/collection")
async def scrape_collection(collection_url: str):
    """Start scraping a collection with input validation"""
    try:
        # Sanitize and validate input
        collection_url = sanitize_input(collection_url, max_length=2000)
        
        if not collection_url:
            raise HTTPException(status_code=400, detail="Collection URL cannot be empty")
        
        # Validate URL format if it's a URL
        if collection_url.startswith("http://") or collection_url.startswith("https://"):
            if not validate_url(collection_url):
                raise HTTPException(status_code=400, detail="Invalid URL format")
        
        contract_address, chain = extract_collection_info(collection_url)
        
        if not contract_address:
            raise HTTPException(status_code=400, detail="Could not extract collection address from URL")
        
        # Validate contract address format
        is_valid, normalized_address = validate_contract_address(contract_address, chain.value)
        if not is_valid:
            logger.warning(f"Invalid contract address format: {contract_address} for chain {chain.value}")
            # Continue anyway as extract_collection_info may have special handling
        
        return {
            "status": "started",
            "contract_address": normalized_address or contract_address,
            "chain": chain.value,
        }
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting scrape: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live updates"""
    await manager.connect(websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            
            if action == "scrape_collection":
                collection_url = data.get("collection_url")
                
                # Validate and sanitize collection URL
                if not collection_url or collection_url.strip() == "" or collection_url == "null" or collection_url == "undefined":
                    await manager.send_personal_message({
                        "type": "error",
                        "message": "❌ Collection URL cannot be empty or None. Please enter a valid collection URL or contract address.",
                    }, websocket)
                    continue
                
                # Sanitize input
                collection_url = sanitize_input(str(collection_url), max_length=2000)
                
                # Validate URL format if it's a URL
                if collection_url.startswith("http://") or collection_url.startswith("https://"):
                    if not validate_url(collection_url):
                        await manager.send_personal_message({
                            "type": "error",
                            "message": "❌ Invalid URL format. Please enter a valid collection URL or contract address.",
                    }, websocket)
                    continue
                
                try:
                    contract_address, chain = extract_collection_info(collection_url)
                except Exception as e:
                    await manager.send_personal_message({
                        "type": "error",
                        "message": f"❌ Error extracting collection info: {str(e)}",
                    }, websocket)
                    continue
                
                # If contract_address is still a URL (Nintondo, etc.), fetch the actual contract address
                logger.info(f"Checking if contract_address is a URL: {contract_address[:50]}...")
                if contract_address.startswith("http://") or contract_address.startswith("https://"):
                    logger.info(f"Contract address is a URL, fetching actual address from: {contract_address}")
                    await manager.send_personal_message({
                        "type": "status",
                        "message": f"🔍 Fetching contract address from {contract_address}...",
                        "api_source": "Detection",
                    }, websocket)
                    
                    try:
                        actual_contract = await fetch_nintondo_contract_address(contract_address)
                        logger.info(f"Fetched contract address result: {actual_contract}")
                        if actual_contract and actual_contract.startswith("0x") and len(actual_contract) == 42:
                            logger.info(f"✅ Valid contract address found: {actual_contract}")
                            contract_address = actual_contract
                            await manager.send_personal_message({
                                "type": "status",
                                "message": f"✅ Found contract address: {contract_address}",
                                "contract_address": contract_address,
                                "chain": chain.value,
                                "api_source": "Detection",
                            }, websocket)
                        else:
                            logger.warning(f"❌ Could not extract valid contract address. Result: {actual_contract}")
                            await manager.send_personal_message({
                                "type": "error",
                                "message": f"❌ Could not extract contract address from {contract_address}. Please provide the contract address directly (0x...). You can find it on the Nintondo collection page.",
                            }, websocket)
                            continue
                    except Exception as e:
                        logger.error(f"Error fetching contract address from URL: {e}", exc_info=True)
                        await manager.send_personal_message({
                            "type": "error",
                            "message": f"❌ Error fetching contract address from URL: {str(e)}. Please provide the contract address directly (0x...). You can find it on the Nintondo collection page.",
                        }, websocket)
                        continue
                else:
                    logger.info(f"Contract address is not a URL, using directly: {contract_address[:50]}...")
                
                # Validate contract address format with security checks
                is_valid, normalized_address = sanitize_blockchain_address(contract_address, chain.value)
                if not is_valid:
                        await manager.send_personal_message({
                            "type": "error",
                        "message": f"❌ Invalid contract address format: {contract_address}. Address validation failed.",
                        }, websocket)
                        continue
                # Use normalized address
                contract_address = normalized_address or contract_address
                
                await manager.send_personal_message({
                    "type": "status",
                    "message": f"🔍 Detecting collection: {contract_address} on {chain.value}...",
                    "contract_address": contract_address,
                    "chain": chain.value,
                    "api_source": "Detection",
                }, websocket)
                
                # Start scraping
                try:
                    cursor = None
                    total_scraped = 0
                    seen_nfts = set()  # Track seen NFTs to prevent duplicates: (token_id, contract_address)
                    collection_total = None  # Will be fetched BEFORE scraping starts
                    collection_name = None
                    max_pages = 10000  # Very high limit to ensure full collection scraping (supports collections up to 10M NFTs)
                    page_count = 0
                    
                    # CRITICAL: Clear cache before scraping to ensure fresh data and proper pagination
                    cache_key = f"collection:{contract_address}:{chain.value}"
                    await scout.storage.delete_cache(cache_key)
                    logger.info(f"Cleared cache for {cache_key} before scraping")
                    
                    # For Solana, ensure we're using the resolved address
                    if chain == Chain.SOLANA and scout.helius:
                        if hasattr(scout.helius, '_current_collection') and scout.helius._current_collection:
                            resolved_address = scout.helius._current_collection
                            logger.info(f"Using resolved collection address for scraping: {resolved_address}")
                            contract_address = resolved_address
                    
                    # Clear previous results and cache for fresh scrape
                    await manager.send_personal_message({
                        "type": "clear",
                        "message": "Starting new scrape...",
                    }, websocket)
                    
                    # Clear cache for this collection to ensure fresh data
                    cache_key = f"collection:{contract_address}:{chain.value}"
                    await scout.storage.delete_cache(cache_key)
                    await manager.send_personal_message({
                        "type": "status",
                        "message": f"🗑️ Cleared cache for fresh scrape of {contract_address}",
                        "api_source": "Backend",
                        "chain": chain.value,
                    }, websocket)
                    
                    # STEP 1: Fetch collection info FIRST before scraping
                    await manager.send_personal_message({
                        "type": "status",
                        "message": f"Fetching collection information...",
                        "chain": chain.value,
                    }, websocket)
                    
                    # Extract Magic Eden symbol if it's a Magic Eden URL
                    magic_eden_symbol = None
                    if chain == Chain.SOLANA and "magiceden" in collection_url.lower():
                        # If contract_address looks like a symbol (not a Solana address)
                        if len(contract_address) < 32:
                            magic_eden_symbol = contract_address
                    
                    collection_stats = None
                    
                    # For Solana/Helius, get total from a small query first
                    if chain == Chain.SOLANA and scout.helius:
                        try:
                            # Reset helius client state for new collection
                            scout.helius._current_collection = None
                            scout.helius._collection_total = None
                            scout.helius._last_total = None
                            
                            # Clear cache to ensure fresh data
                            cache_key = f"collection:{contract_address}:{chain.value}"
                            await scout.storage.delete_cache(cache_key)
                            logger.info(f"Cleared cache for {cache_key} before fetching collection info")
                            
                            # Use large page_size to get accurate total (Helius returns total based on items in response)
                            # With page_size=1000, if collection < 1000, we get exact total
                            logger.info(f"Fetching collection total for {contract_address} on {chain.value}...")
                            await manager.send_personal_message({
                                "type": "status",
                                "message": f"🔍 Querying Helius API for collection total...",
                                "api_source": "Helius",
                                "chain": chain.value,
                            }, websocket)
                            response = await scout.get_collection_nfts(
                                contract_address,
                                chain,
                                cursor=None,
                                page_size=1000,  # Use large page size to get accurate total
                            )
                            
                            # After first query, get the resolved address if available
                            if hasattr(scout.helius, '_current_collection') and scout.helius._current_collection:
                                resolved_address = scout.helius._current_collection
                                logger.info(f"Resolved collection address: {resolved_address}")
                                # Update contract_address to use resolved address for scraping
                                contract_address = resolved_address
                            
                            # Detailed logging - show what we got from Helius
                            await manager.send_personal_message({
                                "type": "status",
                                "message": f"📊 Helius Response: total={response.total if hasattr(response, 'total') else 'None'}, total_count={response.total_count}, nfts={len(response.nfts)}, has_more={response.has_more}, cursor={'Yes' if response.cursor else 'None'}",
                                "api_source": "Helius",
                                "chain": chain.value,
                            }, websocket)
                            
                            # Check multiple sources for total
                            helius_last_total = getattr(scout.helius, '_last_total', None)
                            helius_collection_total = getattr(scout.helius, '_collection_total', None)
                            
                            await manager.send_personal_message({
                                "type": "status",
                                "message": f"🔍 Checking Helius totals: response.total={response.total if hasattr(response, 'total') else 'None'}, _last_total={helius_last_total}, _collection_total={helius_collection_total}",
                                "api_source": "Helius",
                                "chain": chain.value,
                            }, websocket)
                            
                            # The total should be set in helius client after first call
                            if hasattr(response, 'total') and response.total:
                                collection_total = response.total
                                await manager.send_personal_message({
                                    "type": "status",
                                    "message": f"✅ Using response.total: {collection_total:,} NFTs",
                                    "api_source": "Helius",
                                    "chain": chain.value,
                                }, websocket)
                            elif hasattr(scout.helius, '_last_total') and scout.helius._last_total and scout.helius._last_total > 0:
                                collection_total = scout.helius._last_total
                                logger.info(f"Collection total fetched: {collection_total}")
                                await manager.send_personal_message({
                                    "type": "status",
                                    "message": f"✅ Using Helius _last_total: {collection_total:,} NFTs",
                                    "api_source": "Helius",
                                    "chain": chain.value,
                                }, websocket)
                            else:
                                await manager.send_personal_message({
                                    "type": "status",
                                    "message": f"⚠️ Helius total is None - response.total={response.total if hasattr(response, 'total') else 'None'}, _last_total={helius_last_total}",
                                    "api_source": "Helius",
                                    "chain": chain.value,
                                }, websocket)
                            
                            # Get full collection stats with marketplace data (Magic Eden)
                            try:
                                await manager.send_personal_message({
                                    "type": "status",
                                    "message": f"🔍 Fetching collection stats from multiple APIs (Helius, Magic Eden, Moralis)...",
                                    "api_source": "Multi-API",
                                    "chain": chain.value,
                                }, websocket)
                                collection_stats = await scout.get_collection_stats(
                                    contract_address,
                                    chain,
                                    magic_eden_symbol=magic_eden_symbol,
                                    collection_url=collection_url
                                )
                                
                                # Detailed logging - show what we got from stats
                                await manager.send_personal_message({
                                    "type": "status",
                                    "message": f"📊 CollectionStats: name={collection_stats.name}, total_supply={collection_stats.total_supply}, floor_price={collection_stats.floor_price}, volume_24h={collection_stats.volume_24h}, owners={collection_stats.total_owners}",
                                    "api_source": "Multi-API",
                                    "chain": chain.value,
                                }, websocket)
                                
                                collection_name = collection_stats.name
                                # Use stats total_supply if available (more accurate)
                                if collection_stats.total_supply:
                                    old_total = collection_total
                                    collection_total = collection_stats.total_supply
                                    await manager.send_personal_message({
                                        "type": "status",
                                        "message": f"✅ Magic Eden: Using total_supply={collection_total:,} (was {old_total if old_total else 'None'})",
                                        "api_source": "Magic Eden",
                                        "chain": chain.value,
                                    }, websocket)
                                else:
                                    await manager.send_personal_message({
                                        "type": "status",
                                        "message": f"⚠️ Magic Eden: total_supply is None. Checking other fields...",
                                        "api_source": "Magic Eden",
                                        "chain": chain.value,
                                    }, websocket)
                            except Exception as e:
                                logger.debug(f"Error getting collection stats: {e}")
                        except Exception as e:
                            logger.warning(f"Error fetching collection info: {e}")
                            # Continue anyway - we'll try to get total during scraping
                    
                    # For EVM chains, try to get stats which may include supply and marketplace data
                    else:
                        try:
                            await manager.send_personal_message({
                                "type": "status",
                                "message": f"🔍 Fetching collection stats from multiple APIs (Alchemy, Reservoir, Moralis)...",
                                "api_source": "Multi-API",
                                "chain": chain.value,
                            }, websocket)
                            collection_stats = await scout.get_collection_stats(
                                contract_address, 
                                chain,
                                collection_url=collection_url
                            )
                            
                            # Extract collection name - prioritize Reservoir data
                            collection_name = collection_stats.name
                            logger.info(f"📊 CollectionStats received: name='{collection_name}', total_supply={collection_stats.total_supply}, contract={contract_address}")
                            
                            # Detailed logging - show what we got
                            await manager.send_personal_message({
                                "type": "status",
                                "message": f"📊 CollectionStats: name={collection_name or 'None'}, total_supply={collection_stats.total_supply or 'None'}, floor_price={collection_stats.floor_price}, owners={collection_stats.total_owners}, volume_24h={collection_stats.volume_24h}",
                                "api_source": "Multi-API",
                                "chain": chain.value,
                            }, websocket)
                            
                            # Check if stats has total_supply
                            if collection_stats.total_supply:
                                collection_total = collection_stats.total_supply
                                logger.info(f"✅ Collection total from stats.total_supply: {collection_total:,}")
                                await manager.send_personal_message({
                                    "type": "status",
                                    "message": f"✅ Reservoir/Alchemy: Using total_supply={collection_total:,} NFTs",
                                    "api_source": "Reservoir/Alchemy",
                                    "chain": chain.value,
                                }, websocket)
                            else:
                                logger.warning(f"⚠️ collection_stats.total_supply is None for {contract_address}")
                                await manager.send_personal_message({
                                    "type": "status",
                                    "message": f"⚠️ Reservoir/Alchemy: total_supply is None. Will determine during scraping.",
                                    "api_source": "Reservoir/Alchemy",
                                    "chain": chain.value,
                                }, websocket)
                            
                            # Log final collection name
                            if collection_name and collection_name != contract_address:
                                logger.info(f"✅ Collection name extracted: '{collection_name}'")
                            else:
                                logger.warning(f"⚠️ Collection name is missing or same as contract address: '{collection_name}'")
                        except Exception as e:
                            logger.debug(f"Error getting collection stats: {e}")
                            # Continue anyway - we'll try to get total during scraping
                    
                    # CRITICAL: If collection_total is still None, COUNT BY PAGINATING
                    # This is essential for Ethereum collections where APIs don't provide total
                    # BUT: Skip counting if we already have a valid total from get_collection_info
                    logger.info(f"🔍 [scrape_collection] After collection_stats: collection_total={collection_total}, chain={chain.value}, is_solana={chain == Chain.SOLANA}")
                    
                    should_count = False
                    
                    # Skip counting if we already have a valid total (likely from get_collection_info)
                    # Only count if total is None, suspiciously low, or equals page size
                    if collection_total and collection_total > 100 and collection_total != 100:
                        logger.info(f"✅ [scrape_collection] Skipping count - already have valid total: {collection_total:,} (likely from get_collection_info)")
                        should_count = False
                    # Always count for Ethereum if total is None (Alchemy doesn't provide it)
                    elif chain != Chain.SOLANA and not collection_total:
                        should_count = True
                        logger.info(f"🔍 [Ethereum] Collection total is None. Will count NFTs by paginating through all pages...")
                        logger.warning(f"⚠️ [Ethereum] APIs did not provide total_supply. Counting NFTs by paginating...")
                    elif not collection_total:
                        # For other chains too
                        should_count = True
                        logger.info(f"🔍 Collection total is None. Will count NFTs by paginating through all pages...")
                        logger.warning(f"⚠️ APIs did not provide total_supply. Counting NFTs by paginating...")
                    elif (chain != Chain.SOLANA and collection_total == 100) or (chain == Chain.SOLANA and collection_total == 1000):
                        # For Ethereum, 100 is page size; for Solana, 1000 is page size
                        should_count = True
                        logger.info(f"🔍 Collection total ({collection_total}) equals page size limit. Counting NFTs by paginating...")
                    elif chain != Chain.SOLANA and collection_total and collection_total <= 100:
                        # For Ethereum, any total <= 100 is suspicious (could be page size)
                        should_count = True
                        logger.info(f"🔍 [Ethereum] Collection total ({collection_total}) seems suspiciously low. Counting NFTs by paginating...")
                    
                    logger.info(f"🔍 [scrape_collection] should_count={should_count}, collection_total={collection_total}")
                    
                    if should_count:
                        logger.info(f"🚀 [scrape_collection] Starting NFT counting process for {contract_address} on {chain.value}...")
                        try:
                            await manager.send_personal_message({
                                "type": "status",
                                "message": f"🔢 Counting total NFTs in collection (this may take a moment)...",
                                "api_source": "Backend",
                            }, websocket)
                            
                            # Clear cache before counting
                            cache_key = f"collection:{contract_address}:{chain.value}"
                            await scout.storage.delete_cache(cache_key)
                            logger.info(f"Cleared cache for {cache_key} before counting")
                            
                            # Paginate through collection to count all NFTs
                            total_counted = 0
                            current_cursor = None
                            page_count = 0
                            max_count_pages = 200 if chain != Chain.SOLANA else 100  # Safety limit
                            consecutive_empty_pages = 0
                            page_size = 100 if chain != Chain.SOLANA else 1000  # Alchemy max is 100, Helius is 1000
                            
                            while page_count < max_count_pages:
                                try:
                                    count_response = await scout.get_collection_nfts(
                                        contract_address,
                                        chain,
                                        cursor=current_cursor,
                                        page_size=page_size,
                                    )
                                except Exception as count_err:
                                    logger.error(f"Error counting NFTs on page {page_count + 1}: {count_err}")
                                    break
                                
                                nfts_in_page = len(count_response.nfts)
                                total_counted += nfts_in_page
                                page_count += 1
                                
                                # Update progress every 5 pages for Ethereum
                                update_interval = 5 if chain != Chain.SOLANA else 10
                                if page_count % update_interval == 0 or nfts_in_page == 0:
                                    await manager.send_personal_message({
                                        "type": "status",
                                        "message": f"🔢 Counting... Found {total_counted:,} NFTs so far (page {page_count})...",
                                        "api_source": "Backend",
                                    }, websocket)
                                
                                logger.info(f"Count page {page_count}: got {nfts_in_page} NFTs, total so far: {total_counted:,}, has_more={count_response.has_more}, cursor={'Yes' if count_response.cursor else 'No'}")
                                
                                # If we got 0 NFTs, check if we should continue
                                if nfts_in_page == 0:
                                    consecutive_empty_pages += 1
                                    if consecutive_empty_pages >= 2:
                                        logger.warning(f"Got {consecutive_empty_pages} consecutive empty pages, stopping count")
                                        break
                                else:
                                    consecutive_empty_pages = 0
                                
                                # CRITICAL: For Ethereum/Alchemy, if we got exactly page_size NFTs, there's almost certainly more
                                # Continue paginating until we get less than a full page OR no cursor
                                # This matches Solana's behavior - keep going until we actually run out
                                
                                # Get cursor for next page - check both cursor and pageKey (Alchemy uses pageKey)
                                next_cursor = count_response.cursor or getattr(count_response, 'pageKey', None)
                                
                                if next_cursor:
                                    # We have a cursor/pageKey - definitely more pages
                                    current_cursor = next_cursor
                                    logger.debug(f"Got cursor/pageKey for next page: {str(current_cursor)[:50]}...")
                                elif nfts_in_page == page_size:
                                    # Got full page but no cursor - for Alchemy, try using last token ID as cursor
                                    # Alchemy accepts startToken which can be any token ID from the collection
                                    if count_response.nfts and len(count_response.nfts) > 0:
                                        last_nft = count_response.nfts[-1]
                                        token_id = None
                                        if hasattr(last_nft, 'token_id') and last_nft.token_id:
                                            token_id = str(last_nft.token_id).strip()
                                        
                                        # If token_id is empty, try to get from raw_metadata (Alchemy format: id.tokenId)
                                        if not token_id or token_id == '' or token_id == 'None':
                                            if hasattr(last_nft, 'raw_metadata') and last_nft.raw_metadata:
                                                raw_meta = last_nft.raw_metadata
                                                if isinstance(raw_meta, dict):
                                                    # Alchemy format: id: { tokenId: "123" }
                                                    id_obj = raw_meta.get('id', {})
                                                    if isinstance(id_obj, dict):
                                                        token_id = str(id_obj.get('tokenId', '')).strip()
                                                    if not token_id or token_id == '':
                                                        token_id = str(raw_meta.get('tokenId') or raw_meta.get('id') or raw_meta.get('token_id', '')).strip()
                                        
                                        if token_id and token_id != '' and token_id != 'None':
                                            logger.info(f"Got exactly {page_size} NFTs but no cursor/pageKey. Using last token ID ({token_id}) as startToken for next page...")
                                            current_cursor = token_id
                                            await asyncio.sleep(0.2)
                                            continue
                                        else:
                                            logger.warning(f"Got full page ({page_size} NFTs) but no cursor/pageKey and couldn't extract valid token_id. Continuing anyway...")
                                            if page_count < max_count_pages - 1:
                                                logger.info(f"Continuing to check next page (count so far: {total_counted:,})...")
                                                await asyncio.sleep(0.2)
                                                continue
                                            else:
                                                logger.warning(f"Reached max pages limit. Stopping count at {total_counted:,} NFTs.")
                                                break
                                    else:
                                        logger.warning(f"Got full page ({page_size} NFTs) but no NFTs in response. Stopping count.")
                                        break
                                elif nfts_in_page < page_size:
                                    # Got less than full page - we're done
                                    logger.info(f"Got partial page ({nfts_in_page} < {page_size}) - reached end of collection")
                                    break
                                else:
                                    # No cursor, no has_more, and we got less than full page - we're done
                                    logger.info(f"No cursor, no has_more, and got {nfts_in_page} NFTs - reached end of collection")
                                    break
                                
                                # Small delay to avoid rate limiting
                                await asyncio.sleep(0.1)
                            
                            if total_counted > 0:
                                old_total = collection_total
                                collection_total = total_counted
                                logger.info(f"✅ Counted {collection_total:,} NFTs by paginating through collection (was: {old_total if old_total else 'None'})")
                                
                                await manager.send_personal_message({
                                    "type": "status",
                                    "message": f"✅ Found {collection_total:,} NFTs in collection",
                                    "api_source": "Backend",
                                }, websocket)
                            else:
                                logger.warning(f"⚠️ Counted 0 NFTs - collection may be empty or inaccessible")
                                if collection_total is None:
                                    logger.error(f"❌ CRITICAL: Could not determine collection total - counted 0 NFTs and no total from APIs")
                        except Exception as count_error:
                            logger.error(f"❌ ERROR during NFT counting: {count_error}", exc_info=True)
                            await manager.send_personal_message({
                                "type": "status",
                                "message": f"⚠️ Error counting NFTs: {str(count_error)}",
                                "api_source": "Backend",
                            }, websocket)
                    
                    # Log final values before sending to UI
                    await manager.send_personal_message({
                        "type": "status",
                        "message": f"📋 Final Collection Info: name={collection_name or 'None'}, total={collection_total or 'None'}, contract={contract_address}, chain={chain.value}",
                        "api_source": "Backend",
                        "chain": chain.value,
                    }, websocket)
                    
                    # Prepare response with all available collection info
                    collection_info_data = {
                        "type": "collection_info",
                        "contract_address": contract_address,
                        "chain": chain.value,
                        "collection_name": collection_name or contract_address,
                        "collection_total": collection_total,
                        "total_supply": collection_total,  # Also send as total_supply for compatibility
                    }
                    
                    if collection_total is None:
                        await manager.send_personal_message({
                            "type": "status",
                            "message": f"⚠️ WARNING: collection_total is None! This means we couldn't determine the collection size. It will be found during scraping.",
                            "api_source": "Backend",
                            "chain": chain.value,
                        }, websocket)
                    else:
                        logger.info(f"✅ [scrape_collection] Sending collection_info with total: {collection_total:,}")
                    
                    # Add marketplace data if available
                    if collection_stats:
                        if collection_stats.floor_price is not None:
                            collection_info_data["floor_price"] = collection_stats.floor_price
                            collection_info_data["floor_price_currency"] = collection_stats.floor_price_currency
                        if collection_stats.total_volume is not None:
                            collection_info_data["total_volume"] = collection_stats.total_volume
                        if collection_stats.volume_24h is not None:
                            collection_info_data["volume_24h"] = collection_stats.volume_24h
                        if collection_stats.total_owners is not None:
                            collection_info_data["total_owners"] = collection_stats.total_owners
                        if collection_stats.market_cap is not None:
                            collection_info_data["market_cap"] = collection_stats.market_cap
                    
                    # Send collection info to UI BEFORE starting to scrape
                    await manager.send_personal_message(collection_info_data, websocket)
                    
                    # STEP 2: Now start actual scraping
                    if collection_total:
                        await manager.send_personal_message({
                            "type": "status",
                            "message": f"Collection info loaded: {collection_total:,} NFTs. Starting scrape...",
                            "chain": chain.value,
                        }, websocket)
                    else:
                        await manager.send_personal_message({
                            "type": "status",
                            "message": f"Starting scrape... (total size will be determined during scraping)",
                            "chain": chain.value,
                        }, websocket)
                    
                    # Determine API source for logging
                    api_source = "Helius" if chain == Chain.SOLANA else ("Alchemy" if scout.alchemy else "Moralis")
                    
                    while page_count < max_pages:
                        try:
                            if page_count == 0:
                                await manager.send_personal_message({
                                    "type": "status",
                                    "message": f"🚀 Starting scrape from {api_source} API...",
                                    "api_source": api_source,
                                    "chain": chain.value,
                                }, websocket)
                            
                            # For Alchemy/Moralis, use 100 per page (API limit)
                            # For Helius, use 1000 per page
                            if chain == Chain.SOLANA:
                                page_size = 1000
                            else:
                                page_size = 100  # Alchemy/Moralis max
                            
                            response = await scout.get_collection_nfts(
                                contract_address,
                                chain,
                                cursor=cursor,
                                page_size=page_size,
                            )
                            
                            # Detailed logging during scraping - show what we get from each page
                            await manager.send_personal_message({
                                "type": "status",
                                "message": f"📊 Page {page_count + 1} Response: total={response.total if hasattr(response, 'total') else 'None'}, total_count={response.total_count}, nfts={len(response.nfts)}, has_more={response.has_more}, cursor={'Yes' if response.cursor else 'None'}",
                                "api_source": api_source,
                                "chain": chain.value,
                            }, websocket)
                            
                            # Track collection total size from first response if not already set
                            # (We already fetched it before scraping, but if we didn't, try to get it now)
                            if collection_total is None:
                                await manager.send_personal_message({
                                    "type": "status",
                                    "message": f"🔍 collection_total is None - Checking response for total...",
                                    "api_source": api_source,
                                    "chain": chain.value,
                                }, websocket)
                                
                                # Try to get total from response if available (Helius sometimes returns this)
                                if hasattr(response, 'total') and response.total:
                                    collection_total = response.total
                                    await manager.send_personal_message({
                                        "type": "status",
                                        "message": f"✅ Found total from response.total: {collection_total:,}",
                                        "api_source": api_source,
                                        "chain": chain.value,
                                    }, websocket)
                                elif hasattr(response, 'total_count') and response.total_count > len(response.nfts):
                                    collection_total = response.total_count
                                    await manager.send_personal_message({
                                        "type": "status",
                                        "message": f"✅ Found total from response.total_count: {collection_total:,}",
                                        "api_source": api_source,
                                        "chain": chain.value,
                                    }, websocket)
                                
                                # Also check the raw response from Helius client
                                if chain == Chain.SOLANA and hasattr(scout.helius, '_last_total'):
                                    helius_last = getattr(scout.helius, '_last_total', None)
                                    helius_collection = getattr(scout.helius, '_collection_total', None)
                                    await manager.send_personal_message({
                                        "type": "status",
                                        "message": f"🔍 Checking Helius client during scrape: _last_total={helius_last}, _collection_total={helius_collection}",
                                        "api_source": api_source,
                                        "chain": chain.value,
                                    }, websocket)
                                    
                                    if scout.helius._last_total:
                                        collection_total = scout.helius._last_total
                                        await manager.send_personal_message({
                                            "type": "status",
                                            "message": f"✅ Found total from Helius _last_total during scrape: {collection_total:,}",
                                            "api_source": api_source,
                                            "chain": chain.value,
                                        }, websocket)
                                    elif hasattr(scout.helius, '_collection_total') and scout.helius._collection_total:
                                        collection_total = scout.helius._collection_total
                                        await manager.send_personal_message({
                                            "type": "status",
                                            "message": f"✅ Found total from Helius _collection_total during scrape: {collection_total:,}",
                                            "api_source": api_source,
                                            "chain": chain.value,
                                        }, websocket)
                                
                                # If we got the total now, update the UI
                                if collection_total:
                                    await manager.send_personal_message({
                                        "type": "collection_info",
                                        "collection_total": collection_total,
                                    }, websocket)
                                else:
                                    await manager.send_personal_message({
                                        "type": "status",
                                        "message": f"⚠️ Still no total found - response.total={response.total if hasattr(response, 'total') else 'None'}, response.total_count={response.total_count}",
                                        "api_source": api_source,
                                        "chain": chain.value,
                                    }, websocket)
                            
                            if not response.nfts:
                                # No NFTs found, might be wrong chain or address
                                if page_count == 0:
                                    error_msg = f"No NFTs found on {chain.value}."
                                    
                                    # For Solana with Magic Eden symbols, provide helpful error
                                    if chain == Chain.SOLANA and not contract_address.startswith("0x") and len(contract_address) < 32:
                                        error_msg = f"Magic Eden collection symbol '{contract_address}' cannot be used directly. "
                                        error_msg += "Please provide the Solana collection address. "
                                        error_msg += "You can find it on Magic Eden by viewing the collection details."
                                        await manager.send_personal_message({
                                            "type": "error",
                                            "message": error_msg,
                                        }, websocket)
                                        break
                                    
                                    # Try other chains if first attempt fails
                                    await manager.send_personal_message({
                                        "type": "warning",
                                        "message": f"{error_msg} Trying other chains...",
                                        "api_source": api_source,
                                        "chain": chain.value,
                                    }, websocket)
                                    
                                    # Try all EVM chains if it's an Ethereum address
                                    if chain == Chain.ETHEREUM and contract_address.startswith("0x"):
                                        chains_to_try = [Chain.POLYGON, Chain.ARBITRUM, Chain.OPTIMISM, Chain.BASE]
                                        found = False
                                        for alt_chain in chains_to_try:
                                            try:
                                                alt_response = await scout.get_collection_nfts(
                                                    contract_address,
                                                    alt_chain,
                                                    cursor=None,
                                                    page_size=10,
                                                )
                                                if alt_response.nfts:
                                                    chain = alt_chain
                                                    alt_api_source = "Alchemy" if scout.alchemy else "Moralis"
                                                    await manager.send_personal_message({
                                                        "type": "status",
                                                        "message": f"✅ Found collection on {alt_chain.value} via {alt_api_source} API!",
                                                        "api_source": alt_api_source,
                                                        "chain": alt_chain.value,
                                                    }, websocket)
                                                    found = True
                                                    break
                                            except Exception:
                                                # Error trying alternative chain, continue to next
                                                continue
                                        if not found:
                                            break
                                    elif chain == Chain.SOLANA:
                                        # For Solana, can't try other chains
                                        await manager.send_personal_message({
                                            "type": "error",
                                            "message": "❌ No NFTs found. Please verify the collection address is correct.",
                                            "api_source": api_source,
                                            "chain": chain.value,
                                        }, websocket)
                                        break
                                    else:
                                        break
                                else:
                                    break
                            
                            # Send NFTs one by one for live display with a slight delay for smooth animation
                            await manager.send_personal_message({
                                "type": "status",
                                "message": f"📦 Processing {len(response.nfts)} NFTs from page {page_count + 1}...",
                                "api_source": api_source,
                                "chain": chain.value,
                            }, websocket)
                            
                            for i, nft in enumerate(response.nfts):
                                # Create unique identifier for duplicate checking
                                nft_id = (str(nft.token_id), str(nft.contract_address))
                                
                                # Skip if we've already seen this NFT
                                if nft_id in seen_nfts:
                                    logger.debug(f"⏭️ Skipping duplicate NFT: token_id={nft.token_id}, contract={nft.contract_address}")
                                    continue
                                
                                # Mark as seen
                                seen_nfts.add(nft_id)
                                total_scraped += 1
                                
                                # Convert NFT to dict and ensure HttpUrl fields are strings
                                nft_dict = None
                                try:
                                    if hasattr(nft, 'dict'):
                                        nft_dict = nft.dict()
                                    elif hasattr(nft, 'model_dump'):
                                        nft_dict = nft.model_dump()
                                    else:
                                        nft_dict = {"token_id": str(nft.token_id), "contract_address": str(nft.contract_address)}
                                except Exception:
                                    try:
                                        if hasattr(nft, 'model_dump'):
                                            nft_dict = nft.model_dump()
                                        elif hasattr(nft, 'dict'):
                                            nft_dict = nft.dict()
                                        else:
                                            nft_dict = {"token_id": str(nft.token_id), "contract_address": str(nft.contract_address)}
                                    except Exception as e:
                                        logger.warning(f"Error converting NFT to dict: {e}")
                                        nft_dict = {"token_id": str(nft.token_id), "contract_address": str(nft.contract_address)}
                                
                                # Ensure HttpUrl fields are strings (double check)
                                url_fields = ["image_url", "animation_url", "external_url"]
                                for field in url_fields:
                                    if field in nft_dict and nft_dict[field] is not None:
                                        if not isinstance(nft_dict[field], str):
                                            nft_dict[field] = str(nft_dict[field])
                                
                                # Show what NFT is being scraped
                                nft_name = nft_dict.get("name") or nft_dict.get("token_id") or f"#{i+1}"
                                image_url = nft_dict.get("image_url") or "None"
                                
                                if i % 50 == 0 or i == len(response.nfts) - 1:  # Log every 50th NFT or last one
                                    await manager.send_personal_message({
                                        "type": "status",
                                        "message": f"✅ Scraping NFT {total_scraped}: {nft_name} (image: {str(image_url)[:50]}...)",
                                        "api_source": api_source,
                                        "chain": chain.value,
                                    }, websocket)
                                
                                # Debug: Log image URL details for first few NFTs
                                if i < 5:
                                    await manager.send_personal_message({
                                        "type": "status",
                                        "message": f"🔍 NFT {total_scraped} image_url: {image_url}",
                                        "api_source": api_source,
                                        "chain": chain.value,
                                    }, websocket)
                                
                                # Send NFT immediately for live display
                                await manager.send_personal_message({
                                    "type": "nft",
                                    "nft": nft_dict,
                                    "total_scraped": total_scraped,
                                    "api_source": api_source,
                                }, websocket)
                                
                                # Small delay for smooth UI updates (longer delay for visual effect)
                                await asyncio.sleep(0.05)  # 50ms delay between NFTs for live display effect
                                
                                # Update collection name from first NFT if not set
                                if total_scraped == 1:
                                    await manager.send_personal_message({
                                        "type": "collection_info",
                                        "collection_name": nft.collection_name or contract_address,
                                        "chain": chain.value,
                                    }, websocket)
                            
                            await manager.send_personal_message({
                                "type": "status",
                                "message": f"✅ Completed page {page_count + 1}: {len(response.nfts)} NFTs scraped (total: {total_scraped})",
                                "api_source": api_source,
                                "chain": chain.value,
                            }, websocket)
                            
                            # Calculate remaining and progress
                            remaining = None
                            progress_pct = 0
                            if collection_total and collection_total > 0:
                                remaining = max(0, collection_total - total_scraped)
                                progress_pct = min(100, round((total_scraped / collection_total) * 100, 1))
                            
                            # Update progress
                            await manager.send_personal_message({
                                "type": "progress",
                                "total_scraped": total_scraped,
                                "collection_total": collection_total,
                                "remaining": remaining,
                                "progress_pct": progress_pct,
                                "has_more": response.has_more,
                                "message": f"Scraped {total_scraped} NFTs so far...",
                            }, websocket)
                            
                            # Continue to next page if there are more NFTs
                            # CRITICAL: For Alchemy/Moralis, we MUST continue if:
                            # 1) has_more is True, OR
                            # 2) cursor/pageKey exists, OR  
                            # 3) We haven't reached the total collection size
                            # 4) We got a full page (100 NFTs) - there's almost certainly more
                            should_continue = False
                            
                            # Check for cursor/pageKey in response (Alchemy uses pageKey, Moralis uses cursor)
                            # Also check the raw response dict if available
                            # IMPORTANT: response is a CollectionNFTResponse object, cursor is a direct attribute
                            response_cursor = response.cursor if hasattr(response, 'cursor') and response.cursor else None
                            
                            # If no cursor on response object, check if we can get it from the underlying API response
                            # This shouldn't be necessary but just in case
                            if not response_cursor:
                                # Try to get from response attributes (for debugging)
                                logger.debug(f"Response object attributes: {dir(response)}")
                                response_cursor = getattr(response, 'pageKey', None) or getattr(response, 'nextToken', None)
                            
                            # Debug: Log what we have
                            logger.info(f"🔍 Pagination check: has_more={response.has_more}, cursor={bool(response_cursor)}, total_scraped={total_scraped}, collection_total={collection_total}, nfts_in_page={len(response.nfts)}")
                            
                            # CRITICAL PAGINATION LOGIC - Must continue until ALL NFTs are scraped
                            # PRIORITY 1: If we know the total and haven't reached it - MUST continue (highest priority)
                            if collection_total and collection_total > 0 and total_scraped < collection_total:
                                should_continue = True
                                if response_cursor:
                                    cursor = response_cursor
                                    logger.info(f"✅ Total not reached ({total_scraped}/{collection_total}), using cursor to continue")
                                elif cursor:
                                    logger.warning(f"⚠️ Total not reached ({total_scraped}/{collection_total}), using existing cursor")
                                else:
                                    # Force continue - we'll try to get cursor from next request
                                    logger.warning(f"⚠️ Total not reached ({total_scraped}/{collection_total}), forcing continuation without cursor")
                            # PRIORITY 2: Got full page - almost certainly more (check this BEFORE has_more)
                            # For Solana with 1000 per page, check for 1000; for others check for 100
                            elif (chain == Chain.SOLANA and len(response.nfts) >= 1000) or (chain != Chain.SOLANA and len(response.nfts) >= 100):
                                should_continue = True
                                page_size_got = len(response.nfts)
                                if response_cursor:
                                    cursor = response_cursor
                                    logger.info(f"✅ Got full page ({page_size_got} NFTs) with cursor, continuing...")
                                elif cursor:
                                    logger.warning(f"⚠️ Got full page ({page_size_got} NFTs), using existing cursor to continue")
                                else:
                                    # Try to continue anyway - might get cursor in next request
                                    logger.warning(f"⚠️ Got full page ({page_size_got} NFTs) but no cursor - attempting to continue anyway (will try to get cursor from next request)")
                            # PRIORITY 3: API explicitly says there's more
                            elif response.has_more:
                                should_continue = True
                                if response_cursor:
                                    cursor = response_cursor
                                logger.info(f"✅ has_more=True, continuing. Cursor: {bool(response_cursor)}")
                            # PRIORITY 4: Cursor exists (even if has_more is False)
                            elif response_cursor:
                                should_continue = True
                                cursor = response_cursor
                                logger.info(f"✅ Cursor exists (has_more={response.has_more}), continuing. Cursor: {response_cursor[:30]}...")
                            # PRIORITY 5: Existing cursor from previous page
                            elif cursor:
                                should_continue = True
                                logger.warning(f"⚠️ Using existing cursor to continue (has_more={response.has_more}, nfts={len(response.nfts)})")
                            
                            if should_continue:
                                page_count += 1
                                cursor_str = cursor[:20] + "..." if cursor and len(cursor) > 20 else (cursor or "none")
                                logger.info(f"🔄 Continuing to page {page_count + 1} with cursor: {cursor_str} (scraped: {total_scraped}/{collection_total or '?'})")
                                await manager.send_personal_message({
                                    "type": "status",
                                    "message": f"📥 {api_source} API: Fetching page {page_count + 1}... ({total_scraped}/{collection_total or '?'} NFTs)",
                                    "api_source": api_source,
                                    "chain": chain.value,
                                }, websocket)
                                await asyncio.sleep(0.5)  # Rate limiting
                                # Continue loop - don't break
                            else:
                                # No more pages - but check if we should have continued
                                if collection_total and total_scraped < collection_total:
                                    # We know there are more but stopped - this is an error
                                    logger.error(f"❌ CRITICAL ERROR: Stopped scraping but only got {total_scraped}/{collection_total} NFTs! has_more={response.has_more}, cursor={bool(response_cursor)}, nfts_in_page={len(response.nfts)}")
                                    # Try to force continue one more time
                                    if len(response.nfts) >= 100:
                                        logger.warning(f"⚠️ Got 100 NFTs but stopped - forcing continuation")
                                        should_continue = True
                                        page_count += 1
                                        await manager.send_personal_message({
                                            "type": "status",
                                            "message": f"⚠️ Forcing continuation - got 100 NFTs but total not reached ({total_scraped}/{collection_total})",
                                            "api_source": api_source,
                                            "chain": chain.value,
                                        }, websocket)
                                        await asyncio.sleep(0.5)
                                    else:
                                        await manager.send_personal_message({
                                            "type": "warning",
                                            "message": f"⚠️ {api_source} API: Scraped {total_scraped}/{collection_total} NFTs. Pagination may have been limited.",
                                            "api_source": api_source,
                                            "chain": chain.value,
                                        }, websocket)
                                        break
                                elif len(response.nfts) >= 100:
                                    # Got 100 NFTs but no total - might be more, try to continue
                                    logger.warning(f"⚠️ Got 100 NFTs but has_more=False and no cursor - attempting to continue anyway")
                                    should_continue = True
                                    page_count += 1
                                    await manager.send_personal_message({
                                        "type": "status",
                                        "message": f"⚠️ Got 100 NFTs, attempting to continue...",
                                        "api_source": api_source,
                                        "chain": chain.value,
                                    }, websocket)
                                    await asyncio.sleep(0.5)
                                else:
                                    # Legitimately done
                                    logger.info(f"✅ Completed scraping. Total: {total_scraped} NFTs")
                                    break
                            
                        except Exception as e:
                            logger.error(f"Error scraping page: {e}")
                            # If it's a chain-specific error, try other chains
                            if "No client available" in str(e) or "not available" in str(e).lower():
                                await manager.send_personal_message({
                                    "type": "error",
                                    "message": f"❌ Chain {chain.value} not available. Please ensure API keys are configured.",
                                    "api_source": api_source if 'api_source' in locals() else "Unknown",
                                    "chain": chain.value,
                                }, websocket)
                            else:
                                await manager.send_personal_message({
                                    "type": "error",
                                    "message": f"❌ Error: {str(e)}",
                                    "api_source": api_source if 'api_source' in locals() else "Unknown",
                                    "chain": chain.value if 'chain' in locals() else "Unknown",
                                }, websocket)
                            break
                    
                    # Final progress update
                    remaining = None
                    progress_pct = 0
                    if collection_total and collection_total > 0:
                        remaining = max(0, collection_total - total_scraped)
                        progress_pct = min(100, round((total_scraped / collection_total) * 100, 1))
                    
                    await manager.send_personal_message({
                        "type": "complete",
                        "total_scraped": total_scraped,
                        "collection_total": collection_total,
                        "remaining": remaining,
                        "progress_pct": progress_pct,
                        "message": f"✅ Completed scraping {total_scraped} NFTs from {api_source} API",
                        "api_source": api_source,
                        "chain": chain.value,
                    }, websocket)
                    
                except Exception as e:
                    logger.error(f"Scraping error: {e}")
                    await manager.send_personal_message({
                        "type": "error",
                        "message": str(e),
                    }, websocket)
            
            elif action == "get_collection_info":
                collection_url = data.get("collection_url")
                if not collection_url:
                    await manager.send_personal_message({
                        "type": "error",
                        "message": "No collection URL provided",
                    }, websocket)
                    continue
                
                try:
                    contract_address, chain = extract_collection_info(collection_url)
                    
                    # If contract_address is still a URL (Nintondo, etc.), fetch the actual contract address
                    if contract_address.startswith("http://") or contract_address.startswith("https://"):
                        logger.info(f"[get_collection_info] Contract address is a URL, fetching actual address from: {contract_address}")
                        await manager.send_personal_message({
                            "type": "status",
                            "message": f"🔍 Fetching contract address from {contract_address}...",
                            "api_source": "Detection",
                        }, websocket)
                        
                        try:
                            actual_contract = await fetch_nintondo_contract_address(contract_address)
                            logger.info(f"[get_collection_info] Fetched contract address result: {actual_contract}")
                            if actual_contract and actual_contract.startswith("0x") and len(actual_contract) == 42:
                                logger.info(f"[get_collection_info] ✅ Valid contract address found: {actual_contract}")
                                contract_address = actual_contract
                                await manager.send_personal_message({
                                    "type": "status",
                                    "message": f"✅ Found contract address: {contract_address}",
                                    "contract_address": contract_address,
                                    "chain": chain.value,
                                    "api_source": "Detection",
                                }, websocket)
                            else:
                                logger.warning(f"[get_collection_info] ❌ Could not extract valid contract address. Result: {actual_contract}")
                                await manager.send_personal_message({
                                    "type": "error",
                                    "message": f"❌ Could not extract contract address from {contract_address}. Please provide the contract address directly (0x...). You can find it on the Nintondo collection page.",
                                }, websocket)
                                continue
                        except Exception as e:
                            logger.error(f"[get_collection_info] Error fetching contract address from URL: {e}", exc_info=True)
                            await manager.send_personal_message({
                                "type": "error",
                                "message": f"❌ Error fetching contract address from URL: {str(e)}. Please provide the contract address directly (0x...). You can find it on the Nintondo collection page.",
                            }, websocket)
                            continue
                    
                    # Validate contract address format
                    if chain in [Chain.ETHEREUM, Chain.POLYGON, Chain.ARBITRUM, Chain.OPTIMISM, Chain.BASE]:
                        if not contract_address.startswith("0x") or len(contract_address) != 42:
                            await manager.send_personal_message({
                                "type": "error",
                                "message": f"❌ Invalid contract address format: {contract_address}. Expected format: 0x followed by 40 hex characters.",
                            }, websocket)
                            continue
                    
                    # Extract Magic Eden symbol if it's a Magic Eden URL
                    magic_eden_symbol = None
                    if chain == Chain.SOLANA and "magiceden" in collection_url.lower():
                        # If contract_address looks like a symbol (not a Solana address)
                        if len(contract_address) < 32:
                            magic_eden_symbol = contract_address
                    
                    # Try to get collection info including total size and marketplace data
                    collection_total = None
                    collection_name = None
                    collection_stats = None
                    
                    # For Solana/Helius, we can get the total from a small query
                    if chain == Chain.SOLANA and scout.helius:
                        try:
                            # Don't reset client state - we want to preserve totals from previous queries
                            # Only reset if we're starting fresh (not for info queries)
                            
                            # Do a minimal query with limit=1 just to get total from response
                            # Use large page_size to get accurate total
                            logger.info(f"Fetching collection total for {contract_address} on {chain.value}...")
                            response = await scout.get_collection_nfts(
                                contract_address,
                                chain,
                                cursor=None,
                                page_size=1000,  # Use large page size to get accurate total
                            )
                            
                            # Check multiple sources for total
                            # 1. Response total field (from CollectionNFTResponse) - most reliable
                            if hasattr(response, 'total') and response.total:
                                collection_total = response.total
                                logger.info(f"Got collection total from response.total: {collection_total}")
                            
                            # 2. If cache hit but no total, try to force a fresh query
                            if not collection_total and hasattr(response, 'total') and response.total is None:
                                # Clear cache and try again
                                cache_key = f"collection:{contract_address}:{chain.value}"
                                await scout.storage.delete_cache(cache_key)
                                logger.info("Cache had no total, clearing cache and fetching fresh...")
                                response = await scout.get_collection_nfts(
                                    contract_address,
                                    chain,
                                    cursor=None,
                                    page_size=1000,
                                )
                                if hasattr(response, 'total') and response.total:
                                    collection_total = response.total
                                    logger.info(f"Got collection total from fresh response.total: {collection_total}")
                            
                            # 3. Helius client's _last_total (set after RPC call)
                            if not collection_total and hasattr(scout.helius, '_last_total') and scout.helius._last_total:
                                collection_total = scout.helius._last_total
                                logger.info(f"Got collection total from Helius _last_total: {collection_total}")
                            
                            # 4. Helius client's _collection_total
                            if not collection_total and hasattr(scout.helius, '_collection_total') and scout.helius._collection_total:
                                collection_total = scout.helius._collection_total
                                logger.info(f"Got collection total from Helius _collection_total: {collection_total}")
                        except Exception as e:
                            logger.warning(f"Error fetching Solana collection info: {e}")
                            # Continue anyway - we'll try to get total during scraping
                    
                    # For Ethereum and other EVM chains, try to get total from collection stats
                    if chain != Chain.SOLANA:
                        # Try a small query first to see if we can get total
                        try:
                            logger.info(f"Fetching collection info for {contract_address} on {chain.value}...")
                            test_response = await scout.get_collection_nfts(
                                contract_address,
                                chain,
                                cursor=None,
                                page_size=100,  # Alchemy max is 100
                            )
                            if hasattr(test_response, 'total') and test_response.total:
                                collection_total = test_response.total
                                logger.info(f"Got collection total from test query: {collection_total}")
                        except Exception as test_err:
                            logger.debug(f"Test query for total failed: {test_err}")
                    
                    # Get full collection stats with marketplace data (Reservoir, Alchemy, etc.)
                    try:
                        collection_stats = await scout.get_collection_stats(
                            contract_address,
                            chain,
                            magic_eden_symbol=magic_eden_symbol,
                            collection_url=collection_url
                        )
                        collection_name = collection_stats.name
                        
                        # Use stats total_supply if available (most accurate)
                        if collection_stats.total_supply:
                            old_total = collection_total
                            collection_total = collection_stats.total_supply
                            logger.info(f"✅ Got collection total from collection_stats.total_supply: {collection_total:,} (was: {old_total if old_total else 'None'})")
                            
                            # If we had a different value before, log the correction
                            if old_total and old_total != collection_total:
                                logger.warning(f"⚠️ Total supply corrected: {old_total:,} → {collection_total:,} (using marketplace data)")
                    except Exception as stats_err:
                        logger.warning(f"Error getting collection stats: {stats_err}")
                    
                    # SKIP COUNTING in get_collection_info - just use API totals
                    # Counting will happen during scraping if needed
                    # This makes the confirmation modal show immediately
                    logger.info(f"✅ [get_collection_info] Using API total: {collection_total}, skipping counting (will count during scraping if needed)")
                    
                    # Don't count here - just use what we got from APIs
                    # If total is None or suspicious, we'll count during scraping
                    should_count = False
                    
                    # Log what we have
                    if not collection_total:
                        logger.info(f"⚠️ [get_collection_info] No total from APIs - will show 'Unknown' in modal, counting will happen during scraping")
                    elif (chain != Chain.SOLANA and collection_total == 100) or (chain == Chain.SOLANA and collection_total == 1000):
                        logger.info(f"⚠️ [get_collection_info] Total ({collection_total}) equals page size - might be inaccurate, will verify during scraping")
                    else:
                        logger.info(f"✅ [get_collection_info] Using API total: {collection_total:,} for confirmation modal")
                    
                    # Skip counting block - just use API totals for modal
                    if False:  # Disabled counting in get_collection_info
                        logger.info(f"🚀 Starting NFT counting process for {contract_address} on {chain.value}...")
                        logger.info(f"🚀 [DEBUG] Entering counting block - should_count={should_count}, collection_total={collection_total}")
                        try:
                            await manager.send_personal_message({
                                "type": "status",
                                "message": f"🔢 Counting total NFTs in collection (this may take a moment)...",
                                "api_source": "Backend",
                            }, websocket)
                            
                            # CRITICAL: Clear cache before counting to ensure fresh data
                            cache_key = f"collection:{contract_address}:{chain.value}"
                            await scout.storage.delete_cache(cache_key)
                            logger.info(f"Cleared cache for {cache_key} before counting")
                            
                            # Use the resolved collection address directly (not symbol)
                            # Get it from Helius client if available
                            actual_address = contract_address
                            if chain == Chain.SOLANA and scout.helius:
                                # Try to get the resolved address from Helius
                                if hasattr(scout.helius, '_current_collection') and scout.helius._current_collection:
                                    actual_address = scout.helius._current_collection
                                    logger.info(f"Using resolved collection address for counting: {actual_address}")
                                else:
                                    # Force a fresh query to resolve the address
                                    logger.info(f"Resolving collection address before counting...")
                                    temp_response = await scout.get_collection_nfts(
                                        contract_address,
                                        chain,
                                        cursor=None,
                                        page_size=1,  # Just to trigger resolution
                                    )
                                    if hasattr(scout.helius, '_current_collection') and scout.helius._current_collection:
                                        actual_address = scout.helius._current_collection
                                        logger.info(f"Resolved collection address: {actual_address}")
                            
                            # Paginate through collection to count all NFTs
                            total_counted = 0
                            current_cursor = None
                            page_count = 0
                            # For Ethereum, Alchemy supports up to 100 per page, so we need more pages
                            # 8888 NFTs / 100 per page = ~89 pages max
                            max_count_pages = 200 if chain != Chain.SOLANA else 100  # Safety limit
                            consecutive_empty_pages = 0
                            page_size = 100 if chain != Chain.SOLANA else 1000  # Alchemy max is 100, Helius is 1000
                            
                            while page_count < max_count_pages:
                                # Clear cache for this specific page to avoid stale data
                                if current_cursor:
                                    await scout.storage.delete_cache(cache_key)
                                
                                try:
                                    count_response = await scout.get_collection_nfts(
                                        actual_address,  # Use resolved address
                                        chain,
                                        cursor=current_cursor,
                                        page_size=page_size,
                                    )
                                except Exception as count_err:
                                    logger.error(f"Error counting NFTs on page {page_count + 1}: {count_err}")
                                    break
                                
                                nfts_in_page = len(count_response.nfts)
                                total_counted += nfts_in_page
                                page_count += 1
                                
                                # Update progress every 5 pages for Ethereum (faster updates)
                                update_interval = 5 if chain != Chain.SOLANA else 10
                                if page_count % update_interval == 0 or nfts_in_page == 0:
                                    await manager.send_personal_message({
                                        "type": "status",
                                        "message": f"🔢 Counting... Found {total_counted:,} NFTs so far (page {page_count})...",
                                        "api_source": "Backend",
                                    }, websocket)
                                
                                logger.info(f"Count page {page_count}: got {nfts_in_page} NFTs, total so far: {total_counted:,}, has_more={count_response.has_more}, cursor={'Yes' if count_response.cursor else 'No'}, pageKey={str(count_response.cursor)[:30] if count_response.cursor else 'None'}...")
                                
                                # If we got 0 NFTs, check if we should continue
                                if nfts_in_page == 0:
                                    consecutive_empty_pages += 1
                                    if consecutive_empty_pages >= 2:
                                        logger.warning(f"Got {consecutive_empty_pages} consecutive empty pages, stopping count")
                                        break
                                else:
                                    consecutive_empty_pages = 0
                                
                                # CRITICAL: For Ethereum/Alchemy, if we got exactly page_size NFTs, there's almost certainly more
                                # Continue paginating until we get less than a full page OR no cursor
                                # This matches Solana's behavior - keep going until we actually run out
                                
                                # Get cursor for next page - check both cursor and pageKey (Alchemy uses pageKey)
                                next_cursor = count_response.cursor or getattr(count_response, 'pageKey', None)
                                
                                # PRIORITY 1: If has_more is True OR we got exactly page_size NFTs, we MUST continue
                                # The scraper infers has_more=True when we get exactly 100 NFTs, even if there's no pageKey
                                # So we need to continue when we get exactly 100 NFTs, regardless of cursor
                                # CRITICAL: When we get exactly 100 NFTs, there are almost certainly more pages
                                if count_response.has_more or nfts_in_page == page_size:
                                    logger.debug(f"[Counting] has_more={count_response.has_more}, nfts_in_page={nfts_in_page}, page_size={page_size}, next_cursor={bool(next_cursor)}")
                                    if next_cursor:
                                        current_cursor = next_cursor
                                        logger.debug(f"has_more={count_response.has_more}, got cursor/pageKey for next page: {str(current_cursor)[:50]}...")
                                    elif nfts_in_page == page_size:
                                        # Got exactly 100 NFTs but no cursor - for Alchemy, try using last token ID as cursor
                                        # Alchemy accepts startToken which can be any token ID from the collection
                                        if count_response.nfts and len(count_response.nfts) > 0:
                                            last_nft = count_response.nfts[-1]
                                            # Try to get token ID from the NFT - NormalizedNFT has token_id field
                                            token_id = None
                                            if hasattr(last_nft, 'token_id') and last_nft.token_id:
                                                token_id = str(last_nft.token_id).strip()
                                                logger.debug(f"Extracted token_id from last_nft.token_id: {token_id}")
                                            
                                            # If token_id is empty, try to get from raw_metadata (Alchemy format: id.tokenId)
                                            if not token_id or token_id == '' or token_id == 'None':
                                                if hasattr(last_nft, 'raw_metadata') and last_nft.raw_metadata:
                                                    raw_meta = last_nft.raw_metadata
                                                    if isinstance(raw_meta, dict):
                                                        # Alchemy format: id: { tokenId: "123" }
                                                        id_obj = raw_meta.get('id', {})
                                                        if isinstance(id_obj, dict):
                                                            token_id = str(id_obj.get('tokenId', '')).strip()
                                                        if not token_id or token_id == '':
                                                            token_id = str(raw_meta.get('tokenId') or raw_meta.get('id') or raw_meta.get('token_id', '')).strip()
                                                logger.debug(f"Token ID from raw_metadata: {token_id}")
                                            
                                            if token_id and token_id != '' and token_id != 'None':
                                                logger.info(f"Got exactly {page_size} NFTs but no cursor/pageKey. Using last token ID ({token_id}) as startToken for next page...")
                                                current_cursor = token_id
                                                await asyncio.sleep(0.2)
                                                continue
                                            else:
                                                logger.warning(f"Got exactly {page_size} NFTs but no cursor and couldn't extract valid token_id. Last NFT type: {type(last_nft)}")
                                                # Try to continue without cursor - make one more request to see if we get a cursor
                                                if page_count < max_count_pages - 1:
                                                    logger.info(f"Making request without cursor to check for more pages (count so far: {total_counted:,})...")
                                                    await asyncio.sleep(0.2)
                                                    continue
                                                else:
                                                    logger.warning(f"Reached max pages limit. Stopping count at {total_counted:,} NFTs.")
                                                    break
                                        else:
                                            logger.warning(f"Got exactly {page_size} NFTs but no NFTs in response. Stopping count.")
                                            break
                                    else:
                                        # has_more=True but got less than full page - shouldn't happen, but continue anyway
                                        logger.warning(f"has_more=True but got {nfts_in_page} < {page_size} NFTs. Continuing...")
                                        if page_count < max_count_pages - 1:
                                            await asyncio.sleep(0.2)
                                            continue
                                        else:
                                            break
                                # PRIORITY 2: We have a cursor/pageKey - definitely more pages
                                elif next_cursor:
                                    current_cursor = next_cursor
                                    logger.debug(f"Got cursor/pageKey for next page: {str(current_cursor)[:50]}...")
                                # PRIORITY 3: Got exactly full page - almost certainly more (even if has_more is False)
                                elif nfts_in_page == page_size:
                                    # Got full page but no cursor and has_more=False - for Alchemy, this usually means there's more
                                    # Try one more request to see if we get a cursor or fewer items
                                    logger.warning(f"Got full page ({page_size} NFTs) but no cursor/pageKey and has_more=False. Making one more request to check...")
                                    if page_count < max_count_pages - 1:
                                        logger.info(f"Continuing to check next page (count so far: {total_counted:,})...")
                                        await asyncio.sleep(0.2)
                                        continue
                                    else:
                                        logger.warning(f"Reached max pages limit. Stopping count at {total_counted:,} NFTs.")
                                        break
                                # PRIORITY 4: Got less than full page - we're done
                                elif nfts_in_page < page_size:
                                    logger.info(f"Got partial page ({nfts_in_page} < {page_size}) - reached end of collection")
                                    break
                                # PRIORITY 5: No cursor, no has_more, and we got less than full page - we're done
                                else:
                                    logger.info(f"No cursor, no has_more, and got {nfts_in_page} NFTs - reached end of collection")
                                    break
                                
                                # Small delay to avoid rate limiting
                                await asyncio.sleep(0.1)
                            
                            if total_counted > 0:
                                old_total = collection_total
                                collection_total = total_counted
                                logger.info(f"✅ Counted {collection_total:,} NFTs by paginating through collection (was: {old_total if old_total else 'None'})")
                                
                                await manager.send_personal_message({
                                    "type": "status",
                                    "message": f"✅ Found {collection_total:,} NFTs in collection",
                                    "api_source": "Backend",
                                }, websocket)
                                
                                # Update response_data with the counted total
                                if 'response_data' in locals():
                                    response_data['collection_total'] = collection_total
                                    response_data['total_supply'] = collection_total
                            else:
                                logger.warning(f"⚠️ Counted 0 NFTs - collection may be empty or inaccessible")
                                if collection_total is None:
                                    logger.error(f"❌ CRITICAL: Could not determine collection total - counted 0 NFTs and no total from APIs")
                        except Exception as count_error:
                            logger.error(f"❌ ERROR during NFT counting: {count_error}", exc_info=True)
                            logger.error(f"❌ Counting exception type: {type(count_error).__name__}")
                            logger.error(f"❌ Counting exception args: {count_error.args}")
                            await manager.send_personal_message({
                                "type": "status",
                                "message": f"⚠️ Error counting NFTs: {str(count_error)}",
                                "api_source": "Backend",
                            }, websocket)
                    else:
                        logger.warning(f"⚠️ [DEBUG] Counting was NOT triggered - should_count={should_count}, collection_total={collection_total}, chain={chain.value}")
                        if chain != Chain.SOLANA and not collection_total:
                            logger.error(f"❌ CRITICAL: Ethereum collection with no total but counting not triggered! This should not happen!")
                    
                    # Prepare response with all available collection info
                    # CRITICAL: Use the counted total if available (it's the most accurate)
                    # collection_total variable now contains either:
                    # 1. The counted total from pagination (most accurate)
                    # 2. The total from collection_stats
                    # 3. The total from test query
                    # 4. None (if nothing worked)
                    
                    final_total = collection_total  # This should have the counted value if counting ran
                    
                    response_data = {
                        "type": "collection_info",
                        "contract_address": contract_address,
                        "chain": chain.value,
                        "collection_name": collection_name or contract_address,
                        "collection_total": final_total,  # Use final_total which includes counted value
                        "total_supply": final_total,  # Also send as total_supply for compatibility
                    }
                    
                    # Add all collection stats data if available
                    if collection_stats:
                        # Don't override with stats total if we already have a counted total
                        # The counted total is more accurate
                        if collection_stats.total_supply and not final_total:
                            response_data["collection_total"] = collection_stats.total_supply
                            response_data["total_supply"] = collection_stats.total_supply
                            final_total = collection_stats.total_supply
                        
                        # Add description
                        if collection_stats.description:
                            response_data["description"] = collection_stats.description
                        
                        # Add image URL - try multiple sources
                        if collection_stats.image_url:
                            response_data["image_url"] = str(collection_stats.image_url)
                        elif hasattr(collection_stats, 'logo') and collection_stats.logo:
                            response_data["image_url"] = str(collection_stats.logo)
                        elif hasattr(collection_stats, 'banner_image') and collection_stats.banner_image:
                            response_data["image_url"] = str(collection_stats.banner_image)
                        
                        # Add marketplace data
                        if collection_stats.floor_price is not None:
                            response_data["floor_price"] = collection_stats.floor_price
                            response_data["floor_price_currency"] = collection_stats.floor_price_currency
                        if collection_stats.total_volume is not None:
                            response_data["total_volume"] = collection_stats.total_volume
                        if collection_stats.volume_24h is not None:
                            response_data["volume_24h"] = collection_stats.volume_24h
                        if collection_stats.total_owners is not None:
                            response_data["total_owners"] = collection_stats.total_owners
                        if collection_stats.market_cap is not None:
                            response_data["market_cap"] = collection_stats.market_cap
                        
                        # Add social links
                        if collection_stats.website:
                            response_data["website"] = str(collection_stats.website)
                        if collection_stats.twitter:
                            response_data["twitter"] = collection_stats.twitter
                        if collection_stats.discord:
                            response_data["discord"] = collection_stats.discord
                    
                    # Try to get collection image from first NFT if not in stats
                    if not response_data.get('image_url') or response_data.get('image_url') == '/placeholder.png':
                        try:
                            # Fetch first NFT to get collection image
                            first_nft_response = await scout.get_collection_nfts(
                                contract_address,
                                chain,
                                cursor=None,
                                page_size=1,
                            )
                            if first_nft_response.nfts and len(first_nft_response.nfts) > 0:
                                first_nft = first_nft_response.nfts[0]
                                # Try to get image from first NFT's collection_name or raw_metadata
                                if hasattr(first_nft, 'raw_metadata') and first_nft.raw_metadata:
                                    # Check for collection image in metadata
                                    if isinstance(first_nft.raw_metadata, dict):
                                        collection_img = first_nft.raw_metadata.get('collection_image') or first_nft.raw_metadata.get('collection_logo')
                                        if collection_img:
                                            response_data["image_url"] = str(collection_img)
                                            logger.info(f"Got collection image from first NFT metadata: {collection_img}")
                        except Exception as img_err:
                            logger.debug(f"Could not get collection image from first NFT: {img_err}")
                    
                    # CRITICAL: Final check - ensure collection_total is set
                    # This handles the case where counting updated collection_total after response_data was created
                    if collection_total and (not response_data.get('collection_total') or response_data.get('collection_total') != collection_total):
                        response_data['collection_total'] = collection_total
                        response_data['total_supply'] = collection_total
                        logger.info(f"Updated response_data with counted total: {collection_total:,}")
                    
                    final_sent_total = response_data.get('collection_total')
                    logger.info(f"📤 Sending collection_info: collection_total={final_sent_total}, name={response_data.get('collection_name')}, image_url={response_data.get('image_url', 'None')}, chain={chain.value}")
                    
                    if not final_sent_total:
                        logger.warning(f"⚠️ Sending collection_info with collection_total=None - will show 'Unknown' in modal, counting will happen during scraping")
                    
                    await manager.send_personal_message(response_data, websocket)
                    
                except Exception as e:
                    logger.error(f"Error getting collection info: {e}")
                    await manager.send_personal_message({
                        "type": "error",
                        "message": f"Could not fetch collection info: {str(e)}",
                    }, websocket)
            
            elif action == "get_collection_stats":
                contract_address = data.get("contract_address")
                chain_str = data.get("chain", "ethereum")
                chain = Chain.from_string(chain_str)
                
                try:
                    stats = await scout.get_collection_stats(
                        contract_address, 
                        chain,
                        collection_url=data.get("collection_url")
                    )
                    await manager.send_personal_message({
                        "type": "stats",
                        "stats": stats.dict(),
                    }, websocket)
                except Exception as e:
                    await manager.send_personal_message({
                        "type": "error",
                        "message": str(e),
                    }, websocket)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

