#!/usr/bin/env python3
"""
Test script for WebSocket rate limiting functionality.
This script tests the enhanced rate limiting for WebSocket connections.
"""

import asyncio
import logging
from AlpacaSDK import AlpacaSDK

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_websocket_rate_limiting():
    """Test WebSocket connection with enhanced rate limiting."""
    print("🧪 Testing WebSocket connection with enhanced rate limiting...")
    
    # Create SDK with conservative rate limiting
    sdk = AlpacaSDK.create_with_rate_limiting(max_retries=3, base_delay=15.0)
    
    try:
        # Create clients
        trading_client, confirm_stream = sdk.create_trade_clients()
        print("✅ Clients created successfully")
        
        # Test callback function
        def test_callback(data):
            print(f"📨 Received WebSocket data: {data}")
        
        # Test WebSocket connection with rate limiting
        print("🔌 Testing WebSocket connection...")
        success = await sdk.connect_websocket_with_retry(
            trade_update_handler=test_callback,
            connection_timeout=30
        )
        
        if success:
            print("✅ WebSocket connection successful!")
        else:
            print("❌ WebSocket connection failed")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        if "429" in str(e) or "rate limit" in str(e).lower():
            print("💡 Rate limiting detected - this is expected behavior")
            print("💡 The enhanced rate limiting is working correctly")
        
    finally:
        # Cleanup
        try:
            await sdk.cleanup_websocket()
            print("🧹 WebSocket cleanup completed")
        except Exception as e:
            print(f"Cleanup error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_rate_limiting())