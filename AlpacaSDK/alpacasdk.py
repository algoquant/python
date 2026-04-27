"""
Package AlpacaSDK containing the class AlpacAPI for Alpaca API interactions, and the class Trading for submitting trades, position tracking, and trade event handling.

"""

import os
import logging
import math
import pandas as pd
import time
import asyncio
import random
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from typing import Optional, Callable, Any

from alpaca.trading.client import TradingClient
from alpaca.trading.stream import TradingStream
from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest, MarketOrderRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.data import StockHistoricalDataClient


class Trading:
    """
    Trading class for submitting trades, position tracking, and trade event handling.
    
    This class encapsulates position tracking variables and trading-related 
    functionality that doesn't require direct API access.
    """

    def __init__(self, symbol=None):
        """
        Initialize the Trading class with position tracking variables.
        
        Args:
            symbol (str, optional): Trading symbol (e.g., "AAPL", "SPY")
        
        Instance Variables:
            Trading Symbol:
                symbol: Trading symbol (e.g., "AAPL", "SPY")
            Position Tracking:
                position_list: List of fill prices (negative for buys, positive for sells)
                position_shares: Current share count (positive long, negative short)
                position_broker: Broker-reported position count
                broker_qty: Broker position quantity as float
                shares_available: Available shares to trade (calculated from broker position)
                orders_list: Dictionary of pending order IDs and their limit prices
                total_realized_pnl: Cumulative realized profit and loss from all trades
                num_shares: Number of shares in position list
                unrealized_pnl: Current unrealized profit and loss
                last_buy_price: Last buy limit price
                last_sell_price: Last sell limit price
                num_buy_orders: Number of buy orders currently pending
                num_sell_orders: Number of sell orders currently pending
                total_orders: Total number of orders currently pending
            Price Tracking:
                last_price: Last price update (float)
                last_bar: Last bar/candle data (dict or Bar object)
            File Tracking:
                fills_file: Path to fills CSV file
                canceled_file: Path to canceled orders CSV file
                submits_file: Path to submitted orders CSV file
                state_file: Path to state CSV file
                error_file: Path to error CSV file
        """
        # Initialize trading symbol
        self.symbol = symbol  # Trading symbol (e.g., "AAPL", "SPY")
        
        # Initialize position tracking variables
        # The position_list is a list of prices paid or received for each stock position.
        # Negative prices indicate long positions, and positive prices indicate short positions.
        # Because when we buy a stock we pay for it, which is a negative cash flow, and when we sell it, we receive the market price, which is a positive cash flow.
        self.position_list = []  # List of stock positions with fill prices: negative for buys, positive for sells
        self.position_shares = 0  # The number of shares currently owned (positive for long positions, negative for short positions)
        self.position_broker = None  # The number of shares owned according to the broker
        self.broker_qty = None  # Broker position quantity as float
        self.shares_available = 0  # Available shares to trade (calculated from broker position)
        self.orders_list = {}  # Dictionary of pending limit order IDs: {order_id: limit_price}
        self.total_realized_pnl = 0.0  # Cumulative realized profit and loss from all trades
        self.num_shares = 0  # Number of shares in position list
        self.unrealized_pnl = 0.0  # Current unrealized profit and loss
        self.last_buy_price = None  # Last buy limit price
        self.last_sell_price = None  # Last sell limit price
        self.num_buy_orders = 0  # Number of buy orders currently pending
        self.num_sell_orders = 0  # Number of sell orders currently pending
        self.total_orders = 0  # Total number of orders currently pending
        
        # Initialize price tracking variables
        self.last_price = None  # Last price update (float)
        self.last_bar = None  # Last bar/candle data (dict or Bar object)
        
        # Initialize file tracking variables
        self.fills_file = None
        self.canceled_file = None
        self.submits_file = None
        self.state_file = None
        self.error_file = None

    # end constructor


    def create_file_names(self, strategy_name, timezone=None, dir_name=None, env_file=None, dir_env_var="DATA_DIR_NAME"):
        """
        Create standardized file names for strategy logging files.
        
        This method creates file paths and automatically sets them as instance variables:
        - self.state_file
        - self.submits_file  
        - self.fills_file
        - self.canceled_file
        - self.error_file
        
        Args:
            strategy_name (str): Name of the trading strategy 
            timezone (ZoneInfo, optional): Timezone for date formatting (default: America/New_York)
            dir_name (str, optional): Directory path for output files. If None, will check environment or use default.
            env_file (str, optional): Path to .env file to load. If None, uses default .env or system vars.
            dir_env_var (str): Name of environment variable for directory path (default: "DATA_DIR_NAME")
            
        Returns:
            dict: Dictionary containing all file paths (also available as instance variables)
            
        Examples:
            # Basic usage - files automatically set as instance variables
            trading.create_file_names("MyStrategy")
            # Now you can use: trading.submits_file, trading.fills_file, etc.
            
            # Use specific directory
            trading.create_file_names("MyStrategy", dir_name="/path/to/logs/")
            
            # Use specific .env file
            trading.create_file_names("MyStrategy", env_file="/path/to/.env")
            
            # Use custom environment variable name
            trading.create_file_names("MyStrategy", dir_env_var="LOG_DIR")
        """
        
        # Set default timezone if not provided
        if timezone is None:
            timezone = ZoneInfo("America/New_York")

        # Load the API keys from .env file if provided
        if env_file is not None:
            load_dotenv(env_file)
            print(f"📄 Loading environment variables from: {env_file}")
        else:
            # Load from default .env file in current directory
            load_dotenv()
            print("📄 Loading environment variables from default .env file or system environment")

        # Use provided dir_name or get from environment variable or default
        if dir_name is None:
            dir_name = os.getenv(dir_env_var) or "./"
            if dir_name != "./":
                print(f"📁 Using directory from {dir_env_var}: {dir_name}")
            else:
                print("📁 Using default directory: ./")
        else:
            print(f"📁 Using specified directory: {dir_name}")
        
        # Ensure directory path ends with separator
        if not dir_name.endswith(("/", "\\")):
            dir_name += "/"
        
        # Get the current time in the specified timezone
        time_now = datetime.now(timezone)
        # Format date as YYYYMMDD
        date_short = time_now.strftime("%Y%m%d")
        
        # Create standardized file names
        file_names = {
            "state_file": f"{dir_name}state_{strategy_name}_{self.symbol}_{date_short}.csv",
            "submits_file": f"{dir_name}submits_{strategy_name}_{self.symbol}_{date_short}.csv",
            "fills_file": f"{dir_name}fills_{strategy_name}_{self.symbol}_{date_short}.csv",
            "canceled_file": f"{dir_name}canceled_{strategy_name}_{self.symbol}_{date_short}.csv",
            "error_file": f"{dir_name}error_{strategy_name}_{self.symbol}_{date_short}.csv"
        }
        
        # Set file paths as instance variables
        self.state_file = file_names["state_file"]
        self.submits_file = file_names["submits_file"]
        self.fills_file = file_names["fills_file"]
        self.canceled_file = file_names["canceled_file"]
        self.error_file = file_names["error_file"]
        
        print(f"✅ Strategy files created successfully in directory: {dir_name}")
        print(f"📋 Files: {len(file_names)} files for strategy '{strategy_name}' on {date_short}")
        print(f"📁 Files set as instance variables: state_file, submits_file, fills_file, canceled_file, error_file")
        
        return file_names

    # end create_file_names


    def update_prices(self, *args, **kwargs):
        """
        Update the last price and/or bar information for the Trading instance.
        
        This method accepts flexible arguments to handle different price data formats:
        - Single price value (float/int)
        - Bar/candle data (dict or Bar object)
        - Named parameters via kwargs
        
        Args:
            *args: Variable arguments that can include:
                - price (float/int): A single price value
                - bar (dict/object): Bar/candle data with OHLCV information
            **kwargs: Keyword arguments that can include:
                - price (float/int): A single price value
                - bar (dict/object): Bar/candle data
                - close (float/int): Close price (will update last_price)
                - high, low, open (float/int): OHLC price components
                - volume (int): Volume information
                - timestamp (datetime): Timestamp for the price data
                
        Raises:
            TypeError: If bar data is provided but is invalid
            
        Examples:
            # Update with a single price
            trading.update_prices(150.50)
            trading.update_prices(price=150.50)
            
            # Update with bar data
            bar_data = {'close': 150.50, 'high': 151.00, 'low': 149.50, 'open': 150.00}
            trading.update_prices(bar_data)
            trading.update_prices(bar=bar_data)
            
            # Update with kwargs
            trading.update_prices(close=150.50, high=151.00, volume=1000)
        """
        price = None
        bar = None
        
        # Process positional arguments
        for arg in args:
            if isinstance(arg, (int, float)):
                price = float(arg)
            elif isinstance(arg, (dict, object)):
                # Validate if it's a proper bar before using
                if self.is_bar(arg):
                    bar = arg
                else:
                    raise TypeError(f"Invalid bar data provided: {type(arg)}")
        
        # Process keyword arguments  
        if 'price' in kwargs:
            price = float(kwargs['price'])
        
        if 'bar' in kwargs:
            if self.is_bar(kwargs['bar']):
                bar = kwargs['bar']
            else:
                raise TypeError(f"Invalid bar data provided in kwargs: {type(kwargs['bar'])}")
        
        # Handle direct price components in kwargs
        if 'close' in kwargs:
            price = float(kwargs['close'])
        
        # If we have a complete bar object, build it from kwargs
        if any(key in kwargs for key in ['high', 'low', 'open', 'volume', 'timestamp']):
            bar_dict = {}
            if price is not None:  # Use close from above
                bar_dict['close'] = price
            for key in ['high', 'low', 'open', 'volume', 'timestamp']:
                if key in kwargs:
                    bar_dict[key] = kwargs[key]
            # Only set as bar if we have sufficient data
            if len(bar_dict) >= 2:  # At least 2 components for a meaningful bar
                bar = bar_dict
        
        # Update instance variables
        if price is not None:
            self.last_price = price
            
        if bar is not None:
            self.last_bar = bar
            # Also extract close price if available
            if hasattr(bar, 'close'):
                self.last_price = float(bar.close)
            elif isinstance(bar, dict) and 'close' in bar:
                self.last_price = float(bar['close'])

    # end update_prices


    def is_bar(self, obj):
        """
        Enhanced validation function to check if an object is a valid Alpaca bar.
        
        This function validates bar objects more efficiently by checking required fields
        and using optimized validation logic.
        
        Args:
            obj: The object to validate as a bar
            
        Returns:
            bool: True if the object is a valid bar, False otherwise
            
        Examples:
            # Valid bar dictionary
            bar_dict = {'open': 100.0, 'high': 101.0, 'low': 99.0, 'close': 100.5, 'volume': 1000}
            assert trading.is_bar(bar_dict) == True
            
            # Valid bar object with attributes
            class BarObj:
                def __init__(self):
                    self.open = 100.0
                    self.high = 101.0
                    self.low = 99.0
                    self.close = 100.5
                    self.volume = 1000
            
            bar_obj = BarObj()
            assert trading.is_bar(bar_obj) == True
            
            # Invalid objects
            assert trading.is_bar("not a bar") == False
            assert trading.is_bar({'only': 'close'}) == False
        """
        if obj is None:
            return False
            
        # Define required fields for a valid bar
        required_fields = ['open', 'high', 'low', 'close', 'volume']
        
        try:
            # Check if object is a dictionary
            if isinstance(obj, dict):
                # Optimized: Check if all required fields exist in one operation
                missing_fields = [field for field in required_fields if field not in obj]
                if missing_fields:
                    return False
                    
                # Validate that all required fields have numeric values
                for field in required_fields:
                    if not isinstance(obj[field], (int, float)) or not math.isfinite(obj[field]):
                        return False
                        
                return True
                
            # Check if object has attributes (like Alpaca Bar objects)
            else:
                # Optimized: Check if all required attributes exist
                missing_attrs = [field for field in required_fields if not hasattr(obj, field)]
                if missing_attrs:
                    return False
                    
                # Validate that all required attributes have numeric values  
                for field in required_fields:
                    value = getattr(obj, field)
                    if not isinstance(value, (int, float)) or not math.isfinite(value):
                        return False
                        
                return True
                
        except (AttributeError, TypeError, KeyError):
            return False

    # end is_bar


    def calc_realized_pnl(self, trade_side, qty_filled, fill_price, order_id=None):
        """
        Calculate realized P&L using FIFO (First In, First Out) method.
        
        This method processes a trade and calculates the realized profit/loss by matching
        with existing positions using FIFO methodology. It updates the position list
        and tracks cumulative realized P&L.
        
        Args:
            trade_side (str): The side of the trade - "buy" or "sell"
            qty_filled (int): The quantity filled in the trade
            fill_price (float): The price at which the trade was filled
            order_id (str, optional): The order ID for tracking purposes
            
        Returns:
            float: The realized P&L for this trade (positive for profit, negative for loss)
            
        Side Effects:
            - Updates self.position_list with new position entries or modifications
            - Updates self.total_realized_pnl with cumulative realized P&L
            - Updates self.position_shares with net position quantity
            
        Examples:
            # First buy trade - no realized P&L
            pnl = trading.calc_realized_pnl("buy", 100, 50.0, "order_1")
            # pnl = 0.0, position_list = [{"side": "buy", "qty": 100, "price": 50.0, "order_id": "order_1"}]
            
            # Partial sell - realizes P&L on 50 shares
            pnl = trading.calc_realized_pnl("sell", 50, 55.0, "order_2") 
            # pnl = 250.0 (50 shares * $5 profit), position_list = [{"side": "buy", "qty": 50, "price": 50.0, "order_id": "order_1"}]
            
            # Complete sell - realizes P&L on remaining 50 shares
            pnl = trading.calc_realized_pnl("sell", 50, 52.0, "order_3")
            # pnl = 100.0 (50 shares * $2 profit), position_list = []
        """
        realized_pnl = 0.0
        remaining_qty = qty_filled
        
        if trade_side.lower() == "buy":
            # For buy trades, add to position list (no realized P&L)
            self.position_list.append({
                "side": "buy",
                "qty": qty_filled,
                "price": fill_price,
                "order_id": order_id
            })
            self.position_shares += qty_filled
            
        elif trade_side.lower() == "sell":
            # For sell trades, calculate realized P&L using FIFO
            positions_to_remove = []
            
            for i, position in enumerate(self.position_list):
                if remaining_qty <= 0:
                    break
                    
                if position["side"] == "buy":
                    if position["qty"] <= remaining_qty:
                        # Complete position closure
                        pnl_for_position = position["qty"] * (fill_price - position["price"])
                        realized_pnl += pnl_for_position
                        remaining_qty -= position["qty"]
                        positions_to_remove.append(i)
                        self.position_shares -= position["qty"]
                    else:
                        # Partial position closure
                        pnl_for_position = remaining_qty * (fill_price - position["price"])
                        realized_pnl += pnl_for_position
                        position["qty"] -= remaining_qty
                        self.position_shares -= remaining_qty
                        remaining_qty = 0
            
            # Remove completed positions (in reverse order to maintain indices)
            for i in reversed(positions_to_remove):
                del self.position_list[i]
            
            # If there's still remaining quantity after closing all long positions,
            # it creates a short position
            if remaining_qty > 0:
                self.position_list.append({
                    "side": "sell",
                    "qty": remaining_qty,
                    "price": fill_price,
                    "order_id": order_id
                })
                self.position_shares -= remaining_qty
        
        # Update total realized P&L
        self.total_realized_pnl += realized_pnl
        
        return realized_pnl

    # end calc_realized_pnl


    def calc_unrealized_pnl(self):
        """
        Calculate the unrealized P&L and update the stock positions.
        
        The position_list is a list of prices paid or received for each stock position.
        Negative prices indicate long positions, and positive prices indicate short positions.
        Because when we buy a stock we pay for it, which is a negative cash flow, and when we sell it, 
        we receive the market price, which is a positive cash flow.
        
        This method updates the instance variables:
        - self.num_shares: Number of shares in position list
        - self.position_shares: Net position (positive for long, negative for short)
        - self.unrealized_pnl: Current unrealized profit/loss
        
        Uses self.last_price as the current market price for calculations.
        
        Returns:
            tuple: (position_shares, unrealized_pnl)
        """
        if not self.position_list:
            self.num_shares = 0
            self.position_shares = 0
            self.unrealized_pnl = 0.0
        else:
            # Calculate the number of shares owned
            self.num_shares = len(self.position_list)
            # Calculate the amount of shares owned (positive for long positions, negative for short positions)
            self.position_shares = -math.copysign(1, self.position_list[0]) * self.num_shares
            cost_basis = sum(self.position_list)  # Calculate the total cost basis
            # Calculate the unrealized P&L using self.last_price
            self.unrealized_pnl = (cost_basis + self.position_shares * self.last_price)

        return self.position_shares, self.unrealized_pnl

    # end calc_unrealized_pnl


    def get_state(self, alpaca_api=None, shares_per_trade=1):
        """
        Get the current trading state including broker position and available shares.
        
        This function:
        1. Gets the current position from the broker
        2. Calculates available shares to trade
        3. Updates position_broker and shares_available instance variables
        4. Counts the number of buy and sell limit orders
        5. Updates last_buy_price and last_sell_price based on current orders
        6. Returns comprehensive state information
        
        Args:
            alpaca_api (AlpacAPI, optional): AlpacAPI instance for getting position data
            shares_per_trade (int): Default shares per trade if no position exists (default: 1)
            
        Returns:
            dict: Dictionary with current state information
                {
                    'position_broker': float or None,  # Broker position quantity
                    'shares_available': float,  # Available shares to trade
                    'position_shares': int,  # Internal position count
                    'position_list': list,  # List of position prices
                    'orders_list': dict,  # Pending orders
                    'num_buy_orders': int,  # Number of buy orders
                    'num_sell_orders': int,  # Number of sell orders
                    'total_orders': int,  # Total number of orders
                    'total_realized_pnl': float,  # Total realized P&L
                    'unrealized_pnl': float,  # Current unrealized P&L
                    'last_buy_price': float or None,  # Last buy price
                    'last_sell_price': float or None,  # Last sell price
                    'num_shares': int,  # Number of shares in position list
                    'error': str or None  # Error message if any
                }
        """
        error_msg = None

        try:
            # Get the current position from the broker and calculate the shares_available
            if alpaca_api is not None:
                self.position_broker = alpaca_api.get_position(self.symbol)
                if self.position_broker is None:
                    self.shares_available = shares_per_trade
                    self.position_broker = None
                    print(f"📊 No broker position found for {self.symbol}, using default shares_per_trade: {shares_per_trade}")
                else:
                    self.shares_available = float(self.position_broker.qty_available)
                    self.broker_qty = float(self.position_broker.qty)
                    print(f"🏦 Broker position for {self.symbol}: {self.broker_qty} shares, Available: {self.shares_available}")
                    self.position_broker = self.broker_qty
            else:
                # No API instance provided, use default values
                self.shares_available = shares_per_trade
                self.position_broker = None
                error_msg = "No AlpacAPI instance provided, using default values"
                print(f"⚠️ {error_msg}")
                
        except Exception as e:
            error_msg = f"Error getting broker position: {e}"
            print(f"❌ {error_msg}")
            # Set default values on error
            self.shares_available = shares_per_trade
            self.position_broker = None

        # Calculate the number of buy and sell limit orders (from get_limit_orders logic)
        self.num_buy_orders = sum(1 for price in self.orders_list.values() if price < 0)
        self.num_sell_orders = sum(1 for price in self.orders_list.values() if price > 0)
        self.total_orders = len(self.orders_list)

"""
        # Update last_buy_price and last_sell_price from current orders
        buy_prices = [abs(price) for price in self.orders_list.values() if price < 0]
        sell_prices = [price for price in self.orders_list.values() if price > 0]
        
        if buy_prices:
            self.last_buy_price = min(buy_prices)  # Lowest buy price (most aggressive)
        
        if sell_prices:
            self.last_sell_price = max(sell_prices)  # Highest sell price (most aggressive)
"""

        # Create comprehensive state dictionary
        state = {
            'position_broker': self.position_broker,
            'shares_available': self.shares_available,
            'position_shares': self.position_shares,
            'position_list': self.position_list.copy(),  # Return a copy to prevent external modification
            'orders_list': self.orders_list.copy(),  # Return a copy to prevent external modification
            'num_buy_orders': self.num_buy_orders,
            'num_sell_orders': self.num_sell_orders,
            'total_orders': self.total_orders,
            'total_realized_pnl': self.total_realized_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'last_buy_price': self.last_buy_price,
            'last_sell_price': self.last_sell_price,
            'num_shares': self.num_shares,
            'error': error_msg
        }
        
        # Log current state (enhanced with order status from get_limit_orders)
        print(f"� Order status for {self.symbol}: Buy={self.num_buy_orders}, Sell={self.num_sell_orders}, Total={self.total_orders}")
        if self.last_buy_price:
            print(f"💰 Last buy price: ${self.last_buy_price:.2f}")
        if self.last_sell_price:
            print(f"💰 Last sell price: ${self.last_sell_price:.2f}")
        
        print(f"�📈 Trading State for {self.symbol}:")
        print(f"   🏦 Broker Position: {self.position_broker}")
        print(f"   💼 Available Shares: {self.shares_available}")
        print(f"   📊 Internal Position: {self.position_shares} shares")
        print(f"   📋 Position List: {len(self.position_list)} entries")
        print(f"   📝 Pending Orders: {self.total_orders} (Buy: {self.num_buy_orders}, Sell: {self.num_sell_orders})")
        print(f"   💰 Realized P&L: ${self.total_realized_pnl:.2f}")
        print(f"   💵 Unrealized P&L: ${self.unrealized_pnl:.2f}")
        if self.last_buy_price:
            print(f"   🔵 Last Buy Price: ${self.last_buy_price:.2f}")
        if self.last_sell_price:
            print(f"   🔴 Last Sell Price: ${self.last_sell_price:.2f}")
        
        return state

    # end get_state


    def save_state(self, **kwargs):
        """
        Save the strategy state to the CSV file, using current price and trading data.
        
        This function:
        1. Uses update_prices() to extract price information from various sources
        2. Calculates current unrealized P&L using calc_unrealized_pnl()
        3. Saves comprehensive strategy state to CSV file
        4. Returns success status
        
        Args:
            **kwargs: Flexible arguments for price data that can include:
                - price (float/int): A single price value
                - bar (dict/object): Bar/candle data with OHLCV information
                - volatility (float): Current price volatility (optional)
                - zscore (float): Current Z-score value (optional)
                - order (str): Current trade side ("BUY"/"SELL") or None (optional)
                - close, high, low, open (float/int): OHLC price components
                - volume (int): Volume information
                - timestamp (datetime): Timestamp for the price data
                
        Returns:
            bool: True if save was successful, False otherwise
            
        Examples:
            # Save state with current price
            trading.save_state(price=150.50)
            
            # Save state with bar data
            bar_data = {'close': 150.50, 'high': 151.00, 'low': 149.50, 'open': 150.00}
            trading.save_state(bar=bar_data, volatility=0.02, zscore=1.5)
            
            # Save state with additional trading information
            trading.save_state(close=150.50, volume=1000, order="BUY", zscore=-2.1)
        """
        
        try:
            # Update prices using the flexible update_prices method
            self.update_prices(**kwargs)
            
            # Get current timestamp
            timezone = ZoneInfo("America/New_York")
            time_now = datetime.now(timezone)
            date_time = time_now.strftime("%Y-%m-%d %H:%M:%S")
            
            # Calculate unrealized P&L using current price
            if self.last_price is not None:
                self.calc_unrealized_pnl()
            
            # Extract additional strategy parameters from kwargs
            volatility = kwargs.get('volatility', 0.0)
            zscore = kwargs.get('zscore', 0.0)
            order = kwargs.get('order', None)
            
            # Create state data dictionary
            state_data = {
                "date_time": date_time,
                "symbol": self.symbol,
                "price": self.last_price,
                "volatility": volatility,
                "zscore": zscore,
                "order": order,
                "position_shares": self.position_shares,
                "position_broker": self.position_broker,
                "broker_qty": self.broker_qty,
                "shares_available": self.shares_available,
                "num_buy_orders": self.num_buy_orders,
                "num_sell_orders": self.num_sell_orders,
                "total_orders": self.total_orders,
                "pnlReal": self.total_realized_pnl,
                "pnlUnreal": self.unrealized_pnl,
                "last_buy_price": self.last_buy_price,
                "last_sell_price": self.last_sell_price,
                "num_shares": self.num_shares
            }
            
            # Convert to DataFrame and save to CSV
            if self.state_file is not None:
                state_frame = pd.DataFrame([state_data])
                state_frame.to_csv(self.state_file, mode="a", header=not os.path.exists(self.state_file), index=False)
                print(f"💾 Strategy state saved to {self.state_file}")
            else:
                print("⚠️ No state file specified - use create_file_names() first")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving strategy state: {e}")
            return False

    # end save_state


    async def handle_trade_event(self, event_data):
        """
        Handle trade update events for tracked orders.
        
        Args:
            event_data: The trade update event data
            
        Note:
            Uses self.orders_list to filter events for tracked orders.
            Uses self.fills_file and self.canceled_file for CSV logging.
            Stream lifecycle is managed externally by calling code.
            Multiple orders can be tracked simultaneously without stream interference.
        """
        # Get the order ID from the event
        order_id = str(event_data.order.id)
        
        # Get event type to determine if this is a confirmation event
        event_dict = event_data.model_dump()  # Convert to dictionary
        event_name = str(event_dict["event"]).lower()  # Get the event name
        
        # Check if the order ID is in the orders_list
        if order_id not in self.orders_list.keys():
            return  # Order not tracked, ignore
        
        # Import here to avoid circular imports
        from utils import convert_to_nytzone
        
        # Parse event_dict
        event_dict = convert_to_nytzone(event_dict)
        time_stamp = event_dict["timestamp"]
        orderinfo = event_dict["order"]
        # Remove the "order" key from the event_dict
        event_dict.pop("order", None)
        symbol = orderinfo["symbol"]
        event_dict.update(orderinfo)  # This adds order fields to event_dict
        time_now = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")

        # Process the event data based on the event type
        if (event_name == "fill") or (event_name == "partial_fill"):
            order_type = orderinfo["order_type"]
            trade_side = orderinfo["side"]
            qty_filled = float(orderinfo["qty"])
            fill_price = float(orderinfo.get("filled_avg_price", 0))
            print(f"✅ Order {order_id} filled at {time_now} at price {fill_price}")
            print(f"💸 {time_stamp} Filled {order_type} {trade_side} order for {qty_filled} shares of {symbol} at {fill_price}")
            
            position_fill = event_dict.get("position_qty", 0)
            print(f"📊 Position from broker after the fill: {position_fill} shares of {symbol}")
            
            # Calculate realized P&L and update position tracking
            realized_pnl = self.calc_realized_pnl(trade_side, qty_filled, fill_price, order_id)
            print(f"💰 Realized P&L from this trade: ${realized_pnl:.2f}")
            
            # Append to CSV (write header only if file does not exist)
            if self.fills_file:
                event_frame = pd.DataFrame([event_dict])
                event_frame.to_csv(self.fills_file, mode="a", header=not os.path.exists(self.fills_file), index=False)
                print(f"📁 Fill appended to {self.fills_file}")
            
            # Note: Stream management is handled externally by calling code
            print(f"� Fill processed for order {order_id}. Stream continues for other pending orders.")
            
        elif (event_name == "pending_new") or (event_name == "new") or (event_name == "accepted"):
            print(f"📋 Event {event_name} received for order {order_id} at {time_now}")
            # Already added to orders_list list by submit_order(), so do nothing here
            pass # Do nothing for new/pending events
                    
        elif event_name == "canceled":
            print(f"❌ Order {order_id} canceled at {time_now}")
            # Append to CSV (write header only if file does not exist)
            if self.canceled_file:
                event_frame = pd.DataFrame([event_dict])
                event_frame.to_csv(self.canceled_file, mode="a", header=not os.path.exists(self.canceled_file), index=False)
                print(f"📁 Canceled order appended to {self.canceled_file}")
            
            # Remove canceled order from tracking list
            if order_id in self.orders_list:
                del self.orders_list[order_id]
                print(f"📝 Removed canceled order {order_id} from tracking list")
            
            # Note: Stream management is handled externally by calling code
            print(f"❌ Cancel processed for order {order_id}. Stream continues for other pending orders.")

        elif event_name == "replaced":
            print(f"🔄 Replaced event: {event_dict}")
            # Remove replaced order from tracking list
            if order_id in self.orders_list:
                del self.orders_list[order_id]
                print(f"📝 Removed replaced order {order_id} from tracking list")
            
            # Note: Stream management is handled externally by calling code
            print(f"🔄 Replace processed for order {order_id}. Stream continues for other pending orders.")
            
        elif event_name == "expired":
            print(f"⏰ Expired event: {event_dict}")
            # Remove expired order from tracking list
            if order_id in self.orders_list:
                del self.orders_list[order_id]
                print(f"📝 Removed expired order {order_id} from tracking list")
            
            # Note: Stream management is handled externally by calling code
            print(f"⏰ Expiry processed for order {order_id}. Stream continues for other pending orders.")
            
        else:
            print(f"❓ Unknown event: {event_name}")
            
        print(f"✅ Finished processing the {event_name} update for order {order_id} at {time_now}")

    # end handle_trade_event


# end class Trading



class AlpacAPI:
    """
    Alpaca API wrapper class for API operations.
    
    This class encapsulates Alpaca API functionality including client management,
    order submission, WebSocket connections, and data access with built-in rate limiting.
    
    For position tracking and trade event handling, use the Trading class.
    """
    
    class RateLimitExceededError(Exception):
        """Exception raised when rate limits are exceeded after all retries."""
        pass
    
    # Broker name
    BROKER_NAME = "Alpaca"
    
    def __init__(self, enable_rate_limiting=True, max_retries=3, base_delay=5.0, max_delay=300.0):
        """
        Initialize the AlpacAPI with optional rate limiting.
        
        Args:
            enable_rate_limiting: Whether to enable automatic rate limiting
            max_retries: Maximum retry attempts for rate-limited requests
            base_delay: Base delay in seconds for exponential backoff
            max_delay: Maximum delay in seconds to cap exponential backoff
        """
        self.trading_client = None
        self.confirm_stream = None
        self.data_client = None
        
        # Initialize rate limiting parameters
        self.enable_rate_limiting = enable_rate_limiting
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum seconds between requests
        
        # Set up logging
        self.logger = logging.getLogger(__name__)

    # end constructor


    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if the error is related to rate limiting."""
        error_str = str(error).lower()
        return any(indicator in error_str for indicator in [
            "429", "rate limit", "too many requests", 
            "server rejected websocket", "connection rejected"
        ])


    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay using exponential backoff with jitter."""
        # Exponential backoff: base_delay * 2^(attempt-1)
        delay = self.base_delay * (2 ** (attempt - 1))
        
        # Add jitter (±20% randomization) to avoid thundering herd
        jitter = delay * 0.2 * (random.random() - 0.5)
        delay += jitter
        
        # Cap at max_delay
        return min(delay, self.max_delay)


    async def _enforce_rate_limit(self):
        """Enforce minimum time between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()


    def execute_with_retry_sync(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a synchronous function with retry logic for rate limiting.
        
        Args:
            func: Function to execute
            *args: Arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function execution
            
        Raises:
            Exception: If all retries are exhausted
        """
        last_exception = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # Enforce rate limiting (synchronous)
                current_time = time.time()
                time_since_last = current_time - self.last_request_time
                
                if time_since_last < self.min_request_interval:
                    sleep_time = self.min_request_interval - time_since_last
                    time.sleep(sleep_time)
                
                self.last_request_time = time.time()
                
                # Execute the function
                self.logger.info(f"Executing function (attempt {attempt}/{self.max_retries})")
                result = func(*args, **kwargs)
                
                self.logger.info("Function executed successfully")
                return result
                
            except Exception as e:
                last_exception = e
                
                if self._is_rate_limit_error(e):
                    if attempt < self.max_retries:
                        delay = self._calculate_delay(attempt)
                        self.logger.warning(
                            f"Rate limit error (attempt {attempt}/{self.max_retries}). "
                            f"Retrying in {delay:.1f} seconds..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        self.logger.error(f"Rate limit exceeded after {self.max_retries} attempts")
                        raise self.RateLimitExceededError(
                            f"Rate limit exceeded after {self.max_retries} attempts"
                        ) from e
                else:
                    # Non-rate-limit error, re-raise immediately
                    self.logger.error(f"Non-rate-limit error: {e}")
                    raise e
        
        # If we get here, all retries were exhausted
        raise last_exception

    # end execute_with_retry_sync


    def create_trade_clients(self, env_file=None, TRADE_KEY="ALPACA_TRADE_KEY", TRADE_SECRET="ALPACA_TRADE_SECRET"):
        """
        Create and initialize Alpaca SDK clients for trading and streaming.
        Sets the trading_client and confirm_stream instance variables.
        
        Args:
            env_file (str, optional): Full path to the .env file (including filename). 
                                     If None, will look for .env in current directory or use system env vars.
            TRADE_KEY (str): Name of the trading API key in environment file (default: "ALPACA_TRADE_KEY")
            TRADE_SECRET (str): Name of the trading API secret in environment file (default: "ALPACA_TRADE_SECRET")
            
        Returns:
            tuple: (trading_client, confirm_stream) - Initialized SDK clients
            
        Raises:
            ValueError: If required API keys are not found in environment
        
        Examples:
            # Use default .env file and default key names
            sdk.create_trade_clients()
            # Use specific .env file with default key names
            sdk.create_trade_clients("/path/to/.env")
            # Use default .env file with custom key names
            sdk.create_trade_clients(None, "ALPACA_TRADE_KEY", "ALPACA_TRADE_SECRET")
        """
        # Load the API keys from .env file if provided
        if env_file is not None:
            load_dotenv(env_file)
            print(f"📄 Loading environment variables from: {env_file}")
        else:
            # Load from default .env file in current directory
            load_dotenv()
            print("📄 Loading environment variables from default .env file or system environment")
        
        # Get trade keys from environment using the provided key names
        TRADE_KEY = os.getenv(TRADE_KEY)
        TRADE_SECRET = os.getenv(TRADE_SECRET)

        # Validate that required keys are present
        if not TRADE_KEY or not TRADE_SECRET:
            env_source = f"environment file {env_file}" if env_file else "environment variables"
            raise ValueError(f"Required API keys not found in {env_source}. Please check {TRADE_KEY} and {TRADE_SECRET}.")
        
        # Create clients with rate limiting if enabled
        if self.enable_rate_limiting:
            def _create_clients():
                # Create the SDK trading client and store as instance variable
                self.trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)
                # Create the SDK trade update and confirmation client and store as instance variable
                self.confirm_stream = TradingStream(TRADE_KEY, TRADE_SECRET)
                return self.trading_client, self.confirm_stream
            
            try:
                trading_client, confirm_stream = self.execute_with_retry_sync(_create_clients)
                print(f"✅ SDK clients created successfully with rate limiting")
            except self.RateLimitExceededError:
                print("❌ Rate limit exceeded when creating clients. Please wait and try again.")
                raise
        else:
            # Create the SDK trading client and store as instance variable
            self.trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)
            # Create the SDK trade update and confirmation client and store as instance variable
            self.confirm_stream = TradingStream(TRADE_KEY, TRADE_SECRET)
            print(f"✅ SDK clients created successfully")

        env_source = f"environment file: {env_file}" if env_file else "system environment variables"
        print(f"📡 Using API keys from {env_source}")
        
        return self.trading_client, self.confirm_stream

    # end create_trade_clients


    def create_data_client(self, env_file=None, DATA_KEY="DATA_KEY", DATA_SECRET="DATA_SECRET"):
        """
        Create and configure SDK data client for historical data access.
        
        Args:
            env_file (str): Path to environment file. Defaults to '.env'.
            DATA_KEY (str): API key for data access. If None, reads from environment.
            DATA_SECRET (str): API secret for data access. If None, reads from environment.
        
        Returns:
            StockHistoricalDataClient: Configured data client instance.
        
        Raises:
            ValueError: If API credentials are not found or invalid.
        
        Examples:
            # Create data client with default .env file
            sdk.create_data_client()
            
            # Create data client with custom credentials
            sdk.create_data_client(DATA_KEY="your_key", DATA_SECRET="your_secret")
            
            # Create data client with custom env file
            sdk.create_data_client(env_file="production.env")
        """

        # Load the API keys from .env file if provided
        if env_file is not None:
            load_dotenv(env_file)
            print(f"📄 Loading environment variables from: {env_file}")
        else:
            # Load from default .env file in current directory
            load_dotenv()
            print("📄 Loading environment variables from default .env file or system environment")

        try:
            # Load environment variables if credentials not provided
            DATA_KEY = os.getenv(DATA_KEY)
            DATA_SECRET = os.getenv(DATA_SECRET)
            # Validate credentials
            if not DATA_KEY or not DATA_SECRET:
                raise ValueError(f"API credentials not found. Check {env_file} or provide DATA_KEY and DATA_SECRET parameters.")
            # Create data client
            self.data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)
            logging.info("Data client created successfully")
            return self.data_client
            
        except Exception as e:
            logging.error(f"Failed to create data client: {str(e)}")
            raise ValueError(f"Data client creation failed: {str(e)}")

    # end create_data_client


    async def connect_websocket_with_retry(self, handle_trade_event=None, connection_timeout=30):
        """
        Connect to WebSocket stream with built-in rate limiting and retry logic.
        
        Args:
            handle_trade_event: Optional callback handler function for trade updates
            connection_timeout: Timeout in seconds for WebSocket connection
            
        Returns:
            bool: True if connection successful, False otherwise
            
        Raises:
            ValueError: If confirm_stream is not initialized
        """
        if self.confirm_stream is None:
            raise ValueError("WebSocket stream not initialized. Call create_trade_clients() first.")
        
        if not self.enable_rate_limiting:
            # Direct connection without rate limiting
            try:
                if handle_trade_event:
                    self.confirm_stream.subscribe_trade_updates(handle_trade_event)
                await asyncio.wait_for(
                    self.confirm_stream._run_forever(), 
                    timeout=connection_timeout
                )
                return True
            except Exception as e:
                print(f"❌ WebSocket connection error: {e}")
                return False
        
        # Connection with rate limiting
        connection_attempts = 0
        max_attempts = self.max_retries
        
        # Add initial delay to prevent immediate rate limiting
        initial_delay = self.base_delay
        print(f"⏰ Adding initial delay of {initial_delay} seconds to prevent rate limiting...")
        await asyncio.sleep(initial_delay)
        
        while connection_attempts < max_attempts:
            try:
                connection_attempts += 1
                print(f"🔌 WebSocket connection attempt {connection_attempts}/{max_attempts}")
                
                # Add rate limiting enforcement before connection attempt
                await self._enforce_rate_limit()
                
                if handle_trade_event:
                    self.confirm_stream.subscribe_trade_updates(handle_trade_event)
                
                # Add timeout for connection
                await asyncio.wait_for(
                    self.confirm_stream._run_forever(), 
                    timeout=connection_timeout
                )
                return True
                
            except asyncio.TimeoutError:
                print(f"⏰ Connection timeout after {connection_timeout} seconds")
                if connection_attempts < max_attempts:
                    delay = self._calculate_delay(connection_attempts)
                    print(f"🔄 Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)
                else:
                    print("❌ Max connection attempts reached")
                    break
                    
            except Exception as e:
                error_str = str(e).lower()
                if any(indicator in error_str for indicator in ["429", "rate limit", "rejected", "server rejected websocket"]):
                    print(f"⚠️  Rate limit encountered on WebSocket connection: {e}")
                    if connection_attempts < max_attempts:
                        # Use longer delays for rate limiting during connection handshake
                        delay = self._calculate_delay(connection_attempts)
                        print(f"🔄 Rate limited during connection. Using exponential backoff: waiting {delay:.1f} seconds...")
                        await asyncio.sleep(delay)
                    else:
                        print("❌ Max connection attempts reached due to rate limiting")
                        print("💡 This suggests frequent WebSocket connection attempts.")
                        print("💡 Consider waiting 5-10 minutes before running the script again.")
                        break
                else:
                    print(f"❌ WebSocket error: {e}")
                    if connection_attempts < max_attempts:
                        delay = self.base_delay
                        print(f"🔄 Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)
                    else:
                        break
        
        return False


    async def cleanup_websocket(self):
        """Safely cleanup WebSocket connection."""
        if self.confirm_stream:
            try:
                await self.confirm_stream.stop_ws()
            except Exception as e:
                logging.debug(f"Error stopping WebSocket: {e}")
            
            try:
                await self.confirm_stream.close()
            except Exception as e:
                logging.debug(f"Error closing stream client: {e}")


    @classmethod
    def create_with_rate_limiting(cls, max_retries=5, base_delay=10.0):
        """
        Create an AlpacAPI instance with rate limiting enabled.
        
        Args:
            max_retries: Maximum retry attempts for rate-limited requests (default: 5)
            base_delay: Base delay in seconds for exponential backoff (default: 10.0)
            
        Returns:
            AlpacAPI: Instance with rate limiting enabled
            
        Note:
            Default parameters are conservative to handle WebSocket rate limiting.
            WebSocket connections are particularly sensitive to rate limits.
        """
        return cls(enable_rate_limiting=True, max_retries=max_retries, base_delay=base_delay)


    @classmethod
    def create_without_rate_limiting(cls):
        """
        Create an AlpacAPI instance without rate limiting.
        
        Returns:
            AlpacAPI: Instance with rate limiting disabled
        """
        return cls(enable_rate_limiting=False)


    def get_trading_client(self):
        """
        Get the trading client.
        
        Returns:
            TradingClient: The initialized trading client
            
        Raises:
            ValueError: If trading_client is not initialized
        """
        if self.trading_client is None:
            raise ValueError("Trading client not initialized. Call create_trade_clients() first.")
        
        return self.trading_client


    def get_confirm_stream(self):
        """
        Get the confirmation stream instance.
        
        Returns:
            TradingStream: The confirmation stream instance.
            
        Raises:
            ValueError: If the confirmation stream has not been initialized.
        """
        if self.confirm_stream is None:
            raise ValueError("Confirmation stream not initialized. Call create_trade_clients() first.")
        return self.confirm_stream


    def get_data_client(self):
        """
        Get the data client instance.
        
        Returns:
            StockHistoricalDataClient: The data client instance.
            
        Raises:
            ValueError: If the data client has not been initialized.
        """
        if self.data_client is None:
            raise ValueError("Data client not initialized. Call create_data_client() first.")
        return self.data_client


    def get_position(self, symbol):
        """
        Get the open position for the symbol using the trading client.
        
        Args:
            symbol (str): Trading symbol
            
        Returns:
            Position object or None if no position exists
            
        Raises:
            ValueError: If trading_client is not initialized
        """
        if self.trading_client is None:
            raise ValueError("Trading client not initialized. Call create_trade_clients() first.")
        
        position = None  # Initialize position variable
        # Get the open position for the symbol
        try:
            position = self.trading_client.get_open_position(symbol)
        except Exception as e:
            pass # Do nothing
            # print(f"Error getting open position for {symbol}: {e}")
        if position:
            print(f"({self.BROKER_NAME}) Open position for {symbol}: {position.qty} shares at {position.avg_entry_price}")
        else:
            print(f"({self.BROKER_NAME}) No open position for {symbol}.")
        return position


    def cancel_orders(self, symbol, orders_list=None, canceled_file=None):
        """
        Cancel orders for a symbol using the trading client.
        
        Args:
            symbol (str): Trading symbol
            orders_list (list, optional): List of order IDs to cancel. If None, cancels all open orders.
            canceled_file (str, optional): Path to CSV file to save canceled order information
            
        Returns:
            list: Updated orders list with remaining orders
            
        Raises:
            ValueError: If trading_client is not initialized
        """
        if self.trading_client is None:
            raise ValueError("Trading client not initialized. Call create_trade_clients() first.")
        
        # Case when orders_list is None
        # Cancel all the open orders for the symbol because orders_list is None
        if orders_list is None:
            # Get all the open orders for the symbol
            request_params = GetOrdersRequest(
                                status=QueryOrderStatus.OPEN,
                                symbols=[symbol],
                            )
            orders_list = self.trading_client.get_orders(filter=request_params)
            # Cancel the open orders one at a time
            print(f"Found {len(orders_list)} open orders for {symbol}.")
            for open_order in orders_list:
                # If it's not a string, then extract the order ID as a string
                order_id = open_order
                if not isinstance(order_id, str):
                    order_id = str(order_id.id)
                # print(f"Canceling order: {order_id} for {symbol}")
                try:
                    # Cancel the order
                    self.trading_client.cancel_order_by_id(order_id=order_id)
                    # Get the canceled order status
                    order_status = self.trading_client.get_order_by_id(order_id=order_id)
                    # Append the canceled order status to CSV file only if canceled_file is not None
                    if canceled_file is not None:
                        canceled_frame = pd.DataFrame([order_status.model_dump()])
                        canceled_frame.to_csv(canceled_file, mode="a", header=not os.path.exists(canceled_file), index=False)
                    print(f"Cancelled order: {order_id} for {symbol}")
                    # Remove the canceled order ID from the open orders list
                    orders_list.remove(open_order)
                    print(f"Removed order ID {order_id} from open orders list. Remaining number of open orders: {len(orders_list)}")
                except Exception as e:
                    print(f"Error canceling order {order_id} for {symbol}: {e}")
            if canceled_file is not None:
                print(f"Canceled orders saved to {canceled_file}")
            else:
                print("Canceled orders not saved (canceled_file=None)")
            return orders_list

        # Case when orders_list is not None
        # Cancel the open orders from the list orders_list one at a time
        if not orders_list: # Check if the list orders_list is empty
            print(f"No open orders found for {symbol}.")
            return [] # Return an empty list if orders_list is an empty list
        else:
            print(f"Found {len(orders_list)} open orders for {symbol}.")
            for order_id in orders_list:
                # If it's not a string, then extract the order ID as a string
                if not isinstance(order_id, str):
                    order_id = str(order_id.id)
                # print(f"Canceling order: {order_id} for {symbol}")
                try:
                    # Remove the canceled order ID from the open orders list
                    # Cancel the order
                    self.trading_client.cancel_order_by_id(order_id=order_id)
                    # Get the canceled order status
                    order_status = self.trading_client.get_order_by_id(order_id=order_id)
                    # Append the canceled order status to CSV file only if canceled_file is not None
                    if canceled_file is not None:
                        canceled_frame = pd.DataFrame([order_status.model_dump()])
                        canceled_frame.to_csv(canceled_file, mode="a", header=not os.path.exists(canceled_file), index=False)
                    # Remove the canceled order ID from the open orders list
                    orders_list.remove(order_id)
                    print(f"Cancelled order: {order_id} for {symbol}")
                    print(f"Removed order ID {order_id} from open orders list. Remaining number of open orders: {len(orders_list)}")
                except Exception as e:
                    print(f"Error canceling order {order_id} for {symbol}: {e}")
                    # Remove the order ID from the open orders list anyway
                    orders_list.remove(order_id)
                    print(f"Removed order ID {order_id} from the open orders list after the error. Remaining number of open orders: {len(orders_list)}")
            if canceled_file is not None:
                print(f"Canceled orders saved to {canceled_file}")
            else:
                print("Canceled orders not saved (canceled_file=None)")
            return orders_list

    # end cancel_orders


    def submit_order(self, symbol, shares_per_trade, side, type, limit_price):
        """
        Submit a trade order using the Alpaca TradingClient.
        
        Args:
            symbol (str): Trading symbol
            shares_per_trade (int): Number of shares to trade
            side: Order side (OrderSide.BUY or OrderSide.SELL)
            type (str): Order type ("market" or "limit")
            limit_price (float): Limit price for limit orders
            
        Returns:
            Order response object or None if order failed
            
        Note:
            Uses self.submits_file and self.error_file for CSV logging
            
        Raises:
            ValueError: If trading_client is not initialized
        """
        if self.trading_client is None:
            raise ValueError("Trading client not initialized. Call create_trade_clients() first.")
        
        timezone = ZoneInfo("America/New_York")
        time_now = datetime.now(timezone)

        # Define the order parameters based on the order type
        if type == "market":
            # Create market order parameters
            print(f"Submitting a {type} {side} order for {shares_per_trade} shares of {symbol}")
            order_params = MarketOrderRequest(
                symbol = symbol,
                qty = shares_per_trade,
                side = side,
                type = type,
                time_in_force = TimeInForce.DAY
            )
        elif type == "limit":
            # Create limit order parameters
            print(f"Submitting a {type} {side} order for {shares_per_trade} shares of {symbol} at {limit_price}")
            order_params = LimitOrderRequest(
                symbol = symbol,
                qty = shares_per_trade,
                side = side,
                type = type,
                limit_price = limit_price,
                extended_hours = True,
                time_in_force = TimeInForce.DAY,
            )

        # Submit the order with rate limiting if enabled
        def _submit_order_request():
            return self.trading_client.submit_order(order_data=order_params)
        
        # Initialize order_response to None
        order_response = None
        
        try:
            if self.enable_rate_limiting:
                order_response = self.execute_with_retry_sync(_submit_order_request)
                print(f"📡 Order submitted with rate limiting protection")
            else:
                order_response = _submit_order_request()
            
            # Check if order_response is None after submission
            if order_response is None:
                print(f"❌ Order submission failed: order_response is None")
                return None
            
            print(f"✅ Order submitted: Symbol={order_response.symbol}, Type={order_response.type}, Side={order_response.side}, Qty={order_response.qty}")
            
            # Add order to tracking list with limit price
            order_id = str(order_response.id)
            self.orders_list[order_id] = limit_price
            print(f"📝 Added order {order_id} to tracking list with price {limit_price}")
            
            # Save the submit information to a CSV file
            order_frame = order_response.model_dump()  # or order_response._raw for some SDKs
            order_frame = pd.DataFrame([order_frame])
            # Append to CSV (write header only if file does not exist)
            order_frame.to_csv(self.submits_file, mode="a", header=not os.path.exists(self.submits_file), index=False)
            print(f"📁 Order appended to {self.submits_file}")
            return order_response
            
        except self.RateLimitExceededError as e:
            print(f"❌ Rate limit exceeded when submitting order: {e}")
            # Save rate limit error to CSV
            error_msg = pd.DataFrame([{
                "error": "rate_limit", 
                "timestamp": time_now, 
                "symbol": symbol, 
                "side": side, 
                "message": str(e)
            }])
            error_msg.to_csv(self.error_file, mode="a", header=not os.path.exists(self.error_file), index=False)
            return None
            
        except Exception as e:
            # Convert error to string and save to CSV
            error_msg = pd.DataFrame([{
                "error": "submission_failed", 
                "timestamp": time_now, 
                "symbol": symbol, 
                "side": side, 
                "message": str(e)
            }])
            error_msg.to_csv(self.error_file, mode="a", header=not os.path.exists(self.error_file), index=False)
            print(f"❌ Trade order rejected: {e}")
            return None

    # end submit_order


    @staticmethod
    async def stream_bars(symbol, strategy):
        """
        Stream the price bars from the WebSocket proxy and pass them on to a trading strategy.

        When a new WebSocket bar message arrives matching the symbol, it converts the JSON data into a Bar object using the Bar constructor.
        It then calls the strategy function specified by strategy.strategy_function via the execute_strategy method.

        Args:
            symbol (str): Trading symbol to filter for
            strategy: Strategy instance with execute_strategy method and strategy_function attribute.
        """
        # Import here to avoid circular imports
        import json
        from TechIndic import Bar
        import websockets

        # Connect to the WebSocket proxy URL
        proxy_url = "ws://localhost:8765"
        reconnect_delay = 5
        while True:
            try:
                async with websockets.connect(proxy_url) as ws:
                    print(f"Connected to WebSocket proxy at {proxy_url}")
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            # Alpaca sends a list of events, each is a dict
                            if isinstance(data, list):
                                for event in data:
                                    # Only handle bar events for our symbol
                                    if event.get("T") == "b" and event.get("S") == symbol:
                                        # Create a Bar object directly from the event data
                                        bar_object = Bar(event)
                                        # Call the trading strategy function via execute_strategy wrapper
                                        await strategy.execute_strategy(bar_object)
                            elif isinstance(data, dict):
                                if data.get("T") == "b" and data.get("S") == symbol:
                                    # Create a Bar object directly from the data
                                    bar_object = Bar(data)
                                    # Call the trading strategy function via execute_strategy wrapper
                                    await strategy.execute_strategy(bar_object)
                        except Exception as e:
                            print(f"Error processing message: {e}")
            except Exception as e:
                print(f"WebSocket error: {e}. Reconnecting in {reconnect_delay} seconds...")
                time.sleep(reconnect_delay)

    # end stream_bars

# end class AlpacAPI

