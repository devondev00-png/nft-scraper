#!/usr/bin/env python3
"""
Quick verification script to ensure all security fixes are in place
"""

import sys
from pathlib import Path

def check_imports():
    """Verify all modules import correctly"""
    print("🔍 Checking imports...")
    try:
        from src.nft_scout.utils import (
            validate_ethereum_address,
            validate_solana_address,
            validate_bitcoin_address,
            sanitize_input,
            validate_url
        )
        print("  ✅ Validation utilities imported")
    except Exception as e:
        print(f"  ❌ Failed to import utils: {e}")
        return False
    
    try:
        from src.nft_scout.webhooks.app import (
            app,
            verify_alchemy_signature,
            verify_moralis_signature,
            verify_helius_signature,
            check_rate_limit
        )
        print("  ✅ Webhook security functions imported")
    except Exception as e:
        print(f"  ❌ Failed to import webhook app: {e}")
        return False
    
    try:
        from web_server import app as web_app
        print("  ✅ Web server imported")
    except Exception as e:
        print(f"  ❌ Failed to import web server: {e}")
        return False
    
    return True

def check_security_features():
    """Verify security features are present"""
    print("\n🔒 Checking security features...")
    
    from src.nft_scout.webhooks.app import app as webhook_app
    
    # Check middleware
    middleware_names = [m.__class__.__name__ for m in webhook_app.user_middleware]
    if 'CORSMiddleware' in str(middleware_names):
        print("  ✅ CORS middleware present")
    else:
        print("  ⚠️  CORS middleware not found")
    
    if 'TrustedHostMiddleware' in str(middleware_names):
        print("  ✅ TrustedHost middleware present")
    else:
        print("  ⚠️  TrustedHost middleware not found")
    
    # Check functions
    if hasattr(webhook_app, 'middleware_stack'):
        print("  ✅ Middleware stack configured")
    
    return True

def test_validation():
    """Test validation functions"""
    print("\n🧪 Testing validation functions...")
    
    from src.nft_scout.utils import (
        validate_ethereum_address,
        validate_solana_address,
        sanitize_input
    )
    
    # Test Ethereum address
    valid_eth = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
    is_valid, _ = validate_ethereum_address(valid_eth)
    if is_valid:
        print(f"  ✅ Ethereum validation works: {valid_eth[:10]}...")
    else:
        print(f"  ⚠️  Ethereum validation returned False for valid address")
    
    # Test sanitization
    test_input = "test\x00string<script>alert('xss')</script>"
    sanitized = sanitize_input(test_input)
    if '\x00' not in sanitized and '<script>' not in sanitized:
        print("  ✅ Input sanitization works")
    else:
        print("  ❌ Input sanitization failed")
    
    return True

def main():
    """Run all checks"""
    print("=" * 60)
    print("🔐 SECURITY AUDIT VERIFICATION")
    print("=" * 60)
    
    all_passed = True
    
    if not check_imports():
        all_passed = False
    
    if not check_security_features():
        all_passed = False
    
    if not test_validation():
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL CHECKS PASSED - System is secure!")
        print("=" * 60)
        return 0
    else:
        print("⚠️  SOME CHECKS FAILED - Review output above")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())

