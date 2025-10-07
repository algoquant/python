#!/usr/bin/env python3

"""
Test MovAvg instance creation based on strategy function.
This test isolates the MovAvg creation logic without requiring all CreateStrategy dependencies.
"""

import sys
sys.path.append('TechIndic')
from indicators import MovAvg

def test_movavg_creation():
    """Test MovAvg instance creation with different strategy configurations."""
    
    print('=== Testing MovAvg Instance Creation for Different Strategies ===')
    print()
    
    # Base parameters
    base_alpha = 0.3
    base_vol_floor = 0.1
    
    # Strategy configurations
    strategies = {
        'trade_zscore': {
            'description': 'Standard Z-score strategy',
            'alpha': base_alpha,
            'vol_floor': base_vol_floor
        },
        'trade_dual_ma': {
            'description': 'Dual moving average strategy',
            'fast_alpha': min(base_alpha * 2, 0.9),
            'slow_alpha': base_alpha * 0.5,
            'vol_floor': base_vol_floor
        },
        'trade_bollinger': {
            'description': 'Bollinger bands strategy',
            'alpha': base_alpha,
            'vol_floor': base_vol_floor * 0.5
        },
        'trade_momentum': {
            'description': 'Momentum strategy',
            'alpha': min(base_alpha * 1.5, 0.8),
            'vol_floor': base_vol_floor
        },
        'trade_mean_reversion': {
            'description': 'Mean reversion strategy',
            'alpha': base_alpha * 0.7,
            'vol_floor': base_vol_floor * 1.5
        }
    }
    
    for strategy_name, config in strategies.items():
        print(f"Testing {strategy_name}:")
        print(f"  Description: {config['description']}")
        
        if strategy_name == 'trade_dual_ma':
            # Create dual MovAvg instances
            fast_ma = MovAvg(alpha=config['fast_alpha'], vol_floor=config['vol_floor'])
            slow_ma = MovAvg(alpha=config['slow_alpha'], vol_floor=config['vol_floor'])
            
            print(f"  ✅ Fast MA: alpha={fast_ma.alpha}, vol_floor={fast_ma.vol_floor}")
            print(f"  ✅ Slow MA: alpha={slow_ma.alpha}, vol_floor={slow_ma.vol_floor}")
            
            # Test with sample data
            price = 100.0
            fast_ema = fast_ma.calc_ema(price)
            slow_ema = slow_ma.calc_ema(price)
            print(f"  Initial EMAs: fast={fast_ema:.2f}, slow={slow_ema:.2f}")
            
        else:
            # Create single MovAvg instance
            ma = MovAvg(alpha=config['alpha'], vol_floor=config['vol_floor'])
            print(f"  ✅ MovAvg: alpha={ma.alpha}, vol_floor={ma.vol_floor}")
            
            # Test with sample data - use calc_zscore which handles both EMA and variance
            price = 100.0
            zscore, ema_price, vol = ma.calc_zscore(price)  # First call initializes
            zscore, ema_price, vol = ma.calc_zscore(price + 1)  # Second call shows calculation
            print(f"  Sample calculation: ema={ema_price:.2f}, zscore={zscore:.3f}, vol={vol:.4f}")
        
        print()
    
    print('✅ MovAvg instance creation test completed successfully!')

if __name__ == "__main__":
    test_movavg_creation()
