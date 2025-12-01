#!/usr/bin/env python3
"""
Test API Keys Configuration
This script checks if your API keys are working correctly
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

def test_imports():
    """Test if required modules can be imported"""
    print("🔍 Testing imports...")
    try:
        from src.nft_scout import NFTScout, Chain
        print("  ✅ NFTScout imports successful")
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False

def check_api_keys():
    """Check which API keys are configured"""
    print("\n📋 Checking API Keys Configuration:")
    print("=" * 50)
    
    keys_status = {}
    
    # Check Alchemy
    alchemy_key = os.getenv("ALCHEMY_API_KEY", "").strip()
    if alchemy_key:
        keys_status["Alchemy"] = "✅ Configured"
    else:
        keys_status["Alchemy"] = "❌ Missing (Required for EVM chains)"
    
    # Check Moralis
    moralis_key = os.getenv("MORALIS_API_KEY", "").strip()
    if moralis_key:
        keys_status["Moralis"] = "✅ Configured"
    else:
        keys_status["Moralis"] = "⚠️  Optional (not configured)"
    
    # Check Helius
    helius_key = os.getenv("HELIUS_API_KEY", "").strip()
    if helius_key:
        keys_status["Helius"] = "✅ Configured"
    else:
        keys_status["Helius"] = "❌ Missing (Required for Solana)"
    
    # Check Magic Eden
    magiceden_key = os.getenv("MAGICEDEN_PUBLIC_API_KEY") or os.getenv("MAGICEDEN_API_KEY", "").strip()
    if magiceden_key:
        keys_status["Magic Eden"] = "✅ Configured"
    else:
        keys_status["Magic Eden"] = "⚠️  Optional (works without key)"
    
    # Check Reservoir
    reservoir_key = os.getenv("RESERVOIR_API_KEY", "").strip()
    if reservoir_key:
        keys_status["Reservoir"] = "✅ Configured"
    else:
        keys_status["Reservoir"] = "✅ Working (no key needed)"
    
    for api, status in keys_status.items():
        print(f"  {status} - {api}")
    
    return keys_status

def test_nft_scout_initialization():
    """Test if NFTScout can be initialized"""
    print("\n🔧 Testing NFTScout Initialization:")
    print("=" * 50)
    
    try:
        from src.nft_scout import NFTScout
        scout = NFTScout()
        print("  ✅ NFTScout initialized successfully")
        
        # Check which clients are available
        print("\n📡 Available API Clients:")
        if scout.alchemy:
            print("  ✅ Alchemy client: Available")
        else:
            print("  ❌ Alchemy client: Not available")
        
        if scout.moralis:
            print("  ✅ Moralis client: Available")
        else:
            print("  ⚠️  Moralis client: Not available (optional)")
        
        if scout.helius:
            print("  ✅ Helius client: Available")
        else:
            print("  ❌ Helius client: Not available")
        
        if scout.magiceden:
            print("  ✅ Magic Eden client: Available")
        else:
            print("  ⚠️  Magic Eden client: Not available (optional)")
        
        if scout.reservoir:
            print("  ✅ Reservoir client: Available")
        else:
            print("  ⚠️  Reservoir client: Not available (optional)")
        
        return True
    except Exception as e:
        print(f"  ❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🚀 NFT Scraper API Keys Test")
    print("=" * 50)
    
    # Test imports
    if not test_imports():
        print("\n❌ Cannot proceed - imports failed")
        sys.exit(1)
    
    # Check API keys
    keys_status = check_api_keys()
    
    # Test initialization
    test_nft_scout_initialization()
    
    # Summary
    print("\n📊 Summary:")
    print("=" * 50)
    
    missing_required = []
    if "❌" in keys_status.get("Alchemy", ""):
        missing_required.append("Alchemy (Required for EVM chains)")
    if "❌" in keys_status.get("Helius", ""):
        missing_required.append("Helius (Required for Solana)")
    
    if missing_required:
        print("  ⚠️  Missing required API keys:")
        for key in missing_required:
            print(f"     - {key}")
        print("\n  💡 Get your free API keys:")
        print("     - Alchemy: https://www.alchemy.com/")
        print("     - Helius: https://www.helius.dev/")
        print("\n  📖 See GET_API_KEYS.md for instructions")
    else:
        print("  ✅ All required API keys are configured!")
        print("  🎉 You're ready to scrape NFTs!")
    
    print("\n")

if __name__ == "__main__":
    main()

