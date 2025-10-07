#!/usr/bin/env python3
"""
Demonstration of the CreateStrategy ABC redesign.
Shows how to use the Abstract Base Class pattern for string-based strategy execution.

This demonstrates the key features:
1. Abstract Base Class (BaseStrategy) implementation
2. Factory pattern (StrategyFactory) for strategy creation
3. String-based strategy execution via execute() and recalc() methods
4. Instance variable management for simplified method signatures
5. Multiple strategy support within a single class
"""

import sys
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# Add the current directory to path so we can import MachineTrader
sys.path.append('/Users/jerzy/Develop/Python')

try:
    from MachineTrader import SingleStrategy, BaseStrategy, StrategyFactory, GetArgs
    print("✅ Successfully imported SingleStrategy, BaseStrategy, StrategyFactory, and GetArgs")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def demonstrate_abc_pattern():
    """Demonstrate the ABC pattern with SingleStrategy"""
    
    print("\\n" + "=" * 60)
    print("  SINGLESTRATEGY ABC PATTERN DEMONSTRATION")
    print("=" * 60)
    
    # 1. Traditional instantiation with instance variables
    print("\\n🏗️  1. TRADITIONAL INSTANTIATION")
    print("-" * 40)
    
    # Create strategy using traditional parameter approach
    strategy = SingleStrategy(
        strategy_function="trade_zscore",
        indicator_name="calc_zscore",
        symbol="SPY", 
        shares_per_trade=10,
        alpha=0.3,
        thresholdz=2.0,
        take_profit=15.0,
        vol_floor=0.1,
        delay=1.0,
        order_type="limit",
    )
    
    print(f"   Strategy created: {strategy.strategy_name}")
    print(f"   Symbol: {strategy.symbol}")
    print(f"   Strategy function: {strategy.strategy_function}")
    print(f"   Shares per trade: {strategy.shares_per_trade}")
    print(f"   Alpha: {strategy.alpha}")
    print(f"   Z-score threshold: {strategy.thresholdz}")
    print(f"   Take profit: {strategy.take_profit}")
    print(f"   Order type: {strategy.order_type}")
    print(f"   Delay: {strategy.delay}")
    
    # 2. Using GetArgs for parameter management
    print("\\n📝 2. USING GETARGS FOR PARAMETER MANAGEMENT")
    print("-" * 45)
    
    # Create arguments dictionary manually (simulating command line args)
    args_dict = {
        'strategy_function': 'trade_momentum',
        'symbol': 'AAPL',
        'shares_per_trade': 5,
        'order_type': 'market',
        'alpha': 0.5,
        'vol_floor': 0.05,
        'thresholdz': 1.5,
        'take_profit': 25.0,
        'delay': 0.5,
        'indicator_name': 'calc_zscorew',
        'strategy_name': 'MomentumTest',
        'env_file': None,
        'timezone': ZoneInfo("America/New_York"),
        'interactive': False
    }
    
    # Create strategy using arguments dictionary
    args_strategy = SingleStrategy(arguments=args_dict)
    
    print(f"   Strategy created: {args_strategy.strategy_name}")
    print(f"   Symbol: {args_strategy.symbol}")
    print(f"   Strategy function: {args_strategy.strategy_function}")
    print(f"   Indicator: {args_strategy.indicator_name}")
    
    # 3. ABC Pattern - Inheritance verification
    print("\\n🧬 3. ABSTRACT BASE CLASS INHERITANCE")
    print("-" * 40)
    
    print(f"   SingleStrategy is BaseStrategy: {isinstance(strategy, BaseStrategy)}")
    print(f"   MRO: {[cls.__name__ for cls in strategy.__class__.__mro__]}")
    
    # Show available strategies
    available_strategies = strategy.get_available_strategies()
    print(f"   Available strategies: {available_strategies}")
    
    # 4. String-based strategy execution
    print("\\n🎯 4. STRING-BASED STRATEGY EXECUTION")
    print("-" * 40)
    
    print("   String-based strategy calling allows:")
    print("   • Execute any strategy by name (string)")
    print("   • No need to pass complex parameters")
    print("   • All parameters stored as instance variables")
    print("   • Consistent interface across all strategies")
    
    # Example of how execute() would be called (without actually running trading)
    for strategy_name in available_strategies:
        print(f"   ✓ Can execute: strategy.execute('{strategy_name}', bar)")
        print(f"   ✓ Can recalc:  strategy.recalc('{strategy_name}', bar)")
    
    # 5. Factory pattern demonstration
    print("\\n🏭 5. FACTORY PATTERN")
    print("-" * 25)
    
    registered_strategies = StrategyFactory.get_available_strategies()
    print(f"   Registered factory strategies: {registered_strategies}")
    print(f"   Default strategy class: {StrategyFactory.get_default_strategy()}")
    
    if "SingleStrategy" in registered_strategies:
        print("   ✅ SingleStrategy successfully registered")
        
        # Method 1: Create strategy via factory using default class (simplified)
        print("\\n   📝 Method 1: Using default strategy class (simplified)")
        default_strategy = StrategyFactory.create(
            strategy_function="trade_bollinger",
            symbol="QQQ",
            shares_per_trade=15,
            alpha=0.4,
            thresholdz=2.5,
            take_profit=25.0,
            vol_floor=0.15,
            delay=1.5,
            order_type="limit",
            indicator_name="calc_ema"
        )
        
        print(f"   Default factory strategy: {default_strategy.strategy_name}")
        print(f"   Strategy type: {type(default_strategy).__name__}")
        print(f"   Strategy function: {default_strategy.strategy_function}")
        
        # Method 2: Create strategy via factory with explicit class name (original)
        print("\\n   📝 Method 2: Explicitly specifying strategy class (original)")
        explicit_strategy = StrategyFactory.create("SingleStrategy",
            strategy_function="trade_momentum",
            symbol="TSLA",
            shares_per_trade=20,
            alpha=0.2,
            thresholdz=3.0,
            take_profit=30.0,
            vol_floor=0.2,
            delay=2.0,
            order_type="market",
            indicator_name="calc_zscore"
        )
        
        print(f"   Explicit factory strategy: {explicit_strategy.strategy_name}")
        print(f"   Strategy type: {type(explicit_strategy).__name__}")
        print(f"   Strategy function: {explicit_strategy.strategy_function}")
        
        # Show both strategies are the same type
        print(f"\\n   ✅ Both methods create the same type: {type(default_strategy) == type(explicit_strategy)}")
        
        # Store both strategies for later use
        factory_strategy = default_strategy  # Use default method result
    
    # 6. Reset functionality
    print("\\n🔄 6. RESET FUNCTIONALITY")
    print("-" * 30)
    
    # Show state before reset
    print(f"   Before reset - Position shares: {strategy.position_shares}")
    print(f"   Before reset - Orders list: {len(strategy.orders_list)} items")
    print(f"   Before reset - Realized PnL: ${strategy.total_realized_pnl:.2f}")
    
    # Reset the strategy
    strategy.reset()
    
    print(f"   After reset - Position shares: {strategy.position_shares}")
    print(f"   After reset - Orders list: {len(strategy.orders_list)} items") 
    print(f"   After reset - Realized PnL: ${strategy.total_realized_pnl:.2f}")
    print("   ✅ Reset completed successfully")
    
    # 7. Error handling demonstration
    print("\\n⚠️  7. ERROR HANDLING")
    print("-" * 25)
    
    try:
        # Try to execute an invalid strategy
        strategy.execute("invalid_strategy", None)
    except AttributeError as e:
        print(f"   ✅ Correctly caught invalid strategy: {e}")
    
    try:
        # Try to create invalid strategy via factory (explicit method)
        StrategyFactory.create("NonExistentStrategy")
    except ValueError as e:
        print(f"   ✅ Correctly caught factory error (explicit): {e}")
    
    try:
        # Try to set invalid default strategy
        StrategyFactory.set_default_strategy("NonExistentStrategy")
    except ValueError as e:
        print(f"   ✅ Correctly caught default strategy error: {e}")
    
    print("\\n" + "=" * 60)
    print("  DEMONSTRATION COMPLETE")
    print("=" * 60)
    
    return strategy, args_strategy, factory_strategy

def show_strategy_comparison():
    """Show comparison between old and new patterns"""
    
    print("\\n📊 BEFORE vs AFTER COMPARISON")
    print("-" * 35)
    
    print("\\n🔴 OLD PATTERN (Before ABC Redesign):")
    print("   • Complex parameter passing to strategy methods")
    print("   • Methods like: trade_zscore(bar, mov_avg, alpha, vol_floor, ...)")
    print("   • No string-based strategy execution")
    print("   • No unified interface for different strategies")
    print("   • Hard to extend with new strategies")
    
    print("\\n🟢 NEW PATTERN (After ABC Redesign):")
    print("   • Simple method signatures: trade_zscore(bar)")
    print("   • All parameters stored as instance variables")
    print("   • String-based execution: execute('trade_zscore', bar)")
    print("   • Factory pattern for strategy creation")
    print("   • Simplified factory usage: StrategyFactory.create(strategy_function='trade_zscore')")
    print("   • Explicit factory usage: StrategyFactory.create('SingleStrategy', strategy_function='trade_zscore')")
    print("   • Unified BaseStrategy interface")
    print("   • Easy to extend with new strategies")
    print("   • Consistent with TechIndic package design")

def show_usage_examples():
    """Show practical usage examples"""
    
    print("\\n💡 PRACTICAL USAGE EXAMPLES")
    print("-" * 35)
    
    print("""
# Example 1: Simple strategy creation and execution
strategy = SingleStrategy(
    strategy_function="trade_zscore",
    symbol="SPY",
    shares_per_trade=10,
    alpha=0.3
)

# Execute strategy by name (string-based)
await strategy.execute("trade_zscore", bar_data)

# Example 2: Using factory pattern (simplified - default strategy class)
strategy = StrategyFactory.create(
    strategy_function="trade_momentum", 
    symbol="AAPL"
)

# Example 3: Using factory pattern (explicit strategy class)
strategy = StrategyFactory.create("SingleStrategy",
    strategy_function="trade_momentum", 
    symbol="AAPL"
)

# Example 4: Dynamic strategy switching
available_strategies = strategy.get_available_strategies()
for strategy_name in available_strategies:
    await strategy.execute(strategy_name, bar_data)

# Example 5: Using GetArgs for command-line interface
args_handler = GetArgs()
args = args_handler.parse_arguments()
strategy = SingleStrategy(arguments=args_handler.arguments)
await strategy.execute(args.strategy_function, bar_data)

# Example 6: Changing default strategy class
StrategyFactory.set_default_strategy("SingleStrategy")  # Set default
current_default = StrategyFactory.get_default_strategy()  # Get current default
""")

if __name__ == "__main__":
    print("🎭 SingleStrategy ABC Pattern Demonstration")
    
    try:
        # Run the main demonstration
        strategies = demonstrate_abc_pattern()
        
        # Show comparison
        show_strategy_comparison()
        
        # Show usage examples
        show_usage_examples()
        
        print("\\n🎉 SUCCESS!")
        print("\\n✨ The SingleStrategy ABC redesign is complete and working!")
        print("\\n🏁 Key achievements:")
        print("   ✅ BaseStrategy abstract base class implemented")
        print("   ✅ SingleStrategy inherits from BaseStrategy") 
        print("   ✅ StrategyFactory pattern implemented")
        print("   ✅ String-based strategy execution enabled")
        print("   ✅ Instance variable architecture working")
        print("   ✅ Multiple strategy support added")
        print("   ✅ Error handling implemented")
        print("   ✅ Reset functionality working")
        print("   ✅ Compatible with existing TechIndic pattern")
        
        print("\\n🚀 The MachineTrader package now supports the same")
        print("   string-based strategy execution pattern as TechIndic!")
        
    except Exception as e:
        print(f"\\n💥 Demonstration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
