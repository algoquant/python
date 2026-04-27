"""
Package MachineTrader containing 
the class GetArgs for command line argument parsing,
the class BaseStrategy as abstract base class for trading strategies,
the class StrategyFactory for creating strategies by name,
and the class SingleStockStrategy for implementing trading strategies.

The Bar class has been moved to TechIndic package.

from MachineTrader import SingleStockStrategy, GetArgs, BaseStrategy, StrategyFactory
from TechIndic import Bar

"""

import os
import argparse
import sys
import time
import math
import pandas as pd
from abc import ABC, abstractmethod
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from alpaca.trading.enums import OrderSide
from AlpacaSDK import AlpacaSDK, Trading
from TechIndic import IndicatorFactory, create_indicator, validate_indicator_name, Bar
from utils import convert_to_nytzone


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

    def parse_arguments(self):
        """Parse command line arguments and populate the arguments dictionary"""
        parser = argparse.ArgumentParser(
            description="Trading strategy using Alpaca API",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  python3 parse_arguments.py trade_zscore SPY --shares_per_trade 1 --order_type limit --alpha 0.3
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
                           help="Number of shares per trade (default: 1)")
        parser.add_argument("--order_type", choices=["market", "limit"], default="market",
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
        parser.add_argument("--indicator_name", default="calc_zscore",
                           help="Name of the technical indicator to use (default: calc_zscore)")
        parser.add_argument("--strategy_name", default=None,
                           help="Custom name for the trading strategy (default: auto-generated)")
        parser.add_argument("--env_file", default=None,
                           help="Path to .env file for API keys (default: .env or system environment)")
        parser.add_argument("--interactive", action="store_true",
                           help="Force interactive mode even if all arguments are provided")

        self.args = parser.parse_args()
        
        # Populate the arguments dictionary
        self.arguments = {
            'timezone': self.args.timezone,
            'strategy_function': self.args.strategy_function,
            'symbol': self.args.symbol,
            'shares_per_trade': self.args.shares_per_trade,
            'order_type': self.args.order_type,
            'alpha': self.args.alpha,
            'vol_floor': self.args.vol_floor,
            'thresholdz': self.args.thresholdz,
            'take_profit': self.args.take_profit,
            'delay': self.args.delay,
            'indicator_name': self.args.indicator_name,
            'strategy_name': self.args.strategy_name,
            'env_file': self.args.env_file,
            'interactive': self.args.interactive
        }
        
        return self.args

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
        if self.args.order_type is None:
            self.args.order_type = self.get_user_input("Order type", "market", str, ["market", "limit"])
            self.arguments['order_type'] = self.args.order_type
        
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
        
        # Indicator name
        if not self.args.indicator_name:
            self.args.indicator_name = self.get_user_input("Technical indicator name", "calc_zscore")
            self.arguments['indicator_name'] = self.args.indicator_name
        
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
        
        return self.args

    def confirm_parameters(self):
        """Show final parameters and ask for confirmation"""
        print("\n=== Final Trading Parameters ===")
        print(f"Timezone: {self.args.timezone}")
        print(f"Strategy function: {self.args.strategy_function}")
        print(f"Symbol: {self.args.symbol}")
        print(f"Shares per trade: {self.args.shares_per_trade}")
        print(f"Order type: {self.args.order_type}")
        print(f"EMA alpha: {self.args.alpha}")
        print(f"Volatility floor: {self.args.vol_floor}")
        print(f"Risk premium (Z-score threshold): {self.args.thresholdz}")
        print(f"Take profit factor: {self.args.take_profit}")
        print(f"Order delay: {self.args.delay} seconds")
        print(f"Strategy name: {self.args.strategy_name if self.args.strategy_name else 'Auto-generated'}")
        print(f"Environment file: {self.args.env_file if self.args.env_file else 'Default (.env or system)'}")
        
        while True:
            confirm = input("\nProceed with these parameters? (y/n): ").strip().lower()
            if confirm in ["y", "yes"]:
                return True
            elif confirm in ["n", "no"]:
                return False
            else:
                print("Please enter \'y\' or \'n\'")

# end GetArgs class


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    This class defines the interface that all strategy implementations must follow,
    providing a consistent way to execute and manage different trading strategies.
    """
    
    def __init__(self, **kwargs):
        """Initialize the strategy with configuration parameters."""
        self.config = kwargs
        self.state = {}
        self.reset()


    @abstractmethod
    def reset(self):
        """Reset the strategy state to initial conditions."""
        pass


    @abstractmethod
    def get_available_strategies(self):
        """
        Get list of available strategy methods for this implementation.
        
        Returns:
            list: List of strategy method names that can be called via execute()
        """
        pass


    def execute(self, strategy_name, *args, **kwargs):
        """
        Execute the specified strategy method.
        
        Args:
            strategy_name (str): Name of the strategy method
            *args: Arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method
        
        Returns:
            The result of the strategy execution
        
        Raises:
            AttributeError: If the strategy doesn't exist
            ValueError: If invalid arguments are provided
        """
        if strategy_name not in self.get_available_strategies():
            available = ', '.join(self.get_available_strategies())
            raise AttributeError(f"Strategy '{strategy_name}' not available. Available strategies: {available}")
        
        # Get the actual strategy method
        method = getattr(self, strategy_name)
        if not callable(method):
            raise AttributeError(f"'{strategy_name}' is not a callable strategy method")
        
        try:
            return method(*args, **kwargs)
        except TypeError as e:
            raise TypeError(f"Error executing strategy {strategy_name}: {e}")


    def recalc(self, strategy_name, *args, **kwargs):
        """
        Alias for execute() method for backward compatibility.
        
        Args:
            strategy_name (str): Name of the strategy method
            *args: Arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method
        
        Returns:
            The result of the strategy execution
        """
        return self.execute(strategy_name, *args, **kwargs)

# end BaseStrategy class


class StrategyFactory:
    """
    Factory class for creating trading strategy instances by name.
    
    This class provides a centralized way to create strategy instances
    using string names and configuration parameters.
    """
    
    _strategies = {}
    _default_strategy = "SingleStockStrategy"  # Default strategy class name
    
    @classmethod
    def register(cls, name, strategy_class):
        """
        Register a strategy class with a string name.
        
        Args:
            name (str): Name to register the strategy under
            strategy_class: The strategy class to register
        """
        cls._strategies[name] = strategy_class


    @classmethod
    def create(cls, strategy_class=None, **kwargs):
        """
        Create a strategy instance by name.
        
        Args:
            strategy_class (str, optional): Name of the strategy class to create. 
                                          If None, uses the default strategy class.
            **kwargs: Configuration parameters for the strategy
        
        Returns:
            BaseStrategy: Instance of the requested strategy
        
        Raises:
            ValueError: If the strategy name is not registered
            
        Examples:
            # Using default strategy class (SingleStockStrategy)
            strategy = StrategyFactory.create(strategy_function="trade_zscore", symbol="SPY")
            
            # Explicitly specifying strategy class
            strategy = StrategyFactory.create("SingleStockStrategy", strategy_function="trade_zscore", symbol="SPY")
        """
        # Use default strategy if none specified
        if strategy_class is None:
            strategy_class = cls._default_strategy
        
        if strategy_class not in cls._strategies:
            available = ', '.join(cls._strategies.keys())
            raise ValueError(f"Unknown strategy '{strategy_class}'. Available strategies: {available}")
        
        strategy_class_obj = cls._strategies[strategy_class]
        return strategy_class_obj(**kwargs)


    @classmethod
    def set_default_strategy(cls, name):
        """
        Set the default strategy class name.
        
        Args:
            name (str): Name of the registered strategy to use as default
            
        Raises:
            ValueError: If the strategy name is not registered
        """
        if name not in cls._strategies:
            available = ', '.join(cls._strategies.keys())
            raise ValueError(f"Cannot set default to unknown strategy '{name}'. Available strategies: {available}")
        cls._default_strategy = name


    @classmethod
    def get_default_strategy(cls):
        """
        Get the current default strategy class name.
        
        Returns:
            str: Name of the default strategy class
        """
        return cls._default_strategy


    @classmethod
    def get_available_strategies(cls):
        """
        Get list of available strategy names.
        
        Returns:
            list: List of registered strategy names
        """
        return list(cls._strategies.keys())

# end StrategyFactory class


class SingleStockStrategy(BaseStrategy):
    """
    Trading strategies class that manages trading state and implements strategy functions.

    Examples:
    
    # Using GetArgs arguments dictionary (recommended)
    from MachineTrader import GetArgs, SingleStockStrategy
    args_handler = GetArgs()
    args = args_handler.parse_arguments()
    strategy = SingleStockStrategy(arguments=args_handler.arguments)

    # Backward compatibility with individual arguments
    strategy = SingleStockStrategy(symbol="SPY", shares_per_trade=10, alpha=0.5)

    # Use specific .env file
    strategy = SingleStockStrategy(symbol="SPY", env_file="/path/to/.env")

    """
    
    def __init__(self, arguments=None, **kwargs):
        """
        Initialize the Strategies class with state variables.
        Creates SDK clients automatically during initialization.
        
        Args:
            arguments (dict): Dictionary containing all arguments from GetArgs class, or individual kwargs
            **kwargs: Individual keyword arguments (for backward compatibility)
            
        Arguments dictionary should contain:
            strategy_function (str): Name of the strategy function to use
            indicator_name (str): Name of the technical indicator method to use (e.g., 'calc_zscore', 'calc_ema', 'calc_zscorew')
            symbol (str): Trading symbol
            shares_per_trade (int): Number of shares per trade
            order_type (str): Order type ("market" or "limit")
            alpha (float): EMA decay parameter (0 < alpha <= 1)
            vol_floor (float): Minimum volatility value
            thresholdz (float): Risk premium parameter for Z-score threshold and limit price adjustment
            take_profit (float): Take profit level multiplier
            delay (float): Delay in seconds before order submission
            env_file (str, optional): Path to .env file for API keys (None for default .env or system vars)
            timezone (ZoneInfo): Timezone for operations
            strategy_name (str): Name of the trading strategy (auto-generated if None)
        """
        # Initialize parent class with all arguments
        super().__init__(**kwargs if arguments is None else arguments)
        
        # Handle arguments - either from dictionary or individual kwargs
        if arguments is not None:
            # Use arguments dictionary from GetArgs
            args = arguments
        else:
            # Backward compatibility: use individual kwargs with defaults
            args = {
                'strategy_function': kwargs.get('strategy_function', "trade_zscore"),
                'indicator_name': kwargs.get('indicator_name', "calc_zscore"),
                'symbol': kwargs.get('symbol'),
                'shares_per_trade': kwargs.get('shares_per_trade', 1),
                'order_type': kwargs.get('order_type') or kwargs.get('type', "market"),  # Support both old and new parameter names
                'alpha': kwargs.get('alpha', 0.3),
                'vol_floor': kwargs.get('vol_floor', 0.1),
                'thresholdz': kwargs.get('thresholdz', 2.0),
                'take_profit': kwargs.get('take_profit', 20.0),
                'delay': kwargs.get('delay', 0),
                'env_file': kwargs.get('env_file'),
                'timezone': kwargs.get('timezone', ZoneInfo("America/New_York")),
                'strategy_name': kwargs.get('strategy_name'),
            }

        # Create AlpacaSDK instance and initialize the API clients
        self.alpaca_sdk = AlpacaSDK()

        # Handle None values by providing defaults
        env_file = args.get('env_file')

        self.alpaca_sdk.create_trade_clients(env_file)

        # Handle timezone - convert string to ZoneInfo if needed
        timezone_arg = args.get('timezone')
        if isinstance(timezone_arg, str):
            self.timezone = ZoneInfo(timezone_arg)
        else:
            self.timezone = timezone_arg or ZoneInfo("America/New_York")

        # Trading parameters
        self.strategy_function = args.get('strategy_function')
        self.symbol = args.get('symbol')
        self.order_type = args.get('order_type')
        self.shares_per_trade = args.get('shares_per_trade')
        self.alpha = args.get('alpha')
        self.vol_floor = args.get('vol_floor')
        self.thresholdz = args.get('thresholdz')
        self.take_profit = args.get('take_profit')
        self.delay = args.get('delay')
        self.indicator_name = args.get('indicator_name')
        
        # Create strategy name if not provided
        strategy_name = args.get('strategy_name')
        if strategy_name is None:
            self.strategy_name = f"StratBoll_{self.symbol}_ns{self.shares_per_trade}_{self.order_type}al{self.alpha}rp{self.thresholdz}vf{self.vol_floor}tp{self.take_profit}"
        else:
            self.strategy_name = strategy_name

        # Create indicator instance based on the indicator_name
        self.indicator = create_indicator(
            self.indicator_name, 
            alpha=self.alpha, 
            vol_floor=self.vol_floor
        )
        
        # Validate that the specified indicator_name is available
        validate_indicator_name(
            self.indicator_name,
            self.strategy_function,
            self.indicator
        )

        # Create file paths immediately in constructor using AlpacaSDK
        file_names = self.alpaca_sdk.create_file_names(
            self.strategy_name, self.symbol, self.timezone
        )
        self.submits_file = file_names["submits_file"]
        self.error_file = file_names["error_file"] 
        self.state_file = file_names["state_file"]
        self.fills_file = file_names["fills_file"]
        self.canceled_file = file_names["canceled_file"]

        # State variables as requested
        self.order_response = None
        self.order_id = None
        self.position_shares = 0
        self.position_broker = None
        self.last_buy_price = None
        self.last_sell_price = None
        self.orders_list = {}  # Dictionary of pending limit order IDs: {order_id: limit_price}
        self.position_list = []  # List of stock positions with fill prices: negative for buys, positive for sells
        self.unrealized_pnl = 0.0
        self.total_realized_pnl = 0.0

    # end constructor


    def reset(self):
        """Reset the strategy state to initial conditions."""
        # Reset state variables
        self.state = {}
        self.order_response = None
        self.order_id = None
        self.position_shares = 0
        self.position_broker = None
        self.last_buy_price = None
        self.last_sell_price = None
        self.orders_list = {}
        self.position_list = []
        self.unrealized_pnl = 0.0
        self.total_realized_pnl = 0.0
        
        # Reset indicator instances if they exist
        if hasattr(self, 'indicator') and self.indicator:
            self.indicator.reset()


    def get_available_strategies(self):
        """
        Get list of available strategy methods for this implementation.
        
        Returns:
            list: List of strategy method names that can be called via execute()
        """
        return [
            'trade_zscore',
            'trade_dual_ma', 
            'trade_bollinger',
            'trade_momentum',
            'trade_mean_reversion'
        ]


    async def execute_strategy(self, bar):
        """
        Execute the strategy function specified by strategy_function with the bar data.
        This method now uses the new string-based strategy execution pattern.
        
        Args:
            bar: Bar object with price data
        """
        # Use the new execute method from BaseStrategy for string-based strategy calling
        return await self.execute(self.strategy_function, bar)

    # end execute_strategy


    def save_state(self, date_time, symbol, price, volatility, zscore, order, 
                           position_shares, total_realized_pnl, unrealized_pnl, state_file):
        """
        Save the current strategy state to a CSV file.
        
        Args:
            date_time (str): Current date and time string
            symbol (str): Trading symbol (e.g., "SPY")
            price (float): Current market price
            volatility (float): Current price volatility
            zscore (float): Current Z-score value
            order (OrderSide or None): Current trade side (BUY/SELL) or None
            position_shares (int): Number of shares currently held
            total_realized_pnl (float): Total realized profit/loss
            unrealized_pnl (float): Current unrealized profit/loss
            state_file (str): Path to the state CSV file
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        
        try:
            # Create state data dictionary
            state_data = {
                "date_time": date_time,
                "symbol": symbol,
                "price": price,
                "volatility": volatility,
                "zscore": zscore,
                "order": order,
                "position_shares": position_shares,
                "pnlReal": total_realized_pnl,
                "pnlUnreal": unrealized_pnl,
            }
            
            # Convert to DataFrame and save to CSV
            state_data = pd.DataFrame([state_data])
            state_data.to_csv(state_file, mode="a", header=not os.path.exists(state_file), index=False)
            
            print(f"💾 Strategy state saved to {state_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving strategy state: {e}")
            return False
    # end save_state


    def take_profit(self, position_shares, price_last, shares_per_trade, shares_available, 
                   last_buy_price, last_sell_price, price_adjustment):
        """
        Calculate the trade side and shares to trade for taking profit.
        
        Args:
            position_shares (int): Current position in shares
            price_last (float): Current market price
            shares_per_trade (int): Shares per trade
            shares_available (float): Available shares to trade
            last_buy_price (float): Last buy limit price
            last_sell_price (float): Last sell limit price
            price_adjustment (float): Price adjustment for limit orders
            
        Returns:
            tuple: (trade_side, limit_price, shares_to_trade, last_buy_price, last_sell_price)
        """
        
        # Initialize the trade buy/sell side variable and the limit price
        trade_side = None
        limit_price = None
        shares_to_trade = 0  # Initialize shares_to_trade to 0

        if position_shares > 0:
            # If the position is long stock - submit a sell trade order
            trade_side = OrderSide.SELL
            # The limit price is equal to the last sell price plus the price_adjustment adjustment
            if last_sell_price is None:
                limit_price = round(price_last + price_adjustment, 2)
            else:
                limit_price = round(max(price_last, last_sell_price) + price_adjustment, 2)
            last_sell_price = limit_price

        else: # position_shares < 0
            # The position is short stock - submit a buy trade order
            trade_side = OrderSide.BUY
            # The limit price is equal to the last buy price minus the price_adjustment adjustment
            if last_buy_price is None:
                limit_price = round(price_last - price_adjustment, 2)
            else:
                limit_price = round(min(price_last, last_buy_price) - price_adjustment, 2)
            last_buy_price = limit_price

        # The number of shares to trade is limited by the shares_available
        shares_to_trade = min(abs(shares_available), shares_per_trade)

        return trade_side, limit_price, shares_to_trade, last_buy_price, last_sell_price

    # end take_profit


    def calc_shares_to_trade(self, zscore, price_last, shares_per_trade, shares_available, 
                           last_buy_price, last_sell_price, thresholdz, price_adjustment):
        """
        Calculate the trade side and shares to trade based on Z-score.
        
        Args:
            zscore (float): Current Z-score
            price_last (float): Current market price
            shares_per_trade (int): Shares per trade
            shares_available (float): Available shares to trade
            last_buy_price (float): Last buy limit price
            last_sell_price (float): Last sell limit price
            thresholdz (float): Risk premium threshold
            price_adjustment (float): Price adjustment for limit orders
            
        Returns:
            tuple: (trade_side, limit_price, shares_to_trade, last_buy_price, last_sell_price)
        """
        
        # Initialize the trade buy/sell side variable and the limit price
        trade_side = None
        limit_price = None
        shares_to_trade = 0  # Initialize shares_to_trade to 0

        # If the Z-score is greater than the thresholdz, then submit a sell order
        if zscore > thresholdz:
            # Submit a sell order if the price is significantly above the EMA price
            trade_side = OrderSide.SELL
            # The limit price is equal to the last sell price plus the price_adjustment adjustment
            if last_sell_price is None:
                limit_price = round(price_last + price_adjustment, 2)
            else:
                limit_price = round(max(price_last, last_sell_price) + price_adjustment, 2)
            last_sell_price = limit_price
            if shares_available > 0:
                # The number of shares to trade is limited by the shares_available
                shares_to_trade = min(abs(shares_available), shares_per_trade)
            else:
                # The number of shares to trade is equal to the shares_per_trade
                shares_to_trade = shares_per_trade

        # If the Z-score is less than minus the thresholdz, then submit a buy order
        elif zscore < (-thresholdz):
            # Submit a buy order if the price is significantly below the EMA price
            trade_side = OrderSide.BUY
            # The limit price is equal to the last buy price minus the price_adjustment adjustment
            if last_buy_price is None:
                limit_price = round(price_last - price_adjustment, 2)
            else:
                limit_price = round(min(price_last, last_buy_price) - price_adjustment, 2)
            last_buy_price = limit_price
            if shares_available < 0:
                # The number of shares to trade is limited by the shares_available
                shares_to_trade = min(abs(shares_available), shares_per_trade)
            else:
                # The number of shares to trade is equal to the shares_per_trade
                shares_to_trade = shares_per_trade

        else:
            # If the Z-score is not significant, do not trade
            print(f"⏸️ No trade for {self.symbol} - the Z-score = {zscore:.2f} is not significant compared to the risk premium = {thresholdz}")
            shares_to_trade = 0

        return trade_side, limit_price, shares_to_trade, last_buy_price, last_sell_price
    # end calc_shares_to_trade


    async def handle_trade_update(self, event_data):
        """
        Handle trade update events from the trading stream.
        Uses instance variables for file paths (fills_file and canceled_file).
        
        Args:
            event_data: Trade update event data
        """
        
        # Get the event order ID from the event data
        order_id = str(event_data.order.id)

        ### Check if this order ID is in the pending list
        if order_id in self.orders_list.keys():

            # Unpack the event_data into a dictionary
            event_dict = event_data.model_dump()  # Convert to dictionary
            event_dict = convert_to_nytzone(event_dict)
            event_name = str(event_dict["event"]).lower()  # Get the event name
            time_stamp = event_dict["timestamp"]
            orderinfo = event_dict["order"]
            # Remove the "order" key from the event_dict
            event_dict.pop("order", None)
            symbol = orderinfo["symbol"]
            event_dict.update(orderinfo)  # This adds order fields to event_dict
            time_now = datetime.now(self.timezone).strftime("%Y-%m-%d %H:%M:%S")

            # Process the event data based on the event type
            if (event_name == "fill") or (event_name == "partial_fill"):
                order_type = orderinfo["order_type"]
                trade_side = orderinfo["side"]
                qty_filled = float(orderinfo["qty"])
                fill_price = float(orderinfo.get("filled_avg_price", 0))
                print(f"✅ Order {order_id} filled at {time_now} at price {fill_price}")
                print(f"💸 {time_stamp} Filled {order_type} {trade_side} order for {qty_filled} shares of {symbol} at {fill_price}")

                # Update position_list and calculate realized P&L after the trade is filled
                if trade_side == "buy":
                    # Check if there are existing positions and their direction
                    if (not self.position_list) or all(price < 0 for price in self.position_list):
                        # Add new buy positions as negative prices
                        for _ in range(int(qty_filled)):
                            self.position_list.append(-fill_price)
                        print(f"📈 Added {int(qty_filled)} buy positions at ${fill_price}")
                    else:
                        # Existing positions are sells (positive) - closing short position
                        realized_pnl = 0.0
                        shares_to_close = int(qty_filled)
                        for _ in range(shares_to_close):
                            if self.position_list and self.position_list[0] > 0:  # Pop sell positions (positive prices)
                                position_price = self.position_list.pop(0)
                                # Realized P&L = sell price - buy price (for closing short)
                                realized_pnl += (position_price - fill_price)
                            else:
                                # No more short positions to close, add as new long position
                                self.position_list.append(-fill_price)
                        print(f"🔄 Closed {shares_to_close} short positions. Realized P&L: ${realized_pnl:.2f}")
                        self.total_realized_pnl += realized_pnl
                        
                elif trade_side == "sell":
                    # Check if we have existing positions and their direction
                    if not (self.position_list) or all(price > 0 for price in self.position_list):
                        # No existing positions - add new sell positions as positive prices
                        for _ in range(int(qty_filled)):
                            self.position_list.append(fill_price)
                        print(f"📉 Added {int(qty_filled)} sell positions at ${fill_price}")
                    else:
                        # Existing positions are buys (negative) - closing long position
                        realized_pnl = 0.0
                        shares_to_close = int(qty_filled)
                        for _ in range(shares_to_close):
                            if self.position_list and self.position_list[0] < 0:  # Pop buy positions (negative prices)
                                position_price = self.position_list.pop(0)
                                # Realized P&L = sell price - buy price (for closing long)
                                realized_pnl += (position_price + fill_price)
                            else:
                                # No more long positions to close, add as new short position
                                self.position_list.append(fill_price)
                        print(f"🔄 Closed {shares_to_close} long positions. Realized P&L: ${realized_pnl:.2f}")
                        self.total_realized_pnl += realized_pnl

                # Print the current position list
                print(f"📋 Current position list: {self.position_list}")

                # Update the position_shares
                if not self.position_list:
                    self.position_shares = 0
                else:
                    self.position_shares = -math.copysign(1, self.position_list[0]) * len(self.position_list)
                print(f"💼 Position after the fill: {self.position_shares} shares of {symbol}")
                self.position_broker = event_dict.get("position_qty", 0)
                print(f"🏦 Position from broker after the fill: {self.position_broker} shares of {symbol}")

                # Remove the filled order ID from the orders list
                removed_price = self.orders_list.pop(order_id)
                print(f"🗑️ Removed order ID {order_id} with limit price {removed_price} from pending list. Remaining orders: {len(self.orders_list)}")
                print(f"📊 Updated stock positions: {len(self.position_list)} total positions, current list: {self.position_list}")

                # Save fill data to CSV
                event_frame = pd.DataFrame([event_dict])
                event_frame.to_csv(self.fills_file, mode="a", header=not os.path.exists(self.fills_file), index=False)
                print(f"💾 Fill appended to {self.fills_file}")

            elif (event_name == "canceled") or (event_name == "expired") or (event_name == "rejected"):
                print(f"❌ Order {order_id} canceled or expired at {time_now}")
                # Remove the canceled order ID from orders list
                removed_price = self.orders_list.pop(order_id)
                print(f"🗑️ Removed canceled order ID {order_id} with limit price {removed_price} from orders list. Remaining orders: {len(self.orders_list)}")
                # Append to CSV
                event_frame = pd.DataFrame([event_dict])
                event_frame.to_csv(self.canceled_file, mode="a", header=not os.path.exists(self.canceled_file), index=False)
                print(f"💾 Canceled order appended to {self.canceled_file}")

            elif event_name == "replaced":
                print(f"🔄 Replace event: {event_dict}")
            else:
                print(f"❓ Unknown event: {event_name}")

            print(f"✅ Finished processing the {event_name} update for order {order_id} at {time_now}\n")

    # end handle_trade_update


    async def trade_zscore(self, bar):
        """
        Main trading function that processes bar data and executes trades using Z-score strategy.
        Uses instance variables for all parameters, making it suitable for string-based execution.
        
        Args:
            bar: Bar object with price data
        """
        ### Extract prices from the bar
        ### Get the latest price and volume from the price bar
        price_last = bar.close
        volume_last = bar.volume
        time_stamp = bar.timestamp.astimezone(self.timezone)
        date_time = time_stamp.strftime("%Y-%m-%d %H:%M:%S")

        ### Print strategy information
        print(f"🎯 Strategy: {self.strategy_name}")
        print(f"⚙️ Parameters: symbol={self.symbol}, shares={self.shares_per_trade}, type={self.order_type}, alpha={self.alpha}, vol_floor={self.vol_floor}, thresholdz={self.thresholdz}, take_profit={self.take_profit}, delay={self.delay}")

        ### Calculate the Z-score, EMA price, and price volatility using the indicator
        indicator_result = self.indicator.calculate(self.indicator_name, price_last, volume_last)

        # Handle different indicator return formats
        if isinstance(indicator_result, tuple) and len(indicator_result) >= 3:
            zscore, ema_price, price_vol = indicator_result[:3]
        elif isinstance(indicator_result, tuple) and len(indicator_result) == 2:
            # For methods that return (zscore, ema_price)
            zscore, ema_price = indicator_result
            price_vol = self.vol_floor
        else:
            # Single value return (e.g., from calc_ema)
            zscore = 0.0
            ema_price = float(indicator_result) if indicator_result is not None else price_last
            price_vol = self.vol_floor

        ### Calculate the unrealized P&L and update the stock positions
        trading_helper = Trading()
        trading_helper.position_list = self.position_list  # Set the position list
        trading_helper.last_price = price_last  # Set the current price
        self.position_shares, self.unrealized_pnl = trading_helper.calc_unrealized_pnl()

        # Calculate the number of buy and sell limit orders
        num_buy_orders = sum(1 for price in self.orders_list.values() if price < 0)
        num_sell_orders = sum(1 for price in self.orders_list.values() if price > 0)
        
        # Calculate price adjustment for limit orders using instance variables
        price_adjustment = self.thresholdz * price_vol
        
        # Calculate the take profit level
        take_profit_level = self.take_profit * price_vol

        print(f"📊 Time: {date_time}, Symbol: {bar.symbol}, Z-score: {zscore:.2f}, Price: {price_last}, EMA: {ema_price:.2f}, Vol: {price_vol:.4f}")
        print(f"💼 Position: {self.position_shares} shares, Pending orders: {len(self.orders_list)} (Buy: {num_buy_orders}, Sell: {num_sell_orders}), Unrealized P&L: ${self.unrealized_pnl:.2f}, Take Profit Level: ${take_profit_level:.2f}, Realized P&L: ${self.total_realized_pnl:.2f}")
        print(f"📋 Current position list: {self.position_list}")
        print(f"🔄 Current pending order IDs: {list(self.orders_list.keys())}")

        ### Get the current position from the broker and calculate the shares_available
        self.position_broker = self.alpaca_sdk.get_position(self.symbol)
        if self.position_broker is None:
            shares_available = self.shares_per_trade
        else:
            shares_available = float(self.position_broker.qty_available)
            self.position_broker = float(self.position_broker.qty)

        ### Cancel orders if limit prices are too far apart
        if (self.last_buy_price is not None) and (self.last_sell_price is not None):
            if (self.last_sell_price - self.last_buy_price) > (10 * price_adjustment):
                print(f"\n❌ The limit prices are too far apart for {self.symbol} - Canceling all open limit orders")
                remaining_order_ids = self.alpaca_sdk.cancel_orders(self.symbol, list(self.orders_list.keys()))
                self.orders_list = {order_id: self.orders_list[order_id] for order_id in remaining_order_ids if order_id in self.orders_list}
                self.last_sell_price = None
                self.last_buy_price = None

        ### Apply the trading rules

        # Calculate the trade side (buy/sell) and the amount of shares to trade
        trade_side = None

        if (shares_available != 0):
            # Apply the take-profit rule
            if (self.unrealized_pnl > take_profit_level):
                print(f"\n💰 Take profit triggered for {self.symbol}: Selling the position\n")
                print(f"💵 Unrealized PnL = {self.unrealized_pnl:.2f} and Take profit level = {take_profit_level:.2f}\n")
                trade_side, limit_price, shares_to_trade, self.last_buy_price, self.last_sell_price = self.take_profit(
                    self.position_shares, price_last, self.shares_per_trade, shares_available, 
                    self.last_buy_price, self.last_sell_price, price_adjustment)

            # Apply the contrarian rule based on the Z-score
            elif (abs(zscore) > abs(self.thresholdz)):
                print(f"\n🎯 Take profit not triggered for {self.symbol} - Applying contrarian rule\n")
                trade_side, limit_price, shares_to_trade, self.last_buy_price, self.last_sell_price = self.calc_shares_to_trade(
                    zscore, price_last, self.shares_per_trade, shares_available, 
                    self.last_buy_price, self.last_sell_price, self.thresholdz, price_adjustment)

            else:
                print(f"\n⏸️ No trade conditions met for {self.symbol}")
        else:
            print(f"\n⚠️ No shares available for {self.symbol}")

        ### Submit the trade order if the trade side is not None
        if trade_side is not None:
            print(f"📈 Z-score: {zscore:.2f}, Side: {trade_side}, Limit price: {limit_price}, Shares to trade: {shares_to_trade}")
            
            # Apply delay before order submission if specified
            if self.delay > 0:
                print(f"⏱️ Waiting {self.delay} seconds before submitting order...")
                time.sleep(self.delay)
            
            self.order_response = self.alpaca_sdk.submit_order(self.symbol, shares_to_trade, 
                                             trade_side, self.order_type, limit_price, self.submits_file, self.error_file)

            # If the order submission failed, retry
            if self.order_response is None:
                print(f"❌ Trade order submission failed for {self.symbol}")
                print(f"🧹 Canceling all the open orders for {self.symbol}")
                self.alpaca_sdk.cancel_orders(self.symbol)
                self.last_sell_price = None
                self.last_buy_price = None
                print(f"🔄 Submitting the trade order again for {self.symbol}")
                self.order_response = self.alpaca_sdk.submit_order(self.symbol, shares_to_trade, 
                                                 trade_side, self.order_type, limit_price, self.submits_file, self.error_file)

            # Add the order ID to the pending orders dictionary
            if self.order_response is not None:
                self.order_id = str(self.order_response.id)
                signed_limit_price = limit_price if trade_side == OrderSide.SELL else -limit_price
                self.orders_list[self.order_id] = signed_limit_price
                print(f"✅ Added order ID {self.order_id} with limit price {signed_limit_price} to pending list. Total pending orders: {len(self.orders_list)}")
            else:
                print("❌ Failed to submit order after retry\n")
        else:
            trade_side = None

        ### Save the strategy state to the CSV file
        self.save_state(
            date_time=date_time,
            symbol=bar.symbol,
            price=bar.close,
            volatility=price_vol,
            zscore=zscore,
            order=trade_side,
            position_shares=self.position_shares,
            total_realized_pnl=self.total_realized_pnl,
            unrealized_pnl=self.unrealized_pnl,
            state_file=self.state_file
        )
        print("✨ Done\n")

    # end trade_zscore


    async def trade_dual_ma(self, bar):
        """
        Dual moving average strategy placeholder.
        Currently uses a single indicator until the strategy is fully implemented.
        
        Args:
            bar: Bar object with price data
        """
        # Create file paths
        file_names = self.alpaca_sdk.create_file_names(self.strategy_name, self.symbol, self.timezone)
        submits_file, error_file, state_file = file_names["submits_file"], file_names["error_file"], file_names["state_file"]
        
        print(f"🚧 trade_dual_ma strategy not yet implemented")
        # TODO: When implemented, this will need fast and slow moving averages
        # TODO: Fast MA crossing above slow MA = buy signal
        # TODO: Fast MA crossing below slow MA = sell signal
        
    # end trade_dual_ma


    async def trade_bollinger(self, bar):
        """
        Placeholder for future implementation of Bollinger bands strategy.
        
        Args:
            bar: Bar object with price data
        """
        # Create file paths
        file_names = self.alpaca_sdk.create_file_names(self.strategy_name, self.symbol, self.timezone)
        submits_file, error_file, state_file = file_names["submits_file"], file_names["error_file"], file_names["state_file"]
        
        print(f"🚧 trade_bollinger strategy not yet implemented")
        # TODO: Implement Bollinger bands strategy
        # Buy when price touches lower band, sell when price touches upper band
        
    # end trade_bollinger


    async def trade_momentum(self, bar):
        """
        Placeholder for future implementation of momentum strategy.
        
        Args:
            bar: Bar object with price data
        """
        # Create file paths
        file_names = self.alpaca_sdk.create_file_names(self.strategy_name, self.symbol, self.timezone)
        submits_file, error_file, state_file = file_names["submits_file"], file_names["error_file"], file_names["state_file"]
        
        print(f"🚧 trade_momentum strategy not yet implemented")
        # TODO: Implement momentum strategy
        # Follow the trend direction when momentum is strong
        
    # end trade_momentum


    async def trade_mean_reversion(self, bar):
        """
        Placeholder for future implementation of mean reversion strategy.
        
        Args:
            bar: Bar object with price data
        """
        # Create file paths
        file_names = self.alpaca_sdk.create_file_names(self.strategy_name, self.symbol, self.timezone)
        submits_file, error_file, state_file = file_names["submits_file"], file_names["error_file"], file_names["state_file"]
        
        print(f"🚧 trade_mean_reversion strategy not yet implemented")
        # TODO: Implement mean reversion strategy
        # Trade against extreme price movements expecting reversion to mean
        
    # end trade_mean_reversion


# Register SingleStockStrategy with the StrategyFactory
StrategyFactory.register("SingleStockStrategy", SingleStockStrategy)


