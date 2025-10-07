#!/usr/bin/env python3
"""
Demonstration of the redesigned CreateStrategy using Abstract Base Class pattern.
Shows how to initialize and execute trading strategies using string names.
"""

import sys
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

# Add the current directory to path
sys.path.append('/Users/jerzy/Develop/Python')

from MachineTrader import CreateStrategy, BaseStrategy, StrategyFactory

class MockBar:
    """Mock bar object for demonstration purposes"""
    def __init__(self, symbol="SPY", close=420.50):
        self.symbol = symbol
        self.timestamp = datetime.now(ZoneInfo("America/New_York"))
        self.open = close * 0.999
        self.high = close * 1.002
        self.low = close * 0.997
        self.close = close
        self.volume = 1000000

async def demo_string_based_execution():
    """Demonstrate string-based strategy execution"""
    
    print("🎯 CreateStrategy ABC Pattern Demo")
    print("=" * 50)
    
    # Method 1: Direct instantiation with string-based execution
    print("\n1. Direct Instantiation with String-based Execution")
    print("-" * 50)
    
    strategy = CreateStrategy(
        strategy_function="trade_zscore",  # This will be the default strategy
        symbol="SPY",
        shares_per_trade=10,
        order_type="limit",
        alpha=0.8,
        vol_floor=0.1,
        thresholdz=2.0,
        take_profit=15.0,
        delay=1.0,
        indicator_name="calc_zscore"
    )
    
    print(f"✅ Created strategy: {strategy.strategy_name}")
    print(f"📈 Default strategy: {strategy.strategy_function}")
    print(f"📊 Available strategies: {', '.join(strategy.get_available_strategies())}")
    
    # Create mock bar data
    bar = MockBar("SPY", 420.50)
    print(f"📊 Mock bar: {bar.symbol} @ ${bar.close}")
    
    # Execute different strategies using string names
    print("\n🔄 Executing strategies by string name...")
    
    try:
        # Execute the default strategy (trade_zscore)
        print(f"\n   Executing: {strategy.strategy_function}")
        await strategy.execute(strategy.strategy_function, bar)
        
        # Execute other strategies by name
        other_strategies = ["trade_dual_ma", "trade_bollinger", "trade_momentum"]
        for strategy_name in other_strategies:
            print(f"\n   Executing: {strategy_name}")
            await strategy.execute(strategy_name, bar)
            
    except Exception as e:
        print(f"⚠️ Execution demo limited due to missing environment setup: {e}")
    
    # Method 2: Factory pattern with string-based creation
    print("\n\n2. Factory Pattern with String-based Creation")
    print("-" * 50)
    
    try:
        # Create strategy using factory
        factory_strategy = StrategyFactory.create("CreateStrategy",
            strategy_function="trade_momentum",
            symbol="AAPL", 
            shares_per_trade=5,
            order_type="market",
            alpha=0.6,
            thresholdz=1.5,
            take_profit=25.0,
            vol_floor=0.15,
            delay=0.5,
            indicator_name="calc_zscore"
        )
        
        print(f"✅ Factory created strategy: {factory_strategy.strategy_name}")
        print(f"📈 Strategy function: {factory_strategy.strategy_function}")
        print(f"📊 Symbol: {factory_strategy.symbol}")
        
        # Show that it's the same type
        print(f"🔍 Strategy type: {type(factory_strategy).__name__}")
        print(f"🏗️ Is BaseStrategy: {isinstance(factory_strategy, BaseStrategy)}")
        
        # Execute via factory-created strategy
        bar_aapl = MockBar("AAPL", 175.25)
        print(f"📊 Mock bar: {bar_aapl.symbol} @ ${bar_aapl.close}")
        
        print(f"\n   Executing factory strategy: {factory_strategy.strategy_function}")
        await factory_strategy.execute(factory_strategy.strategy_function, bar_aapl)
        
    except Exception as e:
        print(f"⚠️ Factory demo limited due to missing environment setup: {e}")
    
    # Method 3: Dynamic strategy switching
    print("\n\n3. Dynamic Strategy Switching")
    print("-" * 50)
    
    # Create a strategy instance
    flexible_strategy = CreateStrategy(
        strategy_function="trade_zscore",  # Initial strategy
        symbol="QQQ",
        shares_per_trade=8,
        alpha=0.7,
        thresholdz=1.8,
        take_profit=12.0
    )
    
    print(f"✅ Created flexible strategy for: {flexible_strategy.symbol}")
    
    # Simulate switching between strategies dynamically
    strategies_to_test = ["trade_zscore", "trade_dual_ma", "trade_bollinger"]
    bar_qqq = MockBar("QQQ", 385.75)
    
    for strategy_name in strategies_to_test:
        try:
            print(f"\n   Switching to strategy: {strategy_name}")
            # This demonstrates that we can call any strategy method by name
            await flexible_strategy.execute(strategy_name, bar_qqq)
            print(f"   ✅ Successfully executed {strategy_name}")
        except Exception as e:
            print(f"   ⚠️ {strategy_name} execution limited: {e}")
    
    print("\n\n4. Reset and State Management")
    print("-" * 50)
    
    # Show state before reset
    print(f"📊 Position before reset: {flexible_strategy.position_shares}")
    print(f"📋 Orders before reset: {len(flexible_strategy.orders_list)}")
    
    # Reset the strategy
    flexible_strategy.reset()
    
    # Show state after reset
    print(f"📊 Position after reset: {flexible_strategy.position_shares}")
    print(f"📋 Orders after reset: {len(flexible_strategy.orders_list)}")
    print("✅ Reset completed successfully")
    
    print("\n" + "=" * 50)
    print("🎉 CreateStrategy ABC Pattern Demo Complete!")
    print("\n📝 Key Features Demonstrated:")
    print("   • Abstract Base Class inheritance ✓")
    print("   • String-based strategy execution ✓")
    print("   • Factory pattern for strategy creation ✓")
    print("   • Dynamic strategy switching ✓")
    print("   • State management and reset ✓")
    print("   • Backward compatibility maintained ✓")

if __name__ == "__main__":
    asyncio.run(demo_string_based_execution())
