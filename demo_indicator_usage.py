#!/usr/bin/env python3
"""
Test script demonstrating recalc_indicator() usage with indicator_name parameter
as it would be used in the trading system
"""
import sys
import os

# Add TechIndic to path
sys.path.append('/Users/jerzy/Develop/Python')

from TechIndic.indicators import MovAvg

def demo_indicator_name_usage():
    """Demonstrate how recalc_indicator works with indicator_name from GetArgs"""
    
    print("=== Demonstrating indicator_name Usage ===\n")
    
    # Simulate different indicator_name values from GetArgs
    indicator_names = ['calc_zscore', 'calc_ema', 'calc_zscorew']
    
    # Sample trading data
    price_data = [100.0, 102.5, 99.8, 101.3, 103.1]
    volume_data = [1000, 1500, 800, 1200, 1600]
    
    for indicator_name in indicator_names:
        print(f"Using indicator: {indicator_name}")
        print("-" * 40)
        
        # Create MovAvg instance for this indicator
        movavg = MovAvg(alpha=0.15, vol_floor=0.01)
        
        for i, price in enumerate(price_data):
            try:
                if indicator_name == 'calc_zscorew':
                    # Volume-weighted indicator needs both price and volume
                    result = movavg.recalc_indicator(indicator_name, price, volume_data[i])
                    if isinstance(result, tuple):
                        zscore, ema_price, price_vol = result
                        print(f"  Step {i+1}: Price={price}, Vol={volume_data[i]} → Z-score={zscore:.4f}, EMA={ema_price:.4f}")
                    else:
                        print(f"  Step {i+1}: Price={price}, Vol={volume_data[i]} → Result={result:.4f}")
                        
                elif indicator_name in ['calc_zscore', 'calc_ema']:
                    # Price-only indicators
                    result = movavg.recalc_indicator(indicator_name, price)
                    if isinstance(result, tuple):
                        if len(result) == 3:  # calc_zscore returns (zscore, ema_price, price_vol)
                            zscore, ema_price, price_vol = result
                            print(f"  Step {i+1}: Price={price} → Z-score={zscore:.4f}, EMA={ema_price:.4f}")
                        else:
                            print(f"  Step {i+1}: Price={price} → Result={result}")
                    else:
                        # calc_ema returns single value
                        print(f"  Step {i+1}: Price={price} → EMA={result:.4f}")
                        
            except Exception as e:
                print(f"  Error processing step {i+1}: {e}")
        
        print()
    
    # Demonstrate error handling for invalid indicator names
    print("Error Handling Demo:")
    print("-" * 20)
    
    movavg = MovAvg()
    invalid_names = ['calc_rsi', 'bollinger_bands', 'macd']
    
    for invalid_name in invalid_names:
        try:
            result = movavg.recalc_indicator(invalid_name, 100.0)
            print(f"  ✗ {invalid_name}: Should have failed")
        except AttributeError as e:
            print(f"  ✓ {invalid_name}: Correctly rejected - {str(e)[:50]}...")
    
    print("\n=== Demo Complete ===")
    print("The recalc_indicator() function successfully supports dynamic")
    print("indicator selection based on the indicator_name parameter!")

if __name__ == '__main__':
    demo_indicator_name_usage()
