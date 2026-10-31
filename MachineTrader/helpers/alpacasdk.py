"""
Package AlpacaSDK containing the class AlpacAPI for Alpaca API interactions, and the class Trading for submitting trades, position tracking, and trade event handling.

"""

import os
import logging
import math
import re
import pandas as pd
import time
import asyncio
import random
from datetime import datetime, date, time as dtime, timedelta
from zoneinfo import ZoneInfo
from types import SimpleNamespace
from dotenv import load_dotenv
from typing import Optional, Callable, Any
from MachineTrader.helpers.markets import Markets
from MachineTrader.helpers.mt_file_handlers import FileMan
from MachineTrader.helpers.api_responses import (
    event_in_group,
    status_in_group,
)

try:
    from MachineTrader.helpers.timestamp_utils import coerce_market_datetime_ny, format_timestamp_ny
except ImportError:
    from MachineTrader.helpers.timestamp_utils import coerce_market_datetime_ny, format_timestamp_ny

from alpaca.trading.client import TradingClient
from alpaca.trading.stream import TradingStream
from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest, MarketOrderRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.data import StockHistoricalDataClient
from alpaca.data.live.stock import StockDataStream


class Trading:
    """
    Trading class for submitting trades, position tracking, and trade event handling.
    
    This class encapsulates position tracking variables and trading-related 
    functionality that doesn't require direct API access.
    """

    EOD_FLATTEN_LEAD_MINUTES = 2

    def __init__(self, symbol=None, alpaca_api=None):
        """
        Initialize the Trading class with position tracking variables.
        
        Args:
            symbol (str, optional): Trading symbol (e.g., "AAPL", "SPY")
        
        Instance Variables:
            Trading Symbol:
                symbol: Trading symbol (e.g., "AAPL", "SPY")
            Position Tracking:
                position_queue: Signed-price queue map keyed by symbol
                position_shares: Current share count (positive long, negative short)
                position_broker: Broker-reported position count
                broker_qty: Broker position quantity as float
                shares_available: Available shares to trade (calculated from broker position)
                orders_list: Dictionary of pending order IDs and their limit prices
                pnl_real_total: Cumulative realized profit and loss from all trades
                num_shares: Number of shares in position list
                pnl_unreal: Current unrealized profit and loss
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
        self.alpaca_api = alpaca_api
        
        # Initialize position tracking variables
        # Signed-price queue by symbol: negative prices for long lots, positive for short lots.
        symbol_key = str(symbol or "").upper()
        self._position_queue = {symbol_key: []} if symbol_key else {}
        self.position_shares = 0  # The number of shares currently owned (positive for long positions, negative for short positions)
        self.position_broker = None  # The number of shares owned according to the broker
        self.broker_qty = None  # Broker position quantity as float
        self.shares_available = 0  # Available shares to trade (calculated from broker position)
        self.orders_list = {}  # Dictionary of pending limit order IDs: {order_id: limit_price}
        self.pnl_real_total = 0.0  # Cumulative realized profit and loss from all trades
        self.num_shares = 0  # Number of shares in position list
        self.pnl_unreal = 0.0  # Current unrealized profit and loss
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
        self.persist_submits_log = False
        self.state_file = None
        self.error_file = None
        self.strategy_name = None
        self.manual_reference_price = None
        self.manual_start_time = None
        self.manual_end_time = None
        self.open_price = None
        self.last_submit_rejection = None
        self.current_price = None
        self.last_minute_key = None
        self.current_position = 0
        self.target_position = 0
        self.strategy_trade_amounts = {}
        self.strategy_trade_events = []
        self.pending_order_id = None
        self.pending_order_side = None
        self.pending_submitted_at = None
        self._last_order_status_log_bucket = None
        self._last_out_of_session_log_bucket = None
        self._cached_session_date = None
        self._cached_session_start = dtime(9, 30)
        self._cached_session_end = dtime(16, 0)
        self._eod_flat_triggered = False
        self.data_proxy_url = os.getenv("DATA_PROXY_URL")
        self.markets = Markets()

    def _symbol_key(self) -> str:
        return str(self.symbol or "").upper()

    def _get_local_position_queue(self) -> list[float]:
        symbol_key = self._symbol_key()
        queue_map = getattr(self, "_position_queue", None)
        if not isinstance(queue_map, dict):
            queue_map = {}
            self._position_queue = queue_map
        queue = queue_map.get(symbol_key)
        if not isinstance(queue, list):
            queue = []
            queue_map[symbol_key] = queue
        return queue

    def _set_local_position_queue(self, queue_prices: list[float]) -> None:
        symbol_key = self._symbol_key()
        queue_map = getattr(self, "_position_queue", None)
        if not isinstance(queue_map, dict):
            queue_map = {}
            self._position_queue = queue_map
        queue_map[symbol_key] = [float(v) for v in list(queue_prices or [])]

    def _refresh_daily_files(self):
        self.state_file = FileMan.daily_path(self.state_file)
        self.fills_file = FileMan.daily_path(self.fills_file)
        self.canceled_file = FileMan.daily_path(self.canceled_file)
        self.submits_file = FileMan.daily_path(self.submits_file)
        self.error_file = FileMan.daily_path(self.error_file)


    def add_strategy_amount(self, symbol: str, qty: float, metadata: Optional[dict] = None):
        """Accumulate signed trade deltas and publish strategy metadata."""
        symbol_key = str(symbol or self.symbol or "").upper()
        if not symbol_key:
            return 0.0

        signed_qty = float(qty or 0.0)
        running = self.strategy_trade_amounts.get(symbol_key, 0.0)
        if abs(signed_qty) >= 1e-12:
            running += signed_qty
            self.strategy_trade_amounts[symbol_key] = running

        event = {
            "timestamp": format_timestamp_ny(None),
            "symbol": symbol_key,
            "qty": signed_qty,
            "running_qty": running,
            "metadata": metadata or {},
        }
        self.strategy_trade_events.append(event)
        return running


    def consume_strategy_amounts(self):
        """Return and clear accumulated strategy deltas."""
        amounts = self.strategy_trade_amounts.copy()
        self.strategy_trade_amounts = {}
        return amounts


    def consume_strategy_events(self):
        """Return and clear accumulated strategy events with metadata."""
        events = list(self.strategy_trade_events)
        self.strategy_trade_events = []
        return events


    def convert_bar(self, proxy_bar):
        """Convert a proxy stream bar payload into a bar-like object."""
        if not isinstance(proxy_bar, dict):
            return proxy_bar

        if proxy_bar.get("T") != "b":
            return None

        timestamp = coerce_market_datetime_ny(proxy_bar.get("t"), fallback_to_now=False)
        if timestamp is None:
            return None

        return SimpleNamespace(
            symbol=proxy_bar.get("S"),
            close=float(proxy_bar.get("c", 0.0)),
            vwap=float(proxy_bar.get("vw", proxy_bar.get("c", 0.0))),
            timestamp=timestamp,
            high=float(proxy_bar.get("h", proxy_bar.get("c", 0.0))),
            low=float(proxy_bar.get("l", proxy_bar.get("c", 0.0))),
            volume=float(proxy_bar.get("v", 0.0)),
        )


    def _get_price_field(self, field_name):
        if self.alpaca_api is not None and hasattr(self.alpaca_api, field_name):
            return getattr(self.alpaca_api, field_name)
        return getattr(self, f"_{field_name}", None)


    def _set_price_field(self, field_name, value):
        setattr(self, f"_{field_name}", value)
        if self.alpaca_api is not None and hasattr(self.alpaca_api, field_name):
            setattr(self.alpaca_api, field_name, value)


    @property
    def last_price(self):
        return self._get_price_field("last_price")


    @last_price.setter
    def last_price(self, value):
        self._set_price_field("last_price", value)


    @property
    def last_bar(self):
        return self._get_price_field("last_bar")


    @last_bar.setter
    def last_bar(self, value):
        self._set_price_field("last_bar", value)


    @property
    def manual_reference_price(self):
        return self._get_price_field("manual_reference_price")


    @manual_reference_price.setter
    def manual_reference_price(self, value):
        self._set_price_field("manual_reference_price", value)


    @property
    def manual_start_time(self):
        return self._get_price_field("manual_start_time")


    @manual_start_time.setter
    def manual_start_time(self, value):
        self._set_price_field("manual_start_time", value)


    @property
    def manual_end_time(self):
        return self._get_price_field("manual_end_time")


    @manual_end_time.setter
    def manual_end_time(self, value):
        self._set_price_field("manual_end_time", value)


    @property
    def open_price(self):
        return self._get_price_field("open_price")


    @open_price.setter
    def open_price(self, value):
        self._set_price_field("open_price", value)


    @property
    def current_price(self):
        return self._get_price_field("current_price")


    @current_price.setter
    def current_price(self, value):
        self._set_price_field("current_price", value)

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
        
        file_names = FileMan.create_file_names(
            strategy_name=strategy_name,
            timezone=timezone,
            dir_name=dir_name,
            env_file=env_file,
            dir_env_var=dir_env_var,
        )
        
        # Set file paths as instance variables
        self.state_file = file_names["state_file"]
        self.submits_file = file_names["submits_file"]
        self.fills_file = file_names["fills_file"]
        self.canceled_file = file_names["canceled_file"]
        self.error_file = file_names["error_file"]
        
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
            - Updates the symbol queue inside self._position_queue
            - Updates self.pnl_real_total with cumulative realized P&L
            - Updates self.position_shares with net position quantity
            
        Examples:
            # First buy trade - no realized P&L
            pnl = trading.calc_realized_pnl("buy", 100, 50.0, "order_1")
            # pnl = 0.0, queue holds 100 long lots at 50.0
            
            # Partial sell - realizes P&L on 50 shares
            pnl = trading.calc_realized_pnl("sell", 50, 55.0, "order_2") 
            # pnl = 250.0 (50 shares * $5 profit), queue retains 50 long lots at 50.0
            
            # Complete sell - realizes P&L on remaining 50 shares
            pnl = trading.calc_realized_pnl("sell", 50, 52.0, "order_3")
            # pnl = 100.0 (50 shares * $2 profit), queue becomes empty
        """
        del order_id
        from MachineTrader.helpers import calc_pnls as _calc_pnls

        side_text = str(trade_side or "").strip().lower()
        if side_text not in {"buy", "sell"}:
            return 0.0

        try:
            fill_qty = int(round(abs(float(qty_filled or 0.0))))
            fill_price_num = float(fill_price or 0.0)
        except (TypeError, ValueError):
            return 0.0
        if fill_qty <= 0 or fill_price_num <= 0.0:
            return 0.0

        queue_prices = self._get_local_position_queue()
        normalized_queue = _calc_pnls.normalize_signed_price_queue(queue_prices)

        updated_queue, pnl_real = _calc_pnls.match_fill_lifo(
            normalized_queue,
            side=side_text,
            fill_price=float(fill_price_num),
            fill_qty=int(fill_qty),
        )
        self._set_local_position_queue(list(updated_queue))
        self.num_shares = len(updated_queue)
        self.position_shares = int(round(float(_calc_pnls.signed_queue_to_qty(updated_queue))))
        self.pnl_real_total += float(pnl_real)
        return float(pnl_real)

    # end calc_realized_pnl


    def calc_unrealized_pnl(self):
        """
        Calculate the unrealized P&L and update the stock positions.
        
        The local symbol queue is a list of signed fill prices for each open lot.
        Negative prices indicate long positions, and positive prices indicate short positions.
        Because when we buy a stock we pay for it, which is a negative cash flow, and when we sell it, 
        we receive the market price, which is a positive cash flow.
        
        This method updates the instance variables:
        - self.num_shares: Number of shares in position list
        - self.position_shares: Net position (positive for long, negative for short)
        - self.pnl_unreal: Current unrealized profit/loss
        
        Uses self.last_price as the current market price for calculations.
        
        Returns:
            tuple: (position_shares, pnl_unreal)
        """
        from MachineTrader.helpers import calc_pnls as _calc_pnls

        queue_prices = self._get_local_position_queue()
        normalized_queue = _calc_pnls.normalize_signed_price_queue(queue_prices)

        self._set_local_position_queue(list(normalized_queue))
        self.num_shares = len(normalized_queue)
        self.position_shares = int(round(float(_calc_pnls.signed_queue_to_qty(normalized_queue))))

        try:
            last_price_num = float(self.last_price) if self.last_price is not None else None
        except (TypeError, ValueError):
            last_price_num = None
        self.pnl_unreal = float(_calc_pnls.unrealized_pnl_from_signed_queue(normalized_queue, last_price_num))

        return self.position_shares, self.pnl_unreal

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
                    '_position_queue': dict,  # Signed-price queue map
                    'orders_list': dict,  # Pending orders
                    'num_buy_orders': int,  # Number of buy orders
                    'num_sell_orders': int,  # Number of sell orders
                    'total_orders': int,  # Total number of orders
                    'pnl_real_total': float,  # Total realized P&L
                    'pnl_unreal': float,  # Current unrealized P&L
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

        # Create comprehensive state dictionary
        state = {
            'position_broker': self.position_broker,
            'shares_available': self.shares_available,
            'position_shares': self.position_shares,
            '_position_queue': dict(getattr(self, "_position_queue", {}) or {}),
            'orders_list': self.orders_list.copy(),  # Return a copy to prevent external modification
            'num_buy_orders': self.num_buy_orders,
            'num_sell_orders': self.num_sell_orders,
            'total_orders': self.total_orders,
            'pnl_real_total': self.pnl_real_total,
            'pnl_unreal': self.pnl_unreal,
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
        print(f"   📋 Position Queue Entries: {self.num_shares}")
        print(f"   📝 Pending Orders: {self.total_orders} (Buy: {self.num_buy_orders}, Sell: {self.num_sell_orders})")
        print(f"   💰 Realized P&L: ${self.pnl_real_total:.2f}")
        print(f"   💵 Unrealized P&L: ${self.pnl_unreal:.2f}")
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
            self._refresh_daily_files()
            # Update prices using the flexible update_prices method
            self.update_prices(**kwargs)
            
            # Prefer bar/event timestamp; fallback to current NY time.
            raw_timestamp = kwargs.get("timestamp", None)
            if raw_timestamp is None:
                raw_timestamp = kwargs.get("t", None)
            if raw_timestamp is None and isinstance(kwargs.get("bar"), dict):
                bar_payload = kwargs.get("bar") or {}
                raw_timestamp = bar_payload.get("timestamp", bar_payload.get("t", None))
            timestamp = format_timestamp_ny(raw_timestamp)
            
            # Calculate unrealized P&L using current price
            if self.last_price is not None:
                self.calc_unrealized_pnl()
            
            # Extract additional strategy parameters from kwargs
            volatility = kwargs.get('volatility', 0.0)
            zscore = kwargs.get('zscore', 0.0)
            order = kwargs.get('order', None)
            
            # Create state data dictionary
            state_data = {
                "timestamp": timestamp,
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
                "pnlReal": self.pnl_real_total,
                "pnlUnreal": self.pnl_unreal,
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


    def _session_window_for(self, day):
        if self._cached_session_date != day:
            self._cached_session_date = day
            self._cached_session_start = self.manual_start_time or self.markets.get_open_time(day)
            self._cached_session_end = self.manual_end_time or self.markets.get_close_time(day)
            self._eod_flat_triggered = False
        return self._cached_session_start, self._cached_session_end


    def _in_regular_session(self, ts_ny) -> bool:
        t = ts_ny.time()
        start_t, end_t = self._session_window_for(ts_ny.date())
        return (t >= start_t) and (t <= end_t)


    def _is_eod_flat_minute(self, ts_ny) -> bool:
        _, end_t = self._session_window_for(ts_ny.date())
        end_dt = datetime(ts_ny.year, ts_ny.month, ts_ny.day, end_t.hour, end_t.minute, tzinfo=ZoneInfo("America/New_York"))
        bar_dt = datetime(ts_ny.year, ts_ny.month, ts_ny.day, ts_ny.hour, ts_ny.minute, tzinfo=ZoneInfo("America/New_York"))
        return bar_dt >= end_dt - timedelta(minutes=self.EOD_FLATTEN_LEAD_MINUTES)


    def _desired_position(self, price_now: float):
        if self.open_price is None:
            return 0
        if price_now > self.open_price:
            return 1
        if price_now < self.open_price:
            return -1
        return 0


    def _clear_pending(self):
        self.pending_order_id = None
        self.pending_order_side = None
        self.pending_submitted_at = None


    @staticmethod
    def _normalize_token(value_obj) -> str:
        text = str(value_obj or "").strip().lower()
        if "." in text:
            text = text.split(".")[-1]
        return text.replace("-", "_").replace(" ", "_")


    def _normalize_order_status(self, status_obj) -> str:
        return self._normalize_token(status_obj)


    def _normalize_event_name(self, event_name_obj) -> str:
        return self._normalize_token(event_name_obj)


    def _submit_market_order(self, side: OrderSide, qty: int):
        if self.pending_order_id is not None:
            return

        order_data = MarketOrderRequest(
            symbol=self.symbol,
            qty=qty,
            side=side,
            type="market",
            time_in_force=TimeInForce.DAY,
        )
        order_response = self.trading_client.submit_order(order_data=order_data)
        self.pending_order_id = str(order_response.id)
        self.pending_order_side = side
        self.pending_submitted_at = datetime.now(ZoneInfo("America/New_York"))
        print(f"Submitted market order: id={self.pending_order_id}, side={side}, qty={qty}")


    def _update_position_single(self):
        """
        Update the current position to match the target position by submitting a market order.
        """
        if self.pending_order_id is not None:
            return
        if self.target_position == self.current_position:
            return
        if self.current_position != 0:
            flatten_side = OrderSide.SELL if self.current_position > 0 else OrderSide.BUY
            self._submit_market_order(flatten_side, abs(self.current_position))
            return
        if self.target_position > 0:
            self._submit_market_order(OrderSide.BUY, 1)
        elif self.target_position < 0:
            self._submit_market_order(OrderSide.SELL, 1)


    async def process_strategy_bar(self, event: dict):
        """Process a price bar event for the Tanaka strategy."""
        event_type = str(event.get("T", event.get("type", ""))).strip().lower()
        if event_type not in {"b", "bar"}:
            return

        event_symbol = str(event.get("S", event.get("symbol", ""))).strip().upper()
        if event_symbol != self.symbol:
            return

        event_ts = event.get("t", event.get("timestamp"))
        event_close = event.get("c", event.get("close"))
        if event_ts is None or event_close is None:
            return

        ts_ny = coerce_market_datetime_ny(event_ts, fallback_to_now=False)
        if ts_ny is None:
            return

        bar_date = ts_ny.date()
        if self._cached_session_date != bar_date:
            self._session_window_for(bar_date)
            self.open_price = self.manual_reference_price
            self.last_minute_key = None
            self._last_out_of_session_log_bucket = None

        if not self._in_regular_session(ts_ny):
            start_t, end_t = self._session_window_for(ts_ny.date())
            log_bucket = (ts_ny.year, ts_ny.month, ts_ny.day, ts_ny.hour, ts_ny.minute)
            if log_bucket != self._last_out_of_session_log_bucket:
                self._last_out_of_session_log_bucket = log_bucket
                if self.open_price is None:
                    print(
                        f"{ts_ny}: Received bar for {self.symbol} outside session "
                        f"({start_t}-{end_t}). Waiting for first in-session bar to set reference price."
                    )
                else:
                    print(
                        f"{ts_ny}: Received bar for {self.symbol} outside session "
                        f"({start_t}-{end_t}). Current reference={self.open_price:.4f}."
                    )
            return

        price_now = float(event_close)
        self.current_price = price_now

        minute_key = (ts_ny.year, ts_ny.month, ts_ny.day, ts_ny.hour, ts_ny.minute)
        if minute_key == self.last_minute_key:
            return
        self.last_minute_key = minute_key

        if self.open_price is None:
            self.open_price = price_now
            start_t, _ = self._session_window_for(ts_ny.date())
            print(f"Reference price captured for {self.symbol}: {self.open_price:.4f} at {ts_ny} (session start={start_t})")

        ref_param = f"{self.manual_reference_price:.4f}" if self.manual_reference_price is not None else "first_regular_session_price"
        data_proxy_url = getattr(self, "data_proxy_url", None) or os.getenv("DATA_PROXY_URL", "ws://localhost:8765")
        print(f"Parsing price bar for strategy: {self.strategy_name} | symbol={self.symbol}, reference_mode={ref_param}, data_proxy_url={data_proxy_url}\n")

        if self.open_price is None:
            print(f"{ts_ny}: Waiting for reference price for {self.symbol} (session start price)...")
            return

        if self._is_eod_flat_minute(ts_ny):
            if not self._eod_flat_triggered:
                _, end_t = self._session_window_for(ts_ny.date())
                print(f"{ts_ny}: ⏰ EOD flatten triggered ({self.EOD_FLATTEN_LEAD_MINUTES} min before session end {end_t}). Targeting flat from position={self.current_position}.")
                self._eod_flat_triggered = True
            self.target_position = 0
            self._update_position_single()
            return

        if self._eod_flat_triggered:
            return

        self.target_position = self._desired_position(price_now)
        print(f"{ts_ny}: last_price={price_now:.4f}, reference_price={self.open_price:.4f}, current_position={self.current_position}, target_pos={self.target_position}, pending={self.pending_order_id}")
        self._update_position_single()


    async def on_trade_update(self, event_data):
        event_dict = event_data.model_dump()
        event_name = self._normalize_event_name(event_dict.get("event", ""))
        order = event_dict.get("order", {})

        order_id = str(order.get("id", ""))
        if not order_id:
            return
        if self.pending_order_id is not None and order_id != self.pending_order_id:
            return

        if event_in_group(event_name, "fill_progress"):
            pos_qty = event_dict.get("position_qty", None)
            if pos_qty is not None:
                self.current_position = int(round(float(pos_qty)))
            else:
                side_text = str(order.get("side", "")).lower()
                fill_qty = float(order.get("filled_qty", order.get("qty", 0)) or 0)
                if "buy" in side_text:
                    self.current_position += int(round(fill_qty))
                elif "sell" in side_text:
                    self.current_position -= int(round(fill_qty))

            if event_in_group(event_name, "fill"):
                print(f"Fill confirmed for {order_id}. position={self.current_position}")
                self._clear_pending()
                self._update_position_single()
        elif event_in_group(event_name, "cancel_terminal"):
            print(f"Order {order_id} {event_name}; clearing pending state.")
            self._clear_pending()


    def _apply_fill(self, order_status) -> bool:
        status = self._normalize_order_status(order_status.status)
        if not status_in_group(status, "fill_progress"):
            return False
        side_text = str(order_status.side).lower()
        filled_qty = int(round(float(order_status.filled_qty or 0)))
        if "buy" in side_text:
            self.current_position += filled_qty
        elif "sell" in side_text:
            self.current_position -= filled_qty
        return status_in_group(status, "filled")


    async def poll_pending_order(self, position_poll_interval: float = 60.0, pending_poll_interval: float = 0.2):
        next_position_sync = datetime.now(ZoneInfo("America/New_York"))
        while True:
            await asyncio.sleep(pending_poll_interval)

            now_ny = datetime.now(ZoneInfo("America/New_York"))
            if now_ny >= next_position_sync:
                try:
                    broker_pos = self.trading_client.get_open_position(self.symbol)
                    self.current_position = int(round(float(broker_pos.qty))) if broker_pos is not None else 0
                    is_done_for_day = self._eod_flat_triggered and self.pending_order_id is None and self.current_position == 0
                    if not is_done_for_day:
                        print(f"Poll: broker position={self.current_position} for {self.symbol}")
                except Exception as exc:
                    exc_text = str(exc).lower()
                    if "position does not exist" in exc_text:
                        self.current_position = 0
                        is_done_for_day = self._eod_flat_triggered and self.pending_order_id is None
                        if not is_done_for_day:
                            print(f"Poll: broker position=0 for {self.symbol} (no open position)")
                    else:
                        print(f"Poll position error for {self.symbol}: {exc}")
                next_position_sync = now_ny + timedelta(seconds=position_poll_interval)

            if self.pending_order_id is None:
                continue

            try:
                order_status = self.trading_client.get_order_by_id(self.pending_order_id)
                status = self._normalize_order_status(order_status.status)
                log_bucket = (self.pending_order_id, now_ny.year, now_ny.month, now_ny.day, now_ny.hour, now_ny.minute)
                if log_bucket != self._last_order_status_log_bucket:
                    print(f"Poll: order {self.pending_order_id} status={status}")
                    self._last_order_status_log_bucket = log_bucket
                if status == "filled":
                    self._apply_fill(order_status)
                    print(f"Poll fill confirmed. position={self.current_position}")
                    self._clear_pending()
                    self._update_position_single()
                elif status_in_group(status, "fill_progress") and not status_in_group(status, "filled"):
                    pass
                elif status_in_group(status, "terminal_excluding_filled") or status == "calculated":
                    print(f"Poll: order {self.pending_order_id} {status}; clearing pending state.")
                    self._clear_pending()
            except Exception as exc:
                print(f"Poll error for order {self.pending_order_id}: {exc}")

            if self.pending_order_id is not None and self.pending_submitted_at is not None:
                age_seconds = (datetime.now(ZoneInfo("America/New_York")) - self.pending_submitted_at).total_seconds()
                if age_seconds >= 120:
                    try:
                        open_orders = self.trading_client.get_orders()
                        open_ids = {str(order.id) for order in open_orders}
                        if self.pending_order_id not in open_ids:
                            print(f"Poll: pending order {self.pending_order_id} is not open anymore (age={age_seconds:.0f}s); clearing pending state.")
                            self._clear_pending()
                            self._update_position_single()
                    except Exception as exc:
                        print(f"Poll open-orders check error: {exc}")


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
        self._refresh_daily_files()

        # Get the order ID from the event
        order_id = str(event_data.order.id)
        
        # Get event type to determine if this is a confirmation event
        event_dict = event_data.model_dump()  # Convert to dictionary
        event_name = self._normalize_event_name(event_dict.get("event", ""))
        
        # Check if the order ID is in the orders_list
        if order_id not in self.orders_list.keys():
            return  # Order not tracked, ignore
        
        # Import here to avoid circular imports
        from MachineTrader.helpers.utils import convert_to_nytzone
        
        # Parse event_dict
        event_dict = convert_to_nytzone(event_dict)
        time_stamp = format_timestamp_ny(event_dict.get("timestamp"))
        event_dict["timestamp"] = time_stamp
        orderinfo = event_dict["order"]
        # Remove the "order" key from the event_dict
        event_dict.pop("order", None)
        symbol = orderinfo["symbol"]
        event_dict.update(orderinfo)  # This adds order fields to event_dict
        time_now = format_timestamp_ny(None)

        # Process the event data based on the event type
        if event_in_group(event_name, "fill_progress"):
            order_type = orderinfo["order_type"]
            trade_side = orderinfo["side"]
            qty_filled = float(orderinfo["qty"])
            fill_price = float(orderinfo.get("filled_avg_price", 0))
            print(f"✅ Order {order_id} filled at {time_now} at price {fill_price}")
            print(f"💸 {time_stamp} Filled {order_type} {trade_side} order for {qty_filled} shares of {symbol} at {fill_price}")
            
            position_fill = event_dict.get("position_qty", 0)
            print(f"📊 Position from broker after the fill: {position_fill} shares of {symbol}")
            
            # Calculate realized P&L and update position tracking
            pnl_real = self.calc_realized_pnl(trade_side, qty_filled, fill_price, order_id)
            print(f"💰 Realized P&L from this trade: ${pnl_real:.2f}")
            
            # Append to CSV (write header only if file does not exist)
            if self.fills_file:
                event_frame = pd.DataFrame([event_dict])
                event_frame.to_csv(self.fills_file, mode="a", header=not os.path.exists(self.fills_file), index=False)
                print(f"📁 Fill appended to {self.fills_file}")
            
            # Note: Stream management is handled externally by calling code
            print(f"� Fill processed for order {order_id}. Stream continues for other pending orders.")
            
        elif event_in_group(event_name, "pending_submit"):
            print(f"📋 Event {event_name} received for order {order_id} at {time_now}")
            # Already added to orders_list list by submit_order(), so do nothing here
            pass # Do nothing for new/pending events
                    
        elif event_in_group(event_name, "cancel_persist"):
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
            
        else:
            print(f"❓ Unknown event: {event_name}")
            
        print(f"✅ Finished processing the {event_name} update for order {order_id} at {time_now}")

    # end handle_trade_event


    async def handle_trade_event_signed_queue(
        self,
        event_data,
        orders_list,
        queue_prices,
        pnl_real=0.0,
        order_filled_qty=None,
        fills_file=None,
        canceled_file=None,
    ):
        """
        Handle trade updates using signed-price inventory semantics.

        This helper is intended for strategies that keep local inventory as a
        queue of signed fill prices (negative buys, positive sells).
        """
        self._refresh_daily_files()

        if order_filled_qty is None:
            order_filled_qty = {}

        from MachineTrader.helpers import calc_pnls as _calc_pnls
        queue_prices[:] = _calc_pnls.normalize_signed_price_queue(queue_prices)

        def _position_shares_from_queue() -> int:
            return int(round(float(_calc_pnls.signed_queue_to_qty(queue_prices))))

        try:
            order_id = str(event_data.order.id)
        except Exception:
            return {
                "processed": False,
                "reason": "missing_order_id",
                "pnl_real": float(pnl_real or 0.0),
                "position_shares": _position_shares_from_queue(),
                "pending_orders": len(orders_list),
            }

        if order_id not in orders_list:
            return {
                "processed": False,
                "reason": "untracked_order",
                "order_id": order_id,
                "pnl_real": float(pnl_real or 0.0),
                "position_shares": _position_shares_from_queue(),
                "pending_orders": len(orders_list),
            }

        from MachineTrader.helpers.utils import convert_to_nytzone

        event_dict = event_data.model_dump()
        event_dict = convert_to_nytzone(event_dict)
        event_name = self._normalize_event_name(event_dict.get("event", ""))
        time_stamp = event_dict.get("timestamp")
        orderinfo = event_dict.get("order", {})

        event_dict.pop("order", None)
        event_dict.update(orderinfo)
        time_now = format_timestamp_ny(None)

        current_pnl_real = float(pnl_real or 0.0)

        if event_in_group(event_name, "fill_progress"):
            order_type = orderinfo.get("order_type")
            side_text = str(orderinfo.get("side", "")).lower()
            if "buy" in side_text:
                trade_side = "buy"
            elif "sell" in side_text:
                trade_side = "sell"
            else:
                trade_side = side_text

            total_filled = float(orderinfo.get("filled_qty", orderinfo.get("qty", 0)) or 0)
            prev_filled = float(order_filled_qty.get(order_id, 0.0) or 0.0)
            qty_filled = max(total_filled - prev_filled, 0.0)
            order_filled_qty[order_id] = total_filled

            if qty_filled <= 0:
                position_shares = _position_shares_from_queue()
                return {
                    "processed": True,
                    "event_name": event_name,
                    "order_id": order_id,
                    "pnl_real": current_pnl_real,
                    "position_shares": position_shares,
                    "pending_orders": len(orders_list),
                }

            fill_price = float(orderinfo.get("filled_avg_price", 0) or 0.0)
            print(f"✅ Order {order_id} filled at {time_now} at price {fill_price}")
            print(f"💸 {time_stamp} Filled {order_type} {trade_side} order for {qty_filled} shares of {orderinfo.get('symbol')} at {fill_price}")

            shares_delta = int(round(qty_filled))
            if shares_delta > 0 and trade_side in {"buy", "sell"}:
                updated_queue, pnl_real_delta = _calc_pnls.match_fill_lifo(
                    queue_prices,
                    side=trade_side,
                    fill_price=float(fill_price),
                    fill_qty=int(shares_delta),
                )
                queue_prices[:] = list(updated_queue)
                current_pnl_real += float(pnl_real_delta)

            if event_in_group(event_name, "fill"):
                orders_list.pop(order_id, None)
                order_filled_qty.pop(order_id, None)

            target_fills_file = fills_file or self.fills_file
            if target_fills_file:
                event_frame = pd.DataFrame([event_dict])
                event_frame.to_csv(target_fills_file, mode="a", header=not os.path.exists(target_fills_file), index=False)

        elif event_in_group(event_name, "cancel_terminal"):
            print(f"❌ Order {order_id} {event_name} at {time_now}")
            orders_list.pop(order_id, None)
            order_filled_qty.pop(order_id, None)

            target_canceled_file = canceled_file or self.canceled_file
            if target_canceled_file and event_in_group(event_name, "cancel_persist"):
                event_frame = pd.DataFrame([event_dict])
                event_frame.to_csv(target_canceled_file, mode="a", header=not os.path.exists(target_canceled_file), index=False)

        position_shares = _position_shares_from_queue()
        return {
            "processed": True,
            "event_name": event_name,
            "order_id": order_id,
            "pnl_real": current_pnl_real,
            "position_shares": position_shares,
            "pending_orders": len(orders_list),
        }

    # end handle_trade_event_signed_queue


# end class Trading



class AlpacAPI:
    """
    Alpaca API client class for API operations.
    
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
        self.orders_list = {}
        self.state_file = None
        self.submits_file = None
        self.persist_submits_log = False
        self.fills_file = None
        self.canceled_file = None
        self.error_file = None
        self.proxy_connected = False
        self.last_submit_rejection = None
        self.last_submit_attempt = None
        self.last_price = None
        self.last_bar = None
        self.current_price = None
        self.manual_reference_price = None
        self.manual_start_time = None
        self.manual_end_time = None
        self.open_price = None
        
        # Initialize rate limiting parameters
        self.enable_rate_limiting = enable_rate_limiting
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum seconds between requests
        
        # Set up logging
        self.logger = logging.getLogger(__name__)

    def _refresh_daily_files(self):
        self.state_file = FileMan.daily_path(self.state_file)
        self.fills_file = FileMan.daily_path(self.fills_file)
        self.canceled_file = FileMan.daily_path(self.canceled_file)
        self.submits_file = FileMan.daily_path(self.submits_file)
        self.error_file = FileMan.daily_path(self.error_file)


    def convert_bar(self, proxy_bar):
        """Convert a proxy stream bar payload into a bar-like object."""
        if not isinstance(proxy_bar, dict):
            return proxy_bar

        if proxy_bar.get("T") != "b":
            return None

        timestamp = coerce_market_datetime_ny(proxy_bar.get("t"), fallback_to_now=False)
        if timestamp is None:
            return None

        return SimpleNamespace(
            symbol=proxy_bar.get("S"),
            close=float(proxy_bar.get("c", 0.0)),
            vwap=float(proxy_bar.get("vw", proxy_bar.get("c", 0.0))),
            timestamp=timestamp,
            high=float(proxy_bar.get("h", proxy_bar.get("c", 0.0))),
            low=float(proxy_bar.get("l", proxy_bar.get("c", 0.0))),
            volume=float(proxy_bar.get("v", 0.0)),
        )


    def process_bar(self, event: dict):
        """Update the latest bar price state from a stream event."""
        event_type = str(event.get("T", event.get("type", ""))).strip().lower()
        if event_type not in {"b", "bar"}:
            return None

        event_close = event.get("c", event.get("close"))
        if event_close is None:
            return None

        bar = self.convert_bar(event)
        if bar is None:
            return None

        self.last_bar = bar
        self.last_price = float(event_close)
        self.current_price = self.last_price

        return self.last_price

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
        from MachineTrader.helpers.auth import AccountAuth

        auth = AccountAuth(env_file=env_file)
        trade_key, trade_secret, _, _ = auth.resolve_trade_credentials()
        self.credential_source = auth.credential_source

        if not trade_key:
            env_source = f"environment file {env_file}" if env_file else "environment variables"
            raise ValueError(f"Required trading credentials not found in {env_source}.")
        
        # Create clients with rate limiting if enabled
        if self.enable_rate_limiting:
            def _create_clients():
                if trade_secret:
                    self.trading_client = TradingClient(trade_key, trade_secret)
                    self.confirm_stream = TradingStream(trade_key, trade_secret)
                else:
                    self.trading_client = TradingClient(oauth_token=trade_key, paper=True)
                    self.confirm_stream = None
                return self.trading_client, self.confirm_stream
            
            try:
                trading_client, confirm_stream = self.execute_with_retry_sync(_create_clients)
                print(f"✅ SDK clients created successfully with rate limiting")
            except self.RateLimitExceededError:
                print("❌ Rate limit exceeded when creating clients. Please wait and try again.")
                raise
        else:
            if trade_secret:
                self.trading_client = TradingClient(trade_key, trade_secret)
                self.confirm_stream = TradingStream(trade_key, trade_secret)
            else:
                self.trading_client = TradingClient(oauth_token=trade_key, paper=True)
                self.confirm_stream = None
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


    def create_data_stream_client(self, env_file=None, DATA_KEY="DATA_KEY", DATA_SECRET="DATA_SECRET", feed=None):
        """
        Create and configure SDK live data stream client for real-time bar access.

        Args:
            env_file (str): Path to environment file. Defaults to '.env'.
            DATA_KEY (str): API key name for data access. If None, reads from environment.
            DATA_SECRET (str): API secret name for data access. If None, reads from environment.
            feed: Optional Alpaca data feed passed to StockDataStream.

        Returns:
            StockDataStream: Configured live data stream client instance.
        """
        if env_file is not None:
            load_dotenv(env_file)
            print(f"📄 Loading environment variables from: {env_file}")
        else:
            load_dotenv()
            print("📄 Loading environment variables from default .env file or system environment")

        try:
            DATA_KEY = os.getenv(DATA_KEY)
            DATA_SECRET = os.getenv(DATA_SECRET)
            if not DATA_KEY or not DATA_SECRET:
                raise ValueError(
                    f"API credentials not found. Check {env_file} or provide DATA_KEY and DATA_SECRET parameters."
                )

            if feed is None:
                self.data_stream_client = StockDataStream(DATA_KEY, DATA_SECRET)
            else:
                self.data_stream_client = StockDataStream(DATA_KEY, DATA_SECRET, feed=feed)

            logging.info("Data stream client created successfully")
            return self.data_stream_client

        except Exception as e:
            logging.error(f"Failed to create data stream client: {str(e)}")
            raise ValueError(f"Data stream client creation failed: {str(e)}")

    # end create_data_stream_client


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


    async def run_direct_stream(self, symbol, handle_bar_event):
        """Subscribe to live bars for a symbol and run the direct data stream."""
        if self.data_client is None:
            raise ValueError("Data client not initialized. Call create_data_stream_client() first.")

        self.proxy_connected = False
        self.data_client.subscribe_bars(handle_bar_event, symbol)
        await self.data_client._run_forever()


    async def connect_proxy_stream(
        self,
        symbol,
        handle_bar_event,
        data_proxy_url=None,
        reconnect_delay=5,
        max_proxy_retries=3,
        on_fallback_direct=None,
    ):
        """Read bars from the local proxy and fall back to the direct stream if needed."""
        import json
        import websockets

        data_proxy_url = data_proxy_url or os.getenv("DATA_PROXY_URL", "ws://localhost:8765")

        retry_count = 0

        try:
            while retry_count < max_proxy_retries:
                try:
                    async with websockets.connect(data_proxy_url) as ws:
                        print(f"Connected to WebSocket proxy at {data_proxy_url}")
                        self.proxy_connected = True
                        retry_count = 0
                        async for message in ws:
                            try:
                                data = json.loads(message)
                                events = data if isinstance(data, list) else [data]
                                for event in events:
                                    await handle_bar_event(event)
                            except Exception as e:
                                print(f"Error processing proxy message: {e}")
                except Exception as e:
                    self.proxy_connected = False
                    retry_count += 1
                    print(f"Proxy WebSocket error: {e}. Reconnecting in {reconnect_delay} seconds...")
                    await asyncio.sleep(reconnect_delay)
        finally:
            self.proxy_connected = False

        print("Proxy stream unavailable after retries. Falling back to Alpaca direct stream.")
        if on_fallback_direct is not None:
            on_fallback_direct()
        await self.run_direct_stream(symbol, handle_bar_event)


    def _get_open_position(self, symbol):
        """Return the broker position for a symbol, or None if none exists."""
        if self.trading_client is None:
            raise ValueError("Trading client not initialized. Call create_trade_clients() first.")

        try:
            return self.trading_client.get_open_position(symbol)
        except Exception:
            return None


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
        position = self._get_open_position(symbol)
        if position:
            print(f"({self.BROKER_NAME}) Open position for {symbol}: {position.qty} shares at {position.avg_entry_price}")
        else:
            print(f"({self.BROKER_NAME}) No open position for {symbol}.")
        return position


    def get_available_shares(self, symbol):
        """Return the broker-reported available shares for a symbol."""
        position = self._get_open_position(symbol)
        if position is None:
            return 0.0

        return float(position.qty_available)


    def get_position_and_available_shares(self, symbol, shares_per_trade=1):
        """Return the broker position, available shares, and broker quantity with strategy-friendly defaults."""
        position = self.get_position(symbol)
        if position is None:
            return None, float(shares_per_trade), 0.0

        return position, float(position.qty_available), float(position.qty)

    @staticmethod
    def _normalize_side_text(side) -> str:
        text = str(side or "").strip().lower()
        if "." in text:
            text = text.rsplit(".", 1)[-1]
        return text

    @classmethod
    def resolve_submittable_qty(
        cls,
        requested_qty,
        side,
        *,
        available_qty: float | None = None,
        broker_qty: float = 0.0,
        force_cap_to_available: bool = False,
    ) -> float:
        requested = abs(float(requested_qty or 0.0))
        if requested <= 0.0:
            return 0.0

        try:
            broker_qty_value = float(broker_qty or 0.0)
        except Exception:
            broker_qty_value = 0.0

        if available_qty is None:
            return requested

        try:
            available_value = float(available_qty or 0.0)
        except Exception:
            available_value = 0.0

        side_text = cls._normalize_side_text(side)
        should_cap_to_available = bool(force_cap_to_available)
        if side_text == "sell" and broker_qty_value > 0.0:
            should_cap_to_available = True
        elif side_text == "buy" and broker_qty_value < 0.0:
            should_cap_to_available = True

        if not should_cap_to_available:
            return requested

        available_magnitude = abs(float(available_value))
        if available_magnitude <= 0.0:
            return 0.0
        return min(requested, available_magnitude)


    def get_shares_to_trade(self, symbol, shares_per_trade, side):
        """Return the broker available shares and the capped trade quantity for a side."""
        position = self._get_open_position(symbol)
        shares_available = 0.0
        broker_qty = 0.0
        if position is not None:
            try:
                shares_available = float(position.qty_available)
            except Exception:
                shares_available = 0.0
            try:
                broker_qty = float(position.qty)
            except Exception:
                broker_qty = 0.0

        shares_to_trade = self.resolve_submittable_qty(
            shares_per_trade,
            side,
            available_qty=shares_available,
            broker_qty=broker_qty,
        )

        return shares_available, shares_to_trade


    def _is_market_open_now(self):
        """Best-effort regular-session check using NY wall clock (no broker API call)."""
        now_ny = datetime.now(ZoneInfo("America/New_York"))
        if now_ny.weekday() >= 5:
            return False
        now_time = dtime(now_ny.hour, now_ny.minute, now_ny.second)
        return dtime(9, 30) <= now_time < dtime(16, 0)

    @staticmethod
    def _extract_available_qty_from_rejection(error_text: str) -> float:
        from MachineTrader.helpers.broker_orders import extract_available_qty_from_rejection

        return float(extract_available_qty_from_rejection(error_text))

    @classmethod
    def _parse_submit_rejection(cls, symbol: str, side: Any, error: Exception) -> dict[str, Any]:
        from MachineTrader.helpers.broker_orders import parse_submit_rejection

        return dict(parse_submit_rejection(symbol, side, error))


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

        self._refresh_daily_files()
        if canceled_file is None:
            canceled_file = self.canceled_file

        if orders_list is None:
            request_params = GetOrdersRequest(
                status=QueryOrderStatus.OPEN,
                symbols=[symbol],
            )
            orders_list = self.trading_client.get_orders(filter=request_params)
            print(f"Found {len(orders_list)} open orders for {symbol}.")
            for open_order in list(orders_list):
                order_id = open_order if isinstance(open_order, str) else str(open_order.id)
                try:
                    self.trading_client.cancel_order_by_id(order_id=order_id)
                    order_status = self.trading_client.get_order_by_id(order_id=order_id)
                    order_record = order_status.model_dump()
                    FileMan.append_row_to_csv(self.state_file, order_record)
                    if self.persist_submits_log and self.submits_file:
                        FileMan.append_row_to_csv(self.submits_file, order_record)
                    FileMan.append_row_to_csv(canceled_file, order_record)
                    print(f"Cancelled order: {order_id} for {symbol}")
                    orders_list.remove(open_order)
                    print(f"Removed order ID {order_id} from open orders list. Remaining number of open orders: {len(orders_list)}")
                except Exception as e:
                    print(f"Error canceling order {order_id} for {symbol}: {e}")
            if canceled_file is not None:
                print(f"Canceled orders saved to {canceled_file}")
            else:
                print("Canceled orders not saved (canceled_file=None)")
            return orders_list

        if not orders_list:
            print(f"No open orders found for {symbol}.")
            return []

        print(f"Found {len(orders_list)} open orders for {symbol}.")
        for order_id in list(orders_list):
            if not isinstance(order_id, str):
                order_id = str(order_id.id)
            try:
                self.trading_client.cancel_order_by_id(order_id=order_id)
                order_status = self.trading_client.get_order_by_id(order_id=order_id)
                order_record = order_status.model_dump()
                FileMan.append_row_to_csv(self.state_file, order_record)
                if self.persist_submits_log and self.submits_file:
                    FileMan.append_row_to_csv(self.submits_file, order_record)
                FileMan.append_row_to_csv(canceled_file, order_record)
                orders_list.remove(order_id)
                print(f"Cancelled order: {order_id} for {symbol}")
                print(f"Removed order ID {order_id} from open orders list. Remaining number of open orders: {len(orders_list)}")
            except Exception as e:
                print(f"Error canceling order {order_id} for {symbol}: {e}")
                orders_list.remove(order_id)
                print(f"Removed order ID {order_id} from the open orders list after the error. Remaining number of open orders: {len(orders_list)}")

        if canceled_file is not None:
            print(f"Canceled orders saved to {canceled_file}")
        else:
            print("Canceled orders not saved (canceled_file=None)")
        return orders_list


    def get_open_orders(self, symbol=None):
        """Return the current open orders, optionally filtered to a symbol."""
        if self.trading_client is None:
            raise ValueError("Trading client not initialized. Call create_trade_clients() first.")

        request_params = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        if symbol is not None:
            request_params.symbols = [symbol]

        return self.trading_client.get_orders(filter=request_params)


    def cancel_all_orders(self, canceled_file=None):
        """Cancel every open order and optionally persist the cancelled orders to CSV."""
        if self.trading_client is None:
            raise ValueError("Trading client not initialized. Call create_trade_clients() first.")

        self._refresh_daily_files()
        if canceled_file is None:
            canceled_file = self.canceled_file

        open_orders = self.get_open_orders()
        if not open_orders:
            print("No open orders found.")
            return []

        print(f"Found {len(open_orders)} open orders.")
        canceled_orders = []
        for open_order in open_orders:
            order_id = str(open_order.id)
            try:
                self.trading_client.cancel_order_by_id(order_id=order_id)
                order_status = self.trading_client.get_order_by_id(order_id=order_id)
                order_record = order_status.model_dump()
                canceled_orders.append(order_status)
                FileMan.append_row_to_csv(self.state_file, order_record)
                if self.persist_submits_log and self.submits_file:
                    FileMan.append_row_to_csv(self.submits_file, order_record)
                FileMan.append_row_to_csv(canceled_file, order_record)
                print(f"Cancelled order: {order_id}")
            except Exception as e:
                print(f"Error canceling order {order_id}: {e}")

        if canceled_file is not None:
            print(f"Canceled orders saved to {canceled_file}")
        else:
            print("Canceled orders not saved (canceled_file=None)")

        return canceled_orders

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

        self._refresh_daily_files()
        self.last_submit_rejection = None
        self.last_submit_attempt = None

        market_is_open = self._is_market_open_now()
        shares_owned = 0.0
        if market_is_open:
            position = self._get_open_position(symbol)
            if position is not None:
                try:
                    shares_owned = float(position.qty)
                except Exception:
                    shares_owned = 0.0
            shares_available, shares_to_trade = self.get_shares_to_trade(symbol, shares_per_trade, side)
            print(f"Shares currently owned by the strategy for {symbol}: {shares_owned}")
            print(f"Shares available offered to trade by Alpaca for {symbol}: {shares_available}")
            print(f"Submitted shares for {symbol}: {shares_to_trade}")
        else:
            shares_available = 0.0
            shares_to_trade = float(shares_per_trade or 0.0)
            print(
                f"Market is closed for {symbol}; skipping available-share check and submitting requested shares={shares_to_trade}"
            )

        # Surfaces the available-vs-requested gap so callers can blotter silent submit drops.
        self.last_submit_attempt = {
            "symbol": str(symbol or "").strip().upper(),
            "side": self._normalize_side_text(side),
            "order_type": str(type or "").strip().lower(),
            "limit_price": limit_price,
            "requested_qty": abs(float(shares_per_trade or 0.0)),
            "shares_available": float(shares_available),
            "shares_to_trade": float(shares_to_trade),
            "shares_owned": float(shares_owned),
            "market_is_open": bool(market_is_open),
            "reason": "",
        }

        if shares_to_trade <= 0:
            self.last_submit_attempt["reason"] = "no shares available"
            print(f"No shares can be submitted for {symbol} with side={side}. Exiting.")
            return None
        
        time_now = format_timestamp_ny(None)

        # Define the order parameters based on the order type
        if type == "market":
            # Create market order parameters
            print(f"Submitting a {type} {side} order for {shares_to_trade} shares of {symbol}")
            order_params = MarketOrderRequest(
                symbol = symbol,
                qty = shares_to_trade,
                side = side,
                type = type,
                time_in_force = TimeInForce.DAY
            )
        elif type == "limit":
            # Create limit order parameters
            print(f"Submitting a {type} {side} order for {shares_to_trade} shares of {symbol} at {limit_price}")
            order_params = LimitOrderRequest(
                symbol = symbol,
                qty = shares_to_trade,
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
                self.last_submit_attempt["reason"] = "broker returned no order response"
                print(f"❌ Order submission failed: order_response is None")
                return None
            
            print(f"✅ Order submitted: Symbol={order_response.symbol}, Type={order_response.type}, Side={order_response.side}, Qty={order_response.qty}")
            self.last_submit_rejection = None
            
            # Add order to tracking list with limit price
            order_id = str(order_response.id)
            self.orders_list[order_id] = limit_price
            print(f"📝 Added order {order_id} to tracking list with price {limit_price}")
            
            # Save the submit information to a CSV file
            order_frame = order_response.model_dump()  # or order_response._raw for some SDKs
            order_frame = pd.DataFrame([order_frame])
            # Append to CSV only when a submit log path is configured.
            if self.persist_submits_log and self.submits_file:
                order_frame.to_csv(self.submits_file, mode="a", header=not os.path.exists(self.submits_file), index=False)
                print(f"📁 Order appended to {self.submits_file}")
            return order_response
            
        except self.RateLimitExceededError as e:
            self.last_submit_rejection = self._parse_submit_rejection(symbol, side, e)
            self.last_submit_attempt["reason"] = f"rate limit exceeded: {e}"
            print(f"❌ Rate limit exceeded when submitting order: {e}")
            # Save rate limit error to CSV
            error_msg = pd.DataFrame([{
                "error": "rate_limit", 
                "timestamp": time_now, 
                "symbol": symbol, 
                "side": side, 
                "message": str(e)
            }])
            if self.error_file:
                error_msg.to_csv(self.error_file, mode="a", header=not os.path.exists(self.error_file), index=False)
            return None
            
        except Exception as e:
            self.last_submit_rejection = self._parse_submit_rejection(symbol, side, e)
            self.last_submit_attempt["reason"] = f"broker rejected: {e}"
            # Convert error to string and save to CSV
            error_msg = pd.DataFrame([{
                "error": "submission_failed", 
                "timestamp": time_now, 
                "symbol": symbol, 
                "side": side, 
                "message": str(e)
            }])
            if self.error_file:
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
        data_proxy_url = getattr(self, "data_proxy_url", None) or os.getenv("DATA_PROXY_URL", "ws://localhost:8765")
        reconnect_delay = 5
        while True:
            try:
                async with websockets.connect(data_proxy_url) as ws:
                    print(f"Connected to WebSocket proxy at {data_proxy_url}")
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
                                        # Call the trading strategy function through execute_strategy
                                        await strategy.execute_strategy(bar_object)
                            elif isinstance(data, dict):
                                if data.get("T") == "b" and data.get("S") == symbol:
                                    # Create a Bar object directly from the data
                                    bar_object = Bar(data)
                                    # Call the trading strategy function through execute_strategy
                                    await strategy.execute_strategy(bar_object)
                        except Exception as e:
                            print(f"Error processing message: {e}")
            except Exception as e:
                print(f"WebSocket error: {e}. Reconnecting in {reconnect_delay} seconds...")
                time.sleep(reconnect_delay)

    # end stream_bars

# end class AlpacAPI

