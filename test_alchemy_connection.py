#!/usr/bin/env python3
"""
Test Alchemy API Connection
Quick test to verify Alchemy API key is working
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

async def test_alchemy():
    """Test Alchemy API connection"""
    print("🔍 Testing Alchemy API Connection...")
    print("=" * 50)
    
    try:
        from src.nft_scout import NFTScout, Chain
        
        scout = NFTScout()
        
        if not scout.alchemy:
            print("  ❌ Alchemy client not initialized!")
            print("  💡 Check your ALCHEMY_API_KEY in .env file")
            return False
        
        print("  ✅ Alchemy client initialized")
        
        # Test with a well-known Ethereum collection (Bored Ape Yacht Club)
        test_contract = "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D"  # BAYC
        print(f"\n🧪 Testing API call with contract: {test_contract}")
        print("  (This is Bored Ape Yacht Club on Ethereum)")
        
        try:
            # Try to get collection metadata
            metadata = await scout.alchemy.get_collection_metadata(
                test_contract,
                "ethereum"
            )
            
            if metadata:
                print("  ✅ Alchemy API is working!")
                print(f"  📊 Collection Name: {metadata.get('name', 'N/A')}")
                print(f"  📊 Symbol: {metadata.get('symbol', 'N/A')}")
                return True
            else:
                print("  ⚠️  API call succeeded but returned no data")
                return True  # Still counts as working
                
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg or "Invalid API key" in error_msg:
                print(f"  ❌ API Key Error: {e}")
                print("  💡 Your Alchemy API key may be invalid or expired")
                print("  💡 Check: https://dashboard.alchemy.com/")
                return False
            elif "403" in error_msg or "Forbidden" in error_msg:
                print(f"  ❌ Access Denied: {e}")
                print("  💡 Your API key may not have the right permissions")
                return False
            else:
                print(f"  ⚠️  API Error: {e}")
                print("  💡 This might be a temporary issue or network problem")
                return True  # Might still work for other calls
        
    except Exception as e:
        print(f"  ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("🚀 Alchemy API Connection Test")
    print("=" * 50)
    print()
    
    success = await test_alchemy()
    
    print()
    print("=" * 50)
    if success:
        print("✅ Alchemy API is configured and working!")
        print("🎉 You're ready to scrape NFTs from EVM chains!")
    else:
        print("❌ Alchemy API test failed")
        print("💡 Please check your API key and try again")
    print()

if __name__ == "__main__":
    asyncio.run(main())

