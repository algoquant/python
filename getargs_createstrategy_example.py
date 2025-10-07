#!/usr/bin/env python3
"""
Example of using GetArgs and CreateStrategy together

This example shows how to:
1. Parse command line arguments using GetArgs
2. Pass the arguments dictionary to CreateStrategy
3. Create a trading strategy with all parsed parameters
"""

from MachineTrader import GetArgs, CreateStrategy

def main():
    """Main function demonstrating GetArgs -> CreateStrategy workflow"""
    
    # Step 1: Parse command line arguments
    print("🔧 Parsing command line arguments...")
    args_handler = GetArgs()
    args = args_handler.parse_arguments()
    
    # Step 2: Display parsed arguments
    print("\n📋 Parsed Arguments:")
    for key, value in args_handler.arguments.items():
        if value is not None:
            print(f"  {key}: {value}")
    
    # Step 3: Create trading strategy using arguments dictionary
    print("\n🚀 Creating trading strategy...")
    strategy = CreateStrategy(arguments=args_handler.arguments)
    
    # Step 4: Display strategy details
    print(f"\n✅ Strategy '{strategy.strategy_name}' created successfully!")
    print(f"  Symbol: {strategy.symbol}")
    print(f"  Shares per trade: {strategy.shares_per_trade}")
    print(f"  Order type: {strategy.order_type}")
    print(f"  Alpha (EMA factor): {strategy.alpha}")
    print(f"  Z-score threshold: {strategy.thresholdz}")
    print(f"  Take profit: {strategy.take_profit}")
    print(f"  Delay: {strategy.delay} seconds")
    print(f"  Timezone: {strategy.timezone}")
    
    return strategy

if __name__ == "__main__":
    """
    Example usage:
    
    python3 getargs_createstrategy_example.py trade_zscore AAPL --shares_per_trade 10 --alpha 0.8
    python3 getargs_createstrategy_example.py trade_zscore SPY --order_type limit --thresholdz 1.5 --strategy_name "MyStrategy"
    python3 getargs_createstrategy_example.py --interactive
    """
    strategy = main()
