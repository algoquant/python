#!/usr/bin/env python3

"""
Test script to verify that trade_update_handler checks orders_list.keys() correctly.
"""

import sys
import os
import asyncio
from unittest.mock import Mock

# Add the project directory to Python path
sys.path.append('/Users/jerzy/Develop/Python')

# Import the AlpacaSDK
from AlpacaSDK.alpacasdk import AlpacaSDK

class MockEventData:
    """Mock trade update event data."""
    def __init__(self, order_id, event_type, limit_price=None):
        self.order = Mock()
        self.order.id = order_id
        
        # Create order info
        order_info = {
            "id": order_id,
            "symbol": "AAPL",
            "order_type": "limit",
            "side": "buy",
            "qty": "10"
        }
        
        if limit_price is not None:
            order_info["limit_price"] = str(limit_price)
        
        # Mock the model_dump method to return event data
        event_dict = {
            "event": event_type,
            "timestamp": "2024-01-01T10:00:00Z",
            "order": order_info,
            "position_qty": "50"
        }
        self.model_dump = Mock(return_value=event_dict)

async def test_orders_list_keys_filtering():
    """Test that trade_update_handler checks orders_list.keys() correctly."""
    
    print("🧪 Testing trade_update_handler orders_list.keys() filtering...")
    
    # Create AlpacaSDK instance
    alpaca_sdk = AlpacaSDK(enable_rate_limiting=False)
    
    # Mock required components
    alpaca_sdk.fills_file = "test_fills.csv"
    alpaca_sdk.canceled_file = "test_canceled.csv"
    
    alpaca_sdk.confirm_stream = Mock()
    async def mock_stop_ws():
        pass
    alpaca_sdk.confirm_stream.stop_ws = mock_stop_ws
    
    sys.modules['utils'] = Mock()
    sys.modules['utils'].convert_to_nytzone = Mock(side_effect=lambda x: x)
    
    import pandas as pd
    pd.DataFrame.to_csv = Mock()
    
    # Set up orders_list with some tracked orders
    alpaca_sdk.orders_list = {
        "tracked_order_1": 99.50,
        "tracked_order_2": 105.00,
        "tracked_order_3": 0  # Market order
    }
    
    print("📋 Initial orders_list.keys():", list(alpaca_sdk.orders_list.keys()))
    
    # Test 1: Order in orders_list.keys() should be processed
    print("\n🔸 Test 1: Processing tracked order...")
    
    tracked_event = MockEventData("tracked_order_1", "fill")
    
    # Mock print to capture output
    import builtins
    original_print = builtins.print
    output_captured = []
    builtins.print = lambda *args, **kwargs: output_captured.append(" ".join(str(arg) for arg in args))
    
    try:
        await alpaca_sdk.trade_update_handler(tracked_event)
        processed = any("tracked_order_1" in msg for msg in output_captured)
        assert processed, "Tracked order should be processed"
        print("   ✅ Tracked order was processed")
    finally:
        builtins.print = original_print
    
    # Test 2: Order NOT in orders_list.keys() should be ignored (non-confirmation event)
    print("\n🔸 Test 2: Ignoring untracked order (non-confirmation event)...")
    
    untracked_event = MockEventData("untracked_order", "fill")
    
    output_captured = []
    builtins.print = lambda *args, **kwargs: output_captured.append(" ".join(str(arg) for arg in args))
    
    try:
        await alpaca_sdk.trade_update_handler(untracked_event)
        processed = any("untracked_order" in msg for msg in output_captured)
        assert not processed, "Untracked order with non-confirmation event should be ignored"
        print("   ✅ Untracked order with non-confirmation event was ignored")
    finally:
        builtins.print = original_print
    
    # Test 3: Order NOT in orders_list.keys() but is confirmation event should be processed
    print("\n🔸 Test 3: Processing untracked order (confirmation event)...")
    
    confirmation_event = MockEventData("new_order", "pending_new", 102.00)
    
    output_captured = []
    builtins.print = lambda *args, **kwargs: output_captured.append(" ".join(str(arg) for arg in args))
    
    try:
        await alpaca_sdk.trade_update_handler(confirmation_event)
        processed = any("new_order" in msg for msg in output_captured)
        assert processed, "Untracked order with confirmation event should be processed"
        assert "new_order" in alpaca_sdk.orders_list.keys(), "New order should be added to orders_list"
        print("   ✅ Untracked order with confirmation event was processed and added")
    finally:
        builtins.print = original_print
    
    # Test 4: Verify different confirmation events work
    print("\n🔸 Test 4: Testing different confirmation events...")
    
    confirmation_types = ["new", "accepted"]
    for i, event_type in enumerate(confirmation_types):
        order_id = f"confirm_order_{i}"
        event = MockEventData(order_id, event_type, 100.00 + i)
        
        # Verify order is not tracked initially
        assert order_id not in alpaca_sdk.orders_list.keys(), f"Order {order_id} should not be tracked initially"
        
        output_captured = []
        builtins.print = lambda *args, **kwargs: output_captured.append(" ".join(str(arg) for arg in args))
        
        try:
            await alpaca_sdk.trade_update_handler(event)
            processed = any(order_id in msg for msg in output_captured)
            assert processed, f"Confirmation event {event_type} should be processed"
            assert order_id in alpaca_sdk.orders_list.keys(), f"Order {order_id} should be added to orders_list"
            print(f"   ✅ {event_type} confirmation event processed and order added")
        finally:
            builtins.print = original_print
    
    print(f"\n📝 Final orders_list.keys(): {list(alpaca_sdk.orders_list.keys())}")
    
    # Verify expected final state
    expected_orders = ["tracked_order_1", "tracked_order_2", "tracked_order_3", "new_order", "confirm_order_0", "confirm_order_1"]
    for order_id in expected_orders:
        if order_id != "tracked_order_1":  # This one was removed by fill event
            assert order_id in alpaca_sdk.orders_list.keys(), f"Expected order {order_id} to be in orders_list"
    
    print("🎉 All filtering tests passed!")

if __name__ == "__main__":
    try:
        asyncio.run(test_orders_list_keys_filtering())
        print("\n🏆 All tests passed!")
        print("📝 Verified:")
        print("  ✅ Orders in orders_list.keys() are processed")
        print("  ✅ Orders NOT in orders_list.keys() are ignored (non-confirmation events)")
        print("  ✅ Orders NOT in orders_list.keys() are processed (confirmation events)")
        print("  ✅ Confirmation events add orders to orders_list.keys()")
        print("  ✅ Filtering logic uses explicit orders_list.keys() check")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)