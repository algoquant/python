#!/usr/bin/env python3
"""
Test script for the AlpacaSDK update_position_list() method.

This script demonstrates how the position tracking works with realized P&L calculations.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from AlpacaSDK.alpacasdk import AlpacaSDK

def test_position_tracking():
    """Test the position tracking and realized P&L calculations."""
    
    print("🧪 Testing AlpacaSDK update_position_list() method\n")
    
    # Create SDK instance without rate limiting for testing
    sdk = AlpacaSDK.create_without_rate_limiting()
    
    print("=" * 60)
    print("TEST 1: Opening Long Positions")
    print("=" * 60)
    
    # Test 1: Buy 100 shares at $50
    realized_pnl = sdk.update_position_list("buy", 100, 50.0)
    print(f"Realized P&L: ${realized_pnl:.2f}")
    print(f"Position shares: {sdk.position_shares}")
    print()
    
    # Test 2: Buy another 50 shares at $52
    realized_pnl = sdk.update_position_list("buy", 50, 52.0)
    print(f"Realized P&L: ${realized_pnl:.2f}")
    print(f"Position shares: {sdk.position_shares}")
    print()
    
    print("=" * 60)
    print("TEST 2: Partial Close Long Position")
    print("=" * 60)
    
    # Test 3: Sell 80 shares at $55 (closing long positions)
    realized_pnl = sdk.update_position_list("sell", 80, 55.0)
    print(f"Realized P&L: ${realized_pnl:.2f}")
    print(f"Position shares: {sdk.position_shares}")
    print()
    
    print("=" * 60)
    print("TEST 3: Close Remaining Long and Open Short")
    print("=" * 60)
    
    # Test 4: Sell 100 shares at $58 (close remaining long + open short)
    realized_pnl = sdk.update_position_list("sell", 100, 58.0)
    print(f"Realized P&L: ${realized_pnl:.2f}")
    print(f"Position shares: {sdk.position_shares}")
    print()
    
    print("=" * 60)
    print("TEST 4: Close Short Position")
    print("=" * 60)
    
    # Test 5: Buy 30 shares at $56 (closing short position)
    realized_pnl = sdk.update_position_list("buy", 30, 56.0)
    print(f"Realized P&L: ${realized_pnl:.2f}")
    print(f"Position shares: {sdk.position_shares}")
    print()
    
    print("=" * 60)
    print("TEST 5: Summary")
    print("=" * 60)
    print(f"Final position list: {sdk.position_list}")
    print(f"Final position shares: {sdk.position_shares}")
    print()
    print("✅ All tests completed successfully!")

if __name__ == "__main__":
    test_position_tracking()