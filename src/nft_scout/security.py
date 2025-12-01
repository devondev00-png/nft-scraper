"""
Blockchain security utilities - Protection against common attacks
"""

import re
import ipaddress
from typing import Optional, Tuple
from urllib.parse import urlparse
from loguru import logger


# Blocked internal IP ranges (SSRF protection)
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),      # Localhost
    ipaddress.ip_network("10.0.0.0/8"),       # Private
    ipaddress.ip_network("172.16.0.0/12"),    # Private
    ipaddress.ip_network("192.168.0.0/16"),   # Private
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local
    ipaddress.ip_network("::1/128"),          # IPv6 localhost
    ipaddress.ip_network("fc00::/7"),         # IPv6 private
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]

# Allowed URL schemes
ALLOWED_SCHEMES = {"http", "https"}

# Blocked URL patterns (SSRF protection)
BLOCKED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "[::1]",
]


def is_internal_ip(ip: str) -> bool:
    """Check if IP address is internal/private (SSRF protection)"""
    try:
        ip_obj = ipaddress.ip_address(ip)
        for blocked_range in BLOCKED_IP_RANGES:
            if ip_obj in blocked_range:
                return True
        return False
    except ValueError:
        return True  # Invalid IP, treat as blocked


def validate_url_safe(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate URL is safe for external requests (SSRF protection)
    
    Returns:
        (is_safe, error_message)
    """
    try:
        parsed = urlparse(url)
        
        # Check scheme
        if parsed.scheme not in ALLOWED_SCHEMES:
            return False, f"Invalid URL scheme: {parsed.scheme}. Only http/https allowed."
        
        # Check hostname
        if not parsed.hostname:
            return False, "URL must have a hostname"
        
        hostname_lower = parsed.hostname.lower()
        
        # Check blocked hosts
        if hostname_lower in BLOCKED_HOSTS:
            return False, f"Blocked hostname: {hostname_lower}"
        
        # Check if hostname resolves to internal IP
        try:
            import socket
            resolved_ip = socket.gethostbyname(parsed.hostname)
            if is_internal_ip(resolved_ip):
                return False, f"Hostname resolves to internal IP: {resolved_ip}"
        except socket.gaierror:
            # DNS resolution failed, but we'll allow it (might be valid)
            pass
        except Exception as e:
            logger.warning(f"Error resolving hostname {parsed.hostname}: {e}")
            # Allow it but log warning
        
        # Check for suspicious patterns
        if "@" in parsed.netloc:
            return False, "URL contains credentials (not allowed)"
        
        # Check port (block common internal ports)
        if parsed.port:
            blocked_ports = [22, 23, 25, 53, 80, 135, 139, 443, 445, 1433, 3306, 3389, 5432, 6379, 8080]
            if parsed.port in blocked_ports and is_internal_ip(parsed.hostname):
                return False, f"Blocked port: {parsed.port}"
        
        return True, None
        
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"


def sanitize_blockchain_address(address: str, chain: str = "ethereum") -> Optional[str]:
    """
    Sanitize and validate blockchain address
    
    Args:
        address: Raw address string
        chain: Chain type (ethereum, solana, bitcoin)
    
    Returns:
        Sanitized address or None if invalid
    """
    if not address or not isinstance(address, str):
        return None
    
    # Remove whitespace
    address = address.strip()
    
    # Ethereum/EVM addresses
    if chain.lower() in ["ethereum", "eth", "polygon", "arbitrum", "optimism", "base", "bsc", "avalanche"]:
        # Must start with 0x and be 42 chars
        if not address.startswith("0x"):
            return None
        if len(address) != 42:
            return None
        # Must be hex
        if not re.match(r'^0x[a-fA-F0-9]{40}$', address):
            return None
        return address.lower()  # Normalize to lowercase
    
    # Solana addresses
    elif chain.lower() in ["solana", "sol"]:
        # Base58 encoded, 32-44 chars
        if len(address) < 32 or len(address) > 44:
            return None
        # Base58 characters only
        if not re.match(r'^[1-9A-HJ-NP-Za-km-z]+$', address):
            return None
        return address
    
    # Bitcoin addresses
    elif chain.lower() in ["bitcoin", "btc"]:
        # Various formats: legacy (1...), segwit (3...), bech32 (bc1...)
        if not re.match(r'^(1|3|bc1)[a-zA-Z0-9]{25,62}$', address):
            return None
        return address
    
    return None


def validate_contract_address(address: str, chain: str) -> Tuple[bool, Optional[str]]:
    """
    Validate contract address format and return normalized address
    
    Returns:
        (is_valid, normalized_address)
    """
    normalized = sanitize_blockchain_address(address, chain)
    if normalized:
        return True, normalized
    return False, None


def prevent_private_key_exposure(data: dict) -> dict:
    """
    Remove any potential private keys/secrets from data before logging
    
    Args:
        data: Dictionary that might contain sensitive data
    
    Returns:
        Sanitized dictionary
    """
    sensitive_keys = [
        "private_key", "privateKey", "private-key",
        "secret", "secret_key", "secretKey", "secret-key",
        "mnemonic", "seed", "seed_phrase", "seedPhrase",
        "api_key", "apiKey", "api-key", "apikey",
        "password", "passwd", "pwd",
        "token", "access_token", "accessToken",
        "webhook_secret", "webhookSecret",
    ]
    
    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = prevent_private_key_exposure(value)
        elif isinstance(value, list):
            sanitized[key] = [
                prevent_private_key_exposure(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    
    return sanitized


def validate_transaction_hash(tx_hash: str, chain: str = "ethereum") -> bool:
    """
    Validate transaction hash format
    
    Args:
        tx_hash: Transaction hash string
        chain: Chain type
    
    Returns:
        True if valid format
    """
    if not tx_hash or not isinstance(tx_hash, str):
        return False
    
    tx_hash = tx_hash.strip()
    
    # Ethereum/EVM transaction hashes
    if chain.lower() in ["ethereum", "eth", "polygon", "arbitrum", "optimism", "base", "bsc", "avalanche"]:
        # 0x followed by 64 hex characters
        return bool(re.match(r'^0x[a-fA-F0-9]{64}$', tx_hash))
    
    # Solana transaction signatures
    elif chain.lower() in ["solana", "sol"]:
        # Base58 encoded, 88 chars
        if len(tx_hash) != 88:
            return False
        return bool(re.match(r'^[1-9A-HJ-NP-Za-km-z]{88}$', tx_hash))
    
    # Bitcoin transaction IDs
    elif chain.lower() in ["bitcoin", "btc"]:
        # 64 hex characters
        return bool(re.match(r'^[a-fA-F0-9]{64}$', tx_hash))
    
    return False


def sanitize_for_logging(message: str) -> str:
    """
    Remove potential secrets from log messages
    
    Args:
        message: Log message that might contain sensitive data
    
    Returns:
        Sanitized message
    """
    # Patterns to redact
    patterns = [
        (r'0x[a-fA-F0-9]{64}', '0x***REDACTED_TX_HASH***'),  # Transaction hashes
        (r'[a-zA-Z0-9]{32,}', lambda m: '***REDACTED***' if len(m.group()) > 50 else m.group()),  # Long strings
    ]
    
    sanitized = message
    for pattern, replacement in patterns:
        if callable(replacement):
            sanitized = re.sub(pattern, replacement, sanitized)
        else:
            sanitized = re.sub(pattern, replacement, sanitized)
    
    return sanitized

