#!/usr/bin/env python3
"""
Example: Integration of recalc_indicator() with indicator_name from GetArgs
This demonstrates how the trading system can now dynamically use different indicators
"""

# Example usage in a trading strategy context
def example_trading_integration():
    """Example showing how recalc_indicator integrates with GetArgs indicator_name"""
    
    # Simulated GetArgs result (this would come from the actual GetArgs class)
    class MockArgs:
        def __init__(self, indicator_name):
            self.indicator_name = indicator_name
    
    # Import TechIndic
    import sys
    sys.path.append('/Users/jerzy/Develop/Python')
    from TechIndic.indicators import MovAvg
    
    print("=== Trading System Integration Example ===\n")
    
    # Test different indicator_name values
    test_cases = [
        ('calc_zscore', [100.0, 102.5, 99.8]),
        ('calc_ema', [100.0, 102.5, 99.8]),
        ('calc_zscorew', [100.0, 102.5, 99.8])
    ]
    
    for indicator_name, prices in test_cases:
        print(f"Strategy using indicator: {indicator_name}")
        print("-" * 40)
        
        # Create MovAvg instance (this would be done in CreateStrategy)
        movavg = MovAvg(alpha=0.1, vol_floor=0.01)
        
        # Simulate GetArgs providing the indicator_name
        args = MockArgs(indicator_name)
        
        # Use the indicator_name to dynamically call the right method
        for i, price in enumerate(prices):
            if args.indicator_name == 'calc_zscorew':
                # Volume-weighted needs volume parameter
                volume = 1000 + i * 200  # Mock volume data
                result = movavg.recalc_indicator(args.indicator_name, price, volume)
            else:
                # Standard indicators just need price
                result = movavg.recalc_indicator(args.indicator_name, price)
            
            print(f"  Price {price}: {result}")
        
        print()
    
    print("✓ The recalc_indicator() function successfully enables dynamic")
    print("  indicator selection based on user preferences!")

if __name__ == '__main__':
    example_trading_integration()
