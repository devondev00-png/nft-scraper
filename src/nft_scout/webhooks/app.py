"""FastAPI webhook endpoints with proper security and validation"""

from fastapi import FastAPI, Request, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from typing import Optional, Dict, Any
import json
import hmac
import hashlib
import time
from collections import deque
from loguru import logger
import os

from src.nft_scout.config import config

app = FastAPI(title="NFT Scout Webhooks", version="1.0.0")

# Security: Configure CORS properly
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
if ALLOWED_ORIGINS == ["*"]:
    logger.warning("⚠️ CORS is set to allow all origins. Consider restricting in production.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    max_age=3600,
)

# Security: Add trusted host middleware
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

# Rate limiting: Store request timestamps per IP
rate_limit_store: Dict[str, deque] = {}
MAX_EVENTS = int(os.getenv("WEBHOOK_MAX_EVENTS", "10000"))  # Prevent memory leak
MAX_EVENTS_PER_IP = int(os.getenv("WEBHOOK_RATE_LIMIT", "100"))  # Per minute
RATE_LIMIT_WINDOW = 60  # seconds

# Store webhook events with size limit (prevent memory leak)
webhook_events: deque = deque(maxlen=MAX_EVENTS)


def get_client_ip(request: Request) -> str:
    """Extract client IP address"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(ip: str) -> bool:
    """Check if IP is within rate limit"""
    now = time.time()
    if ip not in rate_limit_store:
        rate_limit_store[ip] = deque()
    
    # Remove old timestamps outside the window
    while rate_limit_store[ip] and rate_limit_store[ip][0] < now - RATE_LIMIT_WINDOW:
        rate_limit_store[ip].popleft()
    
    # Check if limit exceeded
    if len(rate_limit_store[ip]) >= MAX_EVENTS_PER_IP:
        return False
    
    # Add current timestamp
    rate_limit_store[ip].append(now)
    return True


def verify_alchemy_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify Alchemy webhook signature"""
    try:
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Error verifying Alchemy signature: {e}")
        return False


def verify_moralis_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify Moralis webhook signature"""
    try:
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Error verifying Moralis signature: {e}")
        return False


def verify_helius_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify Helius webhook signature"""
    try:
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Error verifying Helius signature: {e}")
        return False


@app.post("/webhook/alchemy")
async def alchemy_webhook(request: Request):
    """Handle Alchemy webhooks with signature verification"""
    client_ip = get_client_ip(request)
    
    # Rate limiting
    if not check_rate_limit(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        # Get raw body for signature verification
        body_bytes = await request.body()
        body = await request.json()
        
        # Verify signature if webhook secret is configured
        webhook_secret = config.webhook_secret
        if webhook_secret:
            signature = request.headers.get("x-alchemy-signature") or request.headers.get("X-Alchemy-Signature")
            if not signature:
                logger.warning("Missing Alchemy signature header")
                raise HTTPException(status_code=401, detail="Missing signature")
            
            if not verify_alchemy_signature(body_bytes, signature, webhook_secret):
                logger.warning(f"Invalid Alchemy signature from IP: {client_ip}")
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        event = {
            "source": "alchemy",
            "timestamp": body.get("timestamp") or time.time(),
            "ip": client_ip,
            "data": body,
        }
        
        webhook_events.append(event)
        logger.info(f"Received Alchemy webhook: {body.get('event', {}).get('type')} from {client_ip}")
        
        return {"status": "ok", "message": "Webhook received"}
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in Alchemy webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Error processing Alchemy webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/webhook/moralis")
async def moralis_webhook(request: Request):
    """Handle Moralis webhooks with signature verification"""
    client_ip = get_client_ip(request)
    
    # Rate limiting
    if not check_rate_limit(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        # Get raw body for signature verification
        body_bytes = await request.body()
        body = await request.json()
        
        # Verify signature if webhook secret is configured
        webhook_secret = config.webhook_secret
        if webhook_secret:
            signature = request.headers.get("x-signature") or request.headers.get("X-Signature")
            if not signature:
                logger.warning("Missing Moralis signature header")
                raise HTTPException(status_code=401, detail="Missing signature")
            
            if not verify_moralis_signature(body_bytes, signature, webhook_secret):
                logger.warning(f"Invalid Moralis signature from IP: {client_ip}")
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        event = {
            "source": "moralis",
            "timestamp": body.get("createdAt") or time.time(),
            "ip": client_ip,
            "data": body,
        }
        
        webhook_events.append(event)
        logger.info(f"Received Moralis webhook: {body.get('tag')} from {client_ip}")
        
        return {"status": "ok", "message": "Webhook received"}
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in Moralis webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Error processing Moralis webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/webhook/helius")
async def helius_webhook(request: Request):
    """Handle Helius webhooks with signature verification"""
    client_ip = get_client_ip(request)
    
    # Rate limiting
    if not check_rate_limit(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        # Get raw body for signature verification
        body_bytes = await request.body()
        body = await request.json()
        
        # Verify signature if webhook secret is configured
        webhook_secret = config.webhook_secret
        if webhook_secret:
            signature = request.headers.get("x-helius-signature") or request.headers.get("X-Helius-Signature")
            if not signature:
                logger.warning("Missing Helius signature header")
                raise HTTPException(status_code=401, detail="Missing signature")
            
            if not verify_helius_signature(body_bytes, signature, webhook_secret):
                logger.warning(f"Invalid Helius signature from IP: {client_ip}")
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        event = {
            "source": "helius",
            "timestamp": body.get("timestamp") or time.time(),
            "ip": client_ip,
            "data": body,
        }
        
        webhook_events.append(event)
        logger.info(f"Received Helius webhook: {body.get('type')} from {client_ip}")
        
        return {"status": "ok", "message": "Webhook received"}
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in Helius webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Error processing Helius webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/webhook/events")
async def get_webhook_events(limit: int = 100):
    """Get recent webhook events with validation"""
    # Validate limit
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 1000")
    
    events_list = list(webhook_events)
    return {
        "events": events_list[-limit:],
        "total": len(events_list),
        "max_events": MAX_EVENTS,
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "webhook_events_count": len(webhook_events),
        "rate_limit_store_size": len(rate_limit_store),
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "NFT Scout Webhooks",
        "version": "1.0.0",
        "endpoints": {
            "alchemy": "/webhook/alchemy",
            "moralis": "/webhook/moralis",
            "helius": "/webhook/helius",
            "events": "/webhook/events",
            "health": "/health",
        }
    }
