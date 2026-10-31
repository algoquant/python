#!/usr/bin/env python3
"""
Final demonstration of recalc_indicator with price bar parsing
"""
import sys
sys.path.append('/Users/jerzy/Develop/Python')

from TechIndic.indicators import MovAvg

def demonstrate_price_bar_integration():
    """Demonstrate the complete price bar parsing integration"""
    
    print("=== recalc_indicator with Price Bar Parsing Demo ===\n")
    
    print("1. Traditional usage (still works):")
    print("-" * 35)
    
    # Test calc_zscore
    indicator1 = MovAvg(alpha=0.1, vol_floor=0.01)
    result = indicator1.recalc_indicator('calc_zscore', 100.0)
    print(f"   recalc_indicator('calc_zscore', 100.0) → {result}")
    
    # Test calc_zscorew with separate instance
    indicator2 = MovAvg(alpha=0.1, vol_floor=0.01)
    result = indicator2.recalc_indicator('calc_zscorew', 101.5, 1000)
    print(f"   recalc_indicator('calc_zscorew', 101.5, 1000) → {result}")
    print()
    
    print("2. NEW: Price bar parsing (automatic):")
    print("-" * 40)
    
    # Reset for fresh calculation
    indicator = MovAvg(alpha=0.1, vol_floor=0.01)
    
    # Dictionary format (most common from APIs)
    api_bar = {'c': 100.0, 'v': 1000, 'o': 99.5, 'h': 100.5, 'l': 99.0}
    result = indicator.recalc_indicator('calc_zscore', api_bar)
    print(f"   API bar: {api_bar}")
    print(f"   Result: {result}")
    print()
    
    # OHLC list format
    ohlc_bar = [100.5, 101.0, 99.8, 101.5, 1200]  # [O, H, L, C, V]
    result = indicator.recalc_indicator('calc_zscore', ohlc_bar)
    print(f"   OHLC bar: {ohlc_bar}")
    print(f"   Result: {result}")
    print()
    
    # Volume-weighted with automatic volume extraction
    indicator_v = MovAvg(alpha=0.1, vol_floor=0.01)
    
    # The same API bar, but using calc_zscorew - volume is extracted automatically
    result = indicator_v.recalc_indicator('calc_zscorew', api_bar)
    print(f"   Volume-weighted with API bar:")
    print(f"   recalc_indicator('calc_zscorew', {api_bar}) → {result}")
    print()
    
    print("3. Supported price bar formats:")
    print("-" * 35)
    formats = [
        ("Dictionary (API)", "{'c': 100.0, 'v': 1000}"),
        ("OHLC List", "[open, high, low, close, volume]"),
        ("OHLC Tuple", "(open, high, low, close, volume)"),
        ("Price-Volume", "[price, volume]"),
        ("Single Price", "100.0 (number)"),
        ("Alternative keys", "{'close': 100.0, 'volume': 1000}")
    ]
    
    for fmt_name, fmt_example in formats:
        print(f"   ✓ {fmt_name}: {fmt_example}")
    
    print()
    print("4. Integration benefits:")
    print("-" * 25)
    print("   ✓ Seamless API integration - pass raw bar data directly")
    print("   ✓ No manual price/volume extraction needed")
    print("   ✓ Supports multiple data formats automatically")
    print("   ✓ Backward compatible - existing code unchanged")
    print("   ✓ Error handling for invalid data formats")
    print("   ✓ Automatic volume extraction for volume-weighted indicators")
    
    print("\n=== Usage in Trading Systems ===")
    print("# Before (manual extraction):")
    print("price = bar_data['c']")
    print("volume = bar_data['v']")
    print("result = indicator.calc_zscorew(price, volume)")
    print()
    print("# After (automatic parsing):")
    print("result = indicator.recalc_indicator('calc_zscorew', bar_data)")
    print()
    print("✓ Cleaner code, fewer errors, more flexible!")

if __name__ == '__main__':
    demonstrate_price_bar_integration()
