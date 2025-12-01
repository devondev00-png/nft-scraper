"""Utility functions for validation and security"""

import re
from typing import Optional, Tuple
import base58
from loguru import logger

# Optional imports for Ethereum address validation
try:
    from eth_utils import is_address, to_checksum_address
    ETH_UTILS_AVAILABLE = True
except ImportError:
    ETH_UTILS_AVAILABLE = False
    logger.warning("eth_utils not available. Ethereum address validation will be limited.")


def validate_ethereum_address(address: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Ethereum address format
    
    Returns:
        (is_valid, checksum_address or None)
    """
    if not address or not isinstance(address, str):
        return False, None
    
    address = address.strip()
    
    # Check basic format
    if not address.startswith('0x') or len(address) != 42:
        return False, None
    
    # Check hex characters
    if not re.match(r'^0x[a-fA-F0-9]{40}$', address):
        return False, None
    
    # Validate using eth_utils if available
    if ETH_UTILS_AVAILABLE:
        try:
            if is_address(address):
                checksum = to_checksum_address(address)
                return True, checksum
        except Exception as e:
            logger.debug(f"Address validation error: {e}")
            # Fall through to basic validation
    # Basic validation without eth_utils (or if eth_utils check failed)
    # Just verify format is correct
    return True, address
    
    return False, None


def validate_solana_address(address: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Solana address format
    
    Returns:
        (is_valid, normalized_address or None)
    """
    if not address or not isinstance(address, str):
        return False, None
    
    address = address.strip()
    
    # Solana addresses are base58 encoded, typically 32-44 characters
    if len(address) < 32 or len(address) > 44:
        return False, None
    
    # Try to decode base58
    try:
        decoded = base58.b58decode(address)
        if len(decoded) == 32:  # Standard Solana address is 32 bytes
            return True, address
    except Exception as e:
        logger.debug(f"Solana address validation error: {e}")
    
    return False, None


def validate_bitcoin_address(address: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Bitcoin address format
    
    Returns:
        (is_valid, normalized_address or None)
    """
    if not address or not isinstance(address, str):
        return False, None
    
    address = address.strip()
    
    # Bitcoin address patterns
    # Legacy: starts with 1, 3
    # Segwit: starts with bc1
    patterns = [
        r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$',  # Legacy
        r'^bc1[a-z0-9]{39,59}$',  # Segwit
    ]
    
    for pattern in patterns:
        if re.match(pattern, address):
            return True, address
    
    return False, None


def validate_contract_address(address: str, chain: str) -> Tuple[bool, Optional[str]]:
    """
    Validate contract address based on chain
    
    Args:
        address: Contract address to validate
        chain: Chain name (ethereum, solana, bitcoin, etc.)
    
    Returns:
        (is_valid, normalized_address or None)
    """
    chain_lower = chain.lower()
    
    if chain_lower in ['ethereum', 'eth', 'polygon', 'arbitrum', 'optimism', 'base', 'avalanche', 'bsc']:
        return validate_ethereum_address(address)
    elif chain_lower in ['solana', 'sol']:
        return validate_solana_address(address)
    elif chain_lower in ['bitcoin', 'btc']:
        return validate_bitcoin_address(address)
    else:
        # For unknown chains, do basic validation
        if address and isinstance(address, str) and len(address) > 10:
            return True, address.strip()
        return False, None


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input to prevent injection attacks
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
    
    Returns:
        Sanitized text
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove script tags and common XSS patterns
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<iframe[^>]*>.*?</iframe>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    
    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length]
        logger.warning(f"Input truncated to {max_length} characters")
    
    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
    
    return text.strip()


def validate_url(url: str) -> bool:
    """
    Validate URL format
    
    Args:
        url: URL to validate
    
    Returns:
        True if valid, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    
    url = url.strip()
    
    # Basic URL pattern
    pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(pattern.match(url))


def validate_chain(chain: str) -> bool:
    """
    Validate chain name
    
    Args:
        chain: Chain name to validate
    
    Returns:
        True if valid, False otherwise
    """
    valid_chains = [
        'ethereum', 'eth',
        'polygon', 'matic',
        'arbitrum', 'arb',
        'optimism', 'op',
        'base',
        'avalanche', 'avax',
        'bsc', 'binance',
        'solana', 'sol',
        'bitcoin', 'btc',
    ]
    
    return chain.lower() in valid_chains

