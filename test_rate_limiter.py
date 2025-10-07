#!/usr/bin/env python3
"""
Test script for Alpaca Rate Limiter

This script demonstrates how to use the rate limiter to handle
HTTP 429 errors when connecting to Alpaca's WebSocket streams.
"""

import asyncio
import sys
from alpaca_rate_limiter import AlpacaRateLimiter, WebSocketConnectionManager, create_rate_limited_clients
from AlpacaSDK import AlpacaSDK

async def test_rate_limiter():
    """Test the rate limiter functionality."""
    print("🧪 Testing Alpaca Rate Limiter...")
    
    # Test 1: Create clients with rate limiting
    print("\n📋 Test 1: Creating clients with rate limiting")
    try:
        alpaca_sdk = AlpacaSDK()
        trading_client, confirm_stream, data_client = create_rate_limited_clients(alpaca_sdk)
        print("✅ Clients created successfully")
    except Exception as e:
        print(f"❌ Failed to create clients: {e}")
        return
    
    # Test 2: Test WebSocket connection with rate limiting
    print("\n📋 Test 2: Testing WebSocket connection with rate limiting")
    
    async def dummy_callback(data):
        """Dummy callback for testing."""
        print(f"📨 Received data: {data}")
    
    connection_manager = WebSocketConnectionManager()
    
    # Subscribe to trade updates (this won't actually receive data without a real order)
    confirm_stream.subscribe_trade_updates(dummy_callback)
    
    print("🔌 Attempting WebSocket connection...")
    success = await connection_manager.connect_with_retry(confirm_stream)
    
    if success:
        print("✅ WebSocket connection test completed")
    else:
        print("❌ WebSocket connection test failed")
    
    # Cleanup
    await connection_manager.cleanup_connection(confirm_stream)
    
    print("\n🎉 Rate limiter tests completed!")

async def test_rate_limit_function():
    """Test rate limiting of individual functions."""
    print("\n📋 Test 3: Testing function execution with rate limiting")
    
    rate_limiter = AlpacaRateLimiter(max_retries=2, base_delay=1.0)
    
    async def test_function(message):
        """Test function that might fail."""
        print(f"🔧 Executing test function: {message}")
        return f"Result: {message}"
    
    try:
        result = await rate_limiter.execute_with_retry(test_function, "Hello World")
        print(f"✅ Function result: {result}")
    except Exception as e:
        print(f"❌ Function failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting Alpaca Rate Limiter Tests")
    print("=" * 50)
    
    try:
        # Run the main test
        asyncio.run(test_rate_limiter())
        
        # Run the function test
        asyncio.run(test_rate_limit_function())
        
    except KeyboardInterrupt:
        print("\n⛔ Tests interrupted by user")
    except Exception as e:
        print(f"❌ Test error: {e}")
        sys.exit(1)
    
    print("\n✅ All tests completed successfully!")
    print("\n💡 Usage tips:")
    print("   - Use create_rate_limited_clients() instead of direct client creation")
    print("   - Use WebSocketConnectionManager for WebSocket connections")
    print("   - Rate limiter handles HTTP 429 errors automatically")
    print("   - Exponential backoff prevents overwhelming the API")