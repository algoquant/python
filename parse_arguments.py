"""
Demonstration of parsing the arguments from a command line input.

Examples of command line inputs:
  python3 parse_arguments.py SPY --shares 1 --type limit --alpha 0.3
  python3 parse_arguments.py AAPL --shares 10 --risk-premium 2.0 --delay 5.0

"""

import argparse
import sys

def get_user_input(prompt, default_value, value_type=str, choices=None):
    """Get user input with validation and default values"""
    while True:
        if choices:
            prompt_text = f"{prompt} {choices} (default: {default_value}): "
        else:
            prompt_text = f"{prompt} (default: {default_value}): "
        
        user_input = input(prompt_text).strip()
        
        # Use default if empty
        if not user_input:
            return default_value
        
        # Validate choices
        if choices and user_input not in choices:
            print(f"Invalid choice. Please select from {choices}")
            continue
        
        # Type conversion
        try:
            if value_type == float:
                return float(user_input)
            elif value_type == int:
                return int(user_input)
            else:
                return user_input
        except ValueError:
            print(f"Invalid input. Please enter a valid {value_type.__name__}")
            continue

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Bollinger Bands trading strategy using Alpaca API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 strat_bollinger_bars_proxy.py SPY --shares 1 --type limit --alpha 0.3
  python3 strat_bollinger_bars_proxy.py AAPL --shares 10 --risk-premium 2.0 --delay 5.0
        """
    )
    
    # Required arguments
    parser.add_argument('symbol', nargs='?', help='Stock symbol to trade (e.g., SPY, AAPL)')
    
    # Optional arguments with defaults
    parser.add_argument('--shares', type=float, default=None, 
                       help='Number of shares per trade (default: 1.0)')
    parser.add_argument('--type', choices=['market', 'limit'], default=None,
                       help='Order type: market or limit (default: limit)')
    parser.add_argument('--alpha', type=float, default=None,
                       help='EMA decay factor 0 < alpha <= 1 (default: 0.1) - larger values produce smoother EMA')
    parser.add_argument('--vol_floor', type=float, default=None,
                       help='Minimum volatility floor (default: 0.1)')
    parser.add_argument('--risk_premium', type=float, default=None,
                       help='The Z-score threshold (default: 2.0) - trade if the Z-score exceeds the threshold')
    parser.add_argument('--take_profit', type=float, default=None,
                       help='Take profit factor (default: 20.0) - Take profit if the unrealized PnL exceeds the factor times the volatility')
    parser.add_argument('--delay', type=float, default=None,
                       help='Delay the trade order submission in seconds (default: 0.0) - to avoid different strategies from submitting at the same time')
    parser.add_argument('--strategy', default=None,
                       help='Name of the trading strategy function (default: trade_zscore)')
    parser.add_argument('--interactive', action='store_true',
                       help='Force interactive mode even if all arguments are provided')

    return parser.parse_args()

# end parse_arguments


def prompt_for_missing_args(args):
    """Prompt user for any missing arguments"""
    
    print("\n=== Trading Strategy Configuration ===")
    print("Press Enter to use default values shown in parentheses\n")
    
    # Symbol (required)
    if not args.symbol:
        args.symbol = get_user_input("Enter stock symbol", "SPY").upper()
    
    # Shares per trade
    if args.shares is None:
        args.shares = get_user_input("Number of shares per trade", 1.0, float)
    
    # Order type
    if args.type is None:
        args.type = get_user_input("Order type", "limit", str, ['market', 'limit'])
    
    # Alpha (EMA decay factor)
    if args.alpha is None:
        while True:
            args.alpha = get_user_input("EMA decay factor (0 < alpha <= 1)", 0.1, float)
            if 0 < args.alpha <= 1:
                break
            print("Alpha must be between 0 and 1")
    
    # Volatility floor
    if args.vol_floor is None:
        while True:
            args.vol_floor = get_user_input("Minimum volatility floor", 0.1, float)
            if args.vol_floor >= 0:
                break
            print("Volatility floor must be non-negative")
    
    # Risk premium (Z-score threshold)
    if args.risk_premium is None:
        while True:
            args.risk_premium = get_user_input("Z-score threshold for trading", 2.0, float)
            if args.risk_premium > 0:
                break
            print("Risk premium must be positive")
    
    # Take profit factor
    if args.take_profit is None:
        while True:
            args.take_profit = get_user_input("Take profit factor", 20.0, float)
            if args.take_profit > 0:
                break
            print("Take profit factor must be positive")
    
    # Delay
    if args.delay is None:
        while True:
            args.delay = get_user_input("Order submission delay (seconds)", 0.0, float)
            if args.delay >= 0:
                break
            print("Delay must be non-negative")
    
    # Strategy function
    if args.strategy is None:
        args.strategy = get_user_input("Trading strategy function name", "trade_zscore")
    
    return args

# end prompt_for_missing_args


def confirm_parameters(args):
    """Show final parameters and ask for confirmation"""
    print("\n=== Final Trading Parameters ===")
    print(f"Symbol: {args.symbol}")
    print(f"Shares per trade: {args.shares}")
    print(f"Order type: {args.type}")
    print(f"EMA alpha: {args.alpha}")
    print(f"Volatility floor: {args.vol_floor}")
    print(f"Risk premium (Z-score threshold): {args.risk_premium}")
    print(f"Take profit factor: {args.take_profit}")
    print(f"Order delay: {args.delay} seconds")
    print(f"Strategy function: {args.strategy}")
    
    while True:
        confirm = input("\nProceed with these parameters? (y/n): ").strip().lower()
        if confirm in ['y', 'yes']:
            return True
        elif confirm in ['n', 'no']:
            return False
        else:
            print("Please enter 'y' or 'n'")

# end confirm_parameters


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    # Check if we need interactive mode
    missing_args = (
        not args.symbol or 
        args.shares is None or 
        args.type is None or 
        args.alpha is None or 
        args.vol_floor is None or 
        args.risk_premium is None or 
        args.take_profit is None or 
        args.delay is None or 
        args.strategy is None or
        args.interactive
    )
    
    if missing_args:
        print("Some arguments are missing or --interactive mode requested.")
        args = prompt_for_missing_args(args)
        
        # Confirm parameters
        if not confirm_parameters(args):
            print("Operation cancelled by user.")
            sys.exit(0)
    
    print(f"\n✅ Trading parameters confirmed:")
    print(f"Symbol: {args.symbol}, Type: {args.type}, "
          f"Shares: {args.shares}, Alpha: {args.alpha}, "
          f"Risk Premium: {args.risk_premium}, Vol Floor: {args.vol_floor}, "
          f"Take Profit: {args.take_profit}, Delay: {args.delay}, "
          f"Strategy: {args.strategy}\n")
    
    print("🚀 Ready to start trading strategy!")
