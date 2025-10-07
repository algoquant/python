"""
Script for parsing the arguments the command line input.

Examples of command line inputs:
    python3 parse_arguments.py trade_zscore SPY --order_type limit --alpha 0.3
    python3 parse_arguments.py trade_zscore AAPL --shares_per_trade 10 --thresholdz 2.0 --delay 5.0

Shows help then prompts interactively
    python3 parse_arguments.py

Minimal command with defaults
    python3 parse_arguments.py trade_zscore SPY

No prompts, proceeds directly with custom values
    python3 parse_arguments.py trade_zscore SPY --shares_per_trade 10 --order_type limit --alpha 0.3 --thresholdz 2.0 --vol_floor 0.1 --take_profit 20.0 --delay 0.0

Force interactive even with all args
    python3 parse_arguments.py trade_zscore SPY --interactive

"""

import argparse
import sys
from zoneinfo import ZoneInfo


class GetArgs:
    """Class for handling command line argument parsing and user interaction"""
    
    def __init__(self):
        self.arguments = {}
        self.args = None
    
    def get_user_input(self, prompt, default_value, value_type=str, choices=None):
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

    # end get_user_input


    def parse_arguments(self):
        """Parse command line arguments and populate the arguments dictionary"""
        parser = argparse.ArgumentParser(
            description="Trading strategy using Alpaca API",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  python3 parse_arguments.py trade_zscore SPY --shares_per_trade 1 --type limit --alpha 0.3
  python3 parse_arguments.py trade_zscore AAPL --shares_per_trade 10 --thresholdz 2.0 --delay 5.0
  python3 parse_arguments.py --interactive  # Force interactive mode
                """
        )
        
        # Timezone first
        parser.add_argument("--timezone", default=ZoneInfo("America/New_York"),
                           help="Timezone for operations (default: America/New_York)")
        
        # Required arguments
        parser.add_argument("strategy_function", nargs="?", help="Name of the trading strategy function (default: trade_zscore)")
        parser.add_argument("symbol", nargs="?", help="Stock symbol to trade (e.g., SPY, AAPL)")
        
        # Optional arguments in specified order
        parser.add_argument("--shares_per_trade", type=float, default=1.0, 
                           help="Number of shares per trade (default: 1.0)")
        parser.add_argument("--type", choices=["market", "limit"], default="market",
                           help="Order type: market or limit (default: market)")
        parser.add_argument("--alpha", type=float, default=0.9,
                           help="EMA decay factor 0 < alpha <= 1 (default: 0.9) - larger values produce smoother EMA")
        parser.add_argument("--vol_floor", type=float, default=0.1,
                           help="Minimum volatility floor (default: 0.1)")
        parser.add_argument("--thresholdz", type=float, default=1.0,
                           help="The Z-score threshold (default: 1.0) - trade if the Z-score exceeds the threshold")
        parser.add_argument("--take_profit", type=float, default=20.0,
                           help="Take profit factor (default: 20.0) - Take profit if the unrealized PnL exceeds the factor times the volatility")
        parser.add_argument("--delay", type=float, default=0.0,
                           help="Delay the trade order submission in seconds (default: 0.0) - to avoid different strategies from submitting at the same time")
        parser.add_argument("--strategy_name", default=None,
                           help="Custom name for the trading strategy (default: auto-generated)")
        parser.add_argument("--env_file", default=None,
                           help="Path to .env file for API keys (default: .env or system environment)")
        parser.add_argument("--trade_key", default=None,
                           help="Environment variable name for trading API key (default: ALPACA_TRADE_KEY)")
        parser.add_argument("--trade_secret", default=None,
                           help="Environment variable name for trading API secret (default: ALPACA_TRADE_SECRET)")
        parser.add_argument("--interactive", action="store_true",
                           help="Force interactive mode even if all arguments are provided")

        self.args = parser.parse_args()
        
        # Populate the arguments dictionary
        self.arguments = {
            'timezone': self.args.timezone,
            'strategy_function': self.args.strategy_function,
            'symbol': self.args.symbol,
            'shares_per_trade': self.args.shares_per_trade,
            'type': self.args.type,
            'alpha': self.args.alpha,
            'vol_floor': self.args.vol_floor,
            'thresholdz': self.args.thresholdz,
            'take_profit': self.args.take_profit,
            'delay': self.args.delay,
            'strategy_name': self.args.strategy_name,
            'env_file': self.args.env_file,
            'trade_key': self.args.trade_key,
            'trade_secret': self.args.trade_secret,
            'interactive': self.args.interactive
        }
        
        return self.args

    # end parse_arguments



    def prompt_for_missing_args(self):
        """Prompt user for any missing arguments and update arguments dictionary"""
        
        print("\n=== Trading Strategy Configuration ===")
        print("Press Enter to use default values shown in parentheses\n")
        
        # Timezone (now has default, but can still be overridden interactively)
        if str(self.args.timezone) == "America/New_York":  # Only prompt if still using default
            new_timezone = self.get_user_input("Timezone", "America/New_York")
            if new_timezone != "America/New_York":
                try:
                    self.args.timezone = ZoneInfo(new_timezone)
                    self.arguments['timezone'] = self.args.timezone
                except Exception as e:
                    print(f"Invalid timezone '{new_timezone}': {e}")
                    print("Using default timezone: America/New_York")
                    self.args.timezone = ZoneInfo("America/New_York")  # Explicitly set to ZoneInfo object
                    self.arguments['timezone'] = self.args.timezone
        
        # Strategy function (first argument)
        if not self.args.strategy_function:
            self.args.strategy_function = self.get_user_input("Trading strategy function name", "trade_zscore")
            self.arguments['strategy_function'] = self.args.strategy_function
        
        # Symbol (second argument)
        if not self.args.symbol:
            self.args.symbol = self.get_user_input("Enter stock symbol", "SPY").upper()
            self.arguments['symbol'] = self.args.symbol
        
        # Shares per trade
        if self.args.shares_per_trade is None:
            self.args.shares_per_trade = self.get_user_input("Number of shares per trade", 1.0, float)
            self.arguments['shares_per_trade'] = self.args.shares_per_trade
        
        # Order type
        if self.args.type is None:
            self.args.type = self.get_user_input("Order type", "market", str, ["market", "limit"])
            self.arguments['type'] = self.args.type
        
        # Alpha (EMA decay factor)
        if self.args.alpha is None:
            while True:
                self.args.alpha = self.get_user_input("EMA decay factor (0 < alpha <= 1)", 0.9, float)
                if 0 < self.args.alpha <= 1:
                    break
                print("Alpha must be between 0 and 1")
            self.arguments['alpha'] = self.args.alpha
        
        # Volatility floor
        if self.args.vol_floor is None:
            while True:
                self.args.vol_floor = self.get_user_input("Minimum volatility floor", 0.1, float)
                if self.args.vol_floor >= 0:
                    break
                print("Volatility floor must be non-negative")
            self.arguments['vol_floor'] = self.args.vol_floor
        
        # Risk premium (Z-score threshold)
        if self.args.thresholdz is None:
            while True:
                self.args.thresholdz = self.get_user_input("Z-score threshold for trading", 1.0, float)
                if self.args.thresholdz > 0:
                    break
                print("Risk premium must be positive")
            self.arguments['thresholdz'] = self.args.thresholdz
        
        # Take profit factor
        if self.args.take_profit is None:
            while True:
                self.args.take_profit = self.get_user_input("Take profit factor", 20.0, float)
                if self.args.take_profit > 0:
                    break
                print("Take profit factor must be positive")
            self.arguments['take_profit'] = self.args.take_profit
        
        # Delay
        if self.args.delay is None:
            while True:
                self.args.delay = self.get_user_input("Order submission delay (seconds)", 0.0, float)
                if self.args.delay >= 0:
                    break
                print("Delay must be non-negative")
            self.arguments['delay'] = self.args.delay
        
        # Strategy name (optional)
        if self.args.strategy_name is None:
            self.args.strategy_name = self.get_user_input("Custom strategy name (optional)", "", str)
            if not self.args.strategy_name:  # If empty string, set to None for auto-generation
                self.args.strategy_name = None
            self.arguments['strategy_name'] = self.args.strategy_name
        
        # Environment file (optional)
        if self.args.env_file is None:
            self.args.env_file = self.get_user_input("Path to .env file (optional)", "", str)
            if not self.args.env_file:  # If empty string, set to None for default behavior
                self.args.env_file = None
            self.arguments['env_file'] = self.args.env_file
        
        # Trade key environment variable name (optional)
        if self.args.trade_key is None:
            self.args.trade_key = self.get_user_input("Trading API key environment variable name (optional)", "", str)
            if not self.args.trade_key:  # If empty string, set to None for default
                self.args.trade_key = None
            self.arguments['trade_key'] = self.args.trade_key
        
        # Trade secret environment variable name (optional)
        if self.args.trade_secret is None:
            self.args.trade_secret = self.get_user_input("Trading API secret environment variable name (optional)", "", str)
            if not self.args.trade_secret:  # If empty string, set to None for default
                self.args.trade_secret = None
            self.arguments['trade_secret'] = self.args.trade_secret
        
        return self.args

    # end prompt_for_missing_args


    def confirm_parameters(self):
        """Show final parameters and ask for confirmation"""
        print("\n=== Final Trading Parameters ===")
        print(f"Timezone: {self.args.timezone}")
        print(f"Strategy function: {self.args.strategy_function}")
        print(f"Symbol: {self.args.symbol}")
        print(f"Shares per trade: {self.args.shares_per_trade}")
        print(f"Order type: {self.args.type}")
        print(f"EMA alpha: {self.args.alpha}")
        print(f"Volatility floor: {self.args.vol_floor}")
        print(f"Risk premium (Z-score threshold): {self.args.thresholdz}")
        print(f"Take profit factor: {self.args.take_profit}")
        print(f"Order delay: {self.args.delay} seconds")
        print(f"Strategy name: {self.args.strategy_name if self.args.strategy_name else 'Auto-generated'}")
        print(f"Environment file: {self.args.env_file if self.args.env_file else 'Default (.env or system)'}")
        print(f"Trade key variable: {self.args.trade_key if self.args.trade_key else 'ALPACA_TRADE_KEY'}")
        print(f"Trade secret variable: {self.args.trade_secret if self.args.trade_secret else 'ALPACA_TRADE_SECRET'}")
        
        while True:
            confirm = input("\nProceed with these parameters? (y/n): ").strip().lower()
            if confirm in ["y", "yes"]:
                return True
            elif confirm in ["n", "no"]:
                return False
            else:
                print("Please enter \'y\' or \'n\'")

    # end confirm_parameters


# Backward compatibility functions
def get_user_input(prompt, default_value, value_type=str, choices=None):
    """Backward compatibility wrapper for get_user_input"""
    args_handler = GetArgs()
    return args_handler.get_user_input(prompt, default_value, value_type, choices)

def parse_arguments():
    """Backward compatibility wrapper for parse_arguments"""
    args_handler = GetArgs()
    return args_handler.parse_arguments()

def prompt_for_missing_args(args):
    """Backward compatibility wrapper for prompt_for_missing_args"""
    args_handler = GetArgs()
    args_handler.args = args
    # Update arguments dictionary from args
    args_handler.arguments = {
        'timezone': args.timezone,
        'strategy_function': args.strategy_function,
        'symbol': args.symbol,
        'shares_per_trade': args.shares_per_trade,
        'type': args.type,
        'alpha': args.alpha,
        'vol_floor': args.vol_floor,
        'thresholdz': args.thresholdz,
        'take_profit': args.take_profit,
        'delay': args.delay,
        'strategy_name': args.strategy_name,
        'env_file': args.env_file,
        'trade_key': args.trade_key,
        'trade_secret': args.trade_secret,
        'interactive': args.interactive
    }
    return args_handler.prompt_for_missing_args()

def confirm_parameters(args):
    """Backward compatibility wrapper for confirm_parameters"""
    args_handler = GetArgs()
    args_handler.args = args
    return args_handler.confirm_parameters()


if __name__ == "__main__":
    # Create GetArgs instance
    args_handler = GetArgs()
    
    # Parse command line arguments
    args = args_handler.parse_arguments()
    # Check if we need interactive mode
    missing_args = (
        not args.strategy_function or
        not args.symbol or 
        args.shares_per_trade is None or 
        args.type is None or 
        args.alpha is None or 
        args.vol_floor is None or 
        args.thresholdz is None or 
        args.take_profit is None or 
        args.delay is None or
        args.interactive
    )
    
    # Show help if no arguments provided at all
    if len(sys.argv) == 1:
        print("🚀 Trading Strategy Configuration")
        print("=" * 50)
        parser = argparse.ArgumentParser(
            description="Trading strategy using Alpaca API",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  python3 parse_arguments.py trade_zscore SPY --shares_per_trade 1 --type limit --alpha 0.3
  python3 parse_arguments.py trade_zscore AAPL --shares_per_trade 10 --thresholdz 2.0 --delay 5.0
  python3 parse_arguments.py --interactive  # Force interactive mode
            """
        )
        parser.add_argument("strategy_function", nargs="?", help="Name of the trading strategy function (default: trade_zscore)")
        parser.add_argument("symbol", nargs="?", help="Stock symbol to trade (e.g., SPY, AAPL)")
        parser.add_argument("--timezone", help="Timezone for operations (default: America/New_York)")
        parser.add_argument("--shares_per_trade", type=float, help="Number of shares per trade (default: 1.0)")
        parser.add_argument("--type", choices=["market", "limit"], help="Order type (default: limit)")
        parser.add_argument("--alpha", type=float, help="EMA decay factor 0 < alpha <= 1 (default: 0.1)")
        parser.add_argument("--vol_floor", type=float, help="Minimum volatility floor (default: 0.1)")
        parser.add_argument("--thresholdz", type=float, help="Z-score threshold (default: 2.0)")
        parser.add_argument("--take_profit", type=float, help="Take profit factor (default: 20.0)")
        parser.add_argument("--delay", type=float, help="Order delay in seconds (default: 0.0)")
        parser.add_argument("--strategy_name", help="Custom strategy name (default: auto-generated)")
        parser.add_argument("--env_file", help="Path to .env file (default: .env or system)")
        parser.add_argument("--trade_key", help="API key environment variable (default: ALPACA_TRADE_KEY)")
        parser.add_argument("--trade_secret", help="API secret environment variable (default: ALPACA_TRADE_SECRET)")
        parser.add_argument("--interactive", action="store_true", help="Force interactive mode")
        
        parser.print_help()
        print("\n❌ Error: At least one argument is required.")
        print("💡 Use --interactive flag to enter interactive mode, or provide at least a symbol.")
        sys.exit(1)
    
    if missing_args:
        if len(sys.argv) > 1:  # Only show this message if some args were provided
            print("Some arguments are missing or --interactive mode requested.")
        args = args_handler.prompt_for_missing_args()
        
        # Confirm parameters
        if not args_handler.confirm_parameters():
            print("Operation cancelled by user.")
            sys.exit(0)
    
    print(f"\n✅ Trading parameters confirmed:")
    print(f"Timezone: {args.timezone}, Strategy: {args.strategy_function}, Symbol: {args.symbol}")
    print(f"Shares: {args.shares_per_trade}, Type: {args.type}, Alpha: {args.alpha}, Vol Floor: {args.vol_floor}")
    print(f"Threshold: {args.thresholdz}, Take Profit: {args.take_profit}, Delay: {args.delay}")
    print(f"Name: {args.strategy_name if args.strategy_name else 'Auto-generated'}, Env: {args.env_file if args.env_file else 'Default'}")
    print(f"Key Var: {args.trade_key if args.trade_key else 'ALPACA_TRADE_KEY'}, Secret Var: {args.trade_secret if args.trade_secret else 'ALPACA_TRADE_SECRET'}\n")
    
    print("🚀 Ready to start trading strategy!")
    
    # Print the arguments dictionary for demonstration
    print(f"\n📋 Arguments Dictionary:")
    for key, value in args_handler.arguments.items():
        print(f"  {key}: {value}")

