#!/usr/bin/env python3
"""
Test script to verify WebSocket callback functionality works correctly.
This will help debug the fill recording issue.
"""

import asyncio
import logging
from AlpacaSDK import AlpacaSDK

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_websocket_callback():
    """Test that WebSocket callbacks are working properly."""
    print("🧪 Testing WebSocket callback functionality...")
    
    # Create SDK with rate limiting
    sdk = AlpacaSDK.create_with_rate_limiting(max_retries=2, base_delay=10.0)
    
    try:
        # Create clients
        trading_client, confirm_stream = sdk.create_trade_clients()
        print("✅ Clients created successfully")
        
        # Test callback function
        callback_called = False
        
        def test_callback(data):
            nonlocal callback_called
            callback_called = True
            print(f"📨 Callback received data: {type(data)}")
            print(f"📊 Data content: {data}")
            # Stop the stream after receiving data
            asyncio.create_task(confirm_stream.stop_ws())
        
        # Subscribe to trade updates
        confirm_stream.subscribe_trade_updates(test_callback)
        print("📡 Subscribed to trade updates")
        
        # Test connection for a short time
        try:
            await asyncio.wait_for(confirm_stream._run_forever(), timeout=30)
        except asyncio.TimeoutError:
            print("⏰ Test timeout - this is expected for callback testing")
        
        print(f"🔍 Callback called: {callback_called}")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        if "429" in str(e) or "rate limit" in str(e).lower():
            print("💡 Rate limiting detected - please wait before testing")
    finally:
        # Cleanup
        try:
            await confirm_stream.stop_ws()
            print("🧹 WebSocket cleanup completed")
        except Exception as e:
            print(f"Cleanup error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_callback())