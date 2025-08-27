## Utility functions for data processing, calculating EMA prices, submitting trades, and managing orders.


import os
import sys
import io
import linecache
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date, datetime
from zoneinfo import ZoneInfo
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest, MarketOrderRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from dotenv import load_dotenv
# Package for download
import requests

# Broker name
BROKER_NAME = "Alpaca"

## Lag a numpy array and pad with zeros
def lagit(xs, n):
    e = np.empty_like(xs)
    if n >= 0:
        e[:n] = 0
        e[n:] = xs[:-n]
    else:
        e[n:] = 0
        e[:n] = xs[-n:]
    return e
# end lagit


## Calculate the rolling sum - output same length as input
# https://stackoverflow.com/questions/30399534/shift-elements-in-a-numpy-array
def calc_rollsum(a, lb=3):
    ret = np.cumsum(a)
    ret[lb:] = ret[lb:] - ret[:-lb]
    return ret
# end calc_rollsum



## Calculate the Sharpe ratio
def calc_sharpe(retsp, raterf=0.0):
    # Calculate mean returns
    meanret = retsp.mean()
    # Calculate standard deviation
    stdev = retsp.std()
    # Calculate day Sharpe ratio
    sharper = (meanret-raterf)/stdev
    # Annualize Sharpe ratio
    sharper = math.sqrt(252)*sharper
    return sharper
# end calc_sharpe



## Load OHLC data from CSV file
# For example:
# ohlc = read_csv('/Users/jerzy/Develop/data/BTC_minute.csv')

def read_csv(filename):
    print('Loading data from: ', filename)
    ohlc = pd.read_csv(filename)
    ohlc.set_index('Date', inplace=True)
    ohlc.index = pd.to_datetime(ohlc.index, utc=True)
    return ohlc
# end read_csv


## Download OHLC time series from Polygon

# Load the API keys from /Users/jerzy/Develop/Python/.env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Get the Polygon key
POLYGON_KEY = os.getenv("POLYGON_KEY")


## Define exception handler function
def CatchException():
    exc_type, exc_obj, tb = sys.exc_info()
    f_err = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f_err.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f_err.f_globals)
    # print('EXCEPTION IN ({}, LINE {} '{}'): {}'.format(filename, lineno, line.strip(), exc_obj))


## get_symbol() downloads data from Polygon and returns an OHLC data frame
def get_symbol(symbol, startd, endd, range='day', polygon_key=POLYGON_KEY):
    print('Downloading', symbol)
    getstring = f'https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/{range}/{startd}/{endd}?adjusted=true&sort=asc&limit=50000&apiKey={polygon_key}'
    # Download the data from url
    response = requests.get(getstring)
    # Coerce url response to json
    jayson = response.json()
    try:
        bardata      = jayson['results']
        ticker       = jayson['ticker']
        queryCount   = jayson['queryCount']
        resultsCount = jayson['resultsCount']
        adjusted     = jayson['adjusted']
    except KeyError:
        pass
    except NameError:
        pass
    except:
        queryCount = 0
        CatchException()
        pass
    # Coerce json to data frame to OHLC data
    if queryCount > 1:
        ohlc = pd.DataFrame(bardata)
        # Create Date column equal to datetime - Polygon timestamp is in milliseconds
        ohlc['Date'] = pd.to_datetime(ohlc.t, unit='ms', utc=True)
        # Coerce column of type datetime to type date
        if (range == 'day'):
          ohlc.Date = ohlc.Date.dt.date
        # Convert Date column to ohlc index
        ohlc.set_index('Date', inplace=True)
        # Change time zone - doesn't work as expected
        # ohlc = ohlc.tz_localize('US/Eastern')
        # Drop columns
        ohlc.drop(columns=['n'], inplace=True)
        # Rename and rearrange columns
        ohlc.rename(columns={'t': 'Seconds', 'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume', 'vw': 'VWAP'}, inplace=True)
        ohlc = ohlc[['Seconds', 'Open', 'High', 'Low', 'Close', 'Volume', 'VWAP']]
        # Convert from milliseconds to seconds
        ohlc.Seconds = ohlc.Seconds / 1000
    # Return OHLC data
    return ohlc
# end get_symbol


# Get the open position for the symbol
def get_position(trading_client, symbol):
    position = None  # Initialize position variable
    # Get the open position for the symbol
    try:
        position = trading_client.get_open_position(symbol)
    except Exception as e:
        pass # Do nothing
        # print(f"Error getting open position for {symbol}: {e}")
    if position:
        print(f"({BROKER_NAME}) Open position for {symbol}: {position.qty} shares at {position.avg_entry_price}")
    else:
        print(f"({BROKER_NAME}) No open position for {symbol}.")
    return position
# End of get_position


# Cancel all open orders in the list open_orders for the symbol
def cancel_orders(trading_client, symbol, canceled_file, open_orders=None):

    # Case when open_orders is None
    # Cancel all the open orders for the symbol because open_orders is None
    if open_orders is None:
        # Get all the open orders for the symbol
        request_params = GetOrdersRequest(
                            status=QueryOrderStatus.OPEN,
                            symbols=[symbol],
                        )
        open_orders = trading_client.get_orders(filter=request_params)
        # Cancel the open orders one at a time
        print(f"Found {len(open_orders)} open orders for {symbol}.")
        for open_order in open_orders:
            # If it's not a string, then extract the order ID as a string
            order_id = open_order
            if not isinstance(order_id, str):
                order_id = str(order_id.id)
            # print(f"Canceling order: {order_id} for {symbol}")
            try:
                # Cancel the order
                trading_client.cancel_order_by_id(order_id=order_id)
                # Get the canceled order status
                order_status = trading_client.get_order_by_id(order_id=order_id)
                # Append the canceled order status to CSV file (write header only if file does not exist)
                canceled_frame = pd.DataFrame([order_status.model_dump()])
                canceled_frame.to_csv(canceled_file, mode="a", header=not os.path.exists(canceled_file), index=False)
                print(f"Cancelled order: {order_id} for {symbol}")
                # Remove the canceled order ID from the open orders list
                open_orders.remove(open_order)
                print(f"Removed order ID {order_id} from open orders list. Remaining number of open orders: {len(open_orders)}")
            except Exception as e:
                print(f"Error canceling order {order_id} for {symbol}: {e}")
        print(f"Canceled orders saved to {canceled_file}")
        return open_orders

    # Case when open_orders is not None
    # Cancel the open orders from the list open_orders one at a time
    if not open_orders:
        print(f"No open orders found for {symbol}.")
        return [] # Return an empty list if no open orders
    else:
        print(f"Found {len(open_orders)} open orders for {symbol}.")
        for order_id in open_orders:
            # If it's not a string, then extract the order ID as a string
            if not isinstance(order_id, str):
                order_id = str(order_id.id)
            # print(f"Canceling order: {order_id} for {symbol}")
            try:
                # Remove the canceled order ID from the open orders list
                # Cancel the order
                trading_client.cancel_order_by_id(order_id=order_id)
                # Get the canceled order status
                order_status = trading_client.get_order_by_id(order_id=order_id)
                # Append the canceled order status to CSV file (write header only if file does not exist)
                canceled_frame = pd.DataFrame([order_status.model_dump()])
                canceled_frame.to_csv(canceled_file, mode="a", header=not os.path.exists(canceled_file), index=False)
                # Remove the canceled order ID from the open orders list
                open_orders.remove(order_id)
                print(f"Cancelled order: {order_id} for {symbol}")
                print(f"Removed order ID {order_id} from open orders list. Remaining number of open orders: {len(open_orders)}")
            except Exception as e:
                print(f"Error canceling order {order_id} for {symbol}: {e}")
        print(f"Canceled orders saved to {canceled_file}")
        return open_orders

# End of cancel_orders



# The function submit_order submits a trade order using the Alpaca TradingClient
def submit_order(trading_client, symbol, shares_per_trade, side, type, limit_price, submits_file, error_file):

    tzone = ZoneInfo("America/New_York")
    time_now = datetime.now(tzone)

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

    # Submit the order
    # Print the order ID and status if successful, or the error if failed
    try:
        order_response = trading_client.submit_order(order_data = order_params)
        print(f"Order submitted for: Symbol={order_response.symbol}, Type={order_response.type}, Side={order_response.side}, shares_per_trade={order_response.qty}")
        # Save the submit information to a CSV file
        order_frame = order_response.model_dump()  # or order_response._raw for some SDKs
        order_frame = pd.DataFrame([order_frame])
        # Append to CSV (write header only if file does not exist)
        order_frame.to_csv(submits_file, mode="a", header=not os.path.exists(submits_file), index=False)
        print(f"Order appended to {submits_file}")
        return order_response
    except Exception as e:
        # Convert error to string and save to CSV
        error_msg = pd.DataFrame([{"error": "error", "timestamp: ": time_now, "symbol: ": symbol, "side: ": side, "msg: ": str(e)}])
        error_msg.to_csv(error_file, mode="a", header=not os.path.exists(error_file), index=False)
        print(f"Trade order rejected: {e}")
        print(f"Order submission failed: {e}")
        return None

# End of submit_order



# Plot function to plot the EMA price and Bollinger Bands
def plot_ema(price_frame):

    global symbol, alpha_param, date_pretty, bollinger_width
    # Convert the timestamp to datetime
    price_frame["timestamp"] = pd.to_datetime(price_frame["timestamp"])
    # Add upper and lower Bollinger Bands to the price frame
    price_frame["upper_band"] = price_frame["ema_price"] + bollinger_width * price_frame["volatility"]
    price_frame["lower_band"] = price_frame["ema_price"] - bollinger_width * price_frame["volatility"]
    
    # Plot the EMA price and the Bollinger Bands
    plt.figure(figsize=(20, 12))
    plt.plot(price_frame["timestamp"], price_frame["price"], label="Price", color="blue")
    plt.plot(price_frame["timestamp"], price_frame["ema_price"], label="EMA Price", color="red")
    plt.plot(price_frame["timestamp"], price_frame["upper_band"], label=f"Upper + {bollinger_width} STDV", color="orange", linestyle='--')
    plt.plot(price_frame["timestamp"], price_frame["lower_band"], label=f"Lower - {bollinger_width} STDV", color="orange", linestyle='--')
    plt.title(f"{symbol} EMA Prices and Bollinger Bands with α = {alpha_param} / {date_pretty}", fontsize=20)
    plt.xlabel("Time", fontsize=16)
    plt.ylabel("Price", fontsize=16)
    # plt.xticks(fontsize=10) # For x-axis tick labels
    # plt.yticks(fontsize=10) # For y-axis tick labels
    # Change the font size of the x and y axis labels
    plt.tick_params(axis="both", which="major", labelsize=14)
    plt.legend(fontsize=16) # Add legend
    # Adjust layout
    plt.tight_layout()

    # Save the plot to a file
    plt.savefig(plot_file)
    plt.close()  # Close the plot to free memory
    print(f"Plot saved to {plot_file}")



# --------- Calculate the total stock position and the unrealized P&L --------

# Calculate the unrealized P&L and the stock positions
def calc_unrealized_pnl(position_list, current_price):
    """
    The position_list is a list of prices paid or received for each stock position.
    Negative prices indicate long positions, and positive prices indicate short positions.
    Because when we buy a stock we pay for it, which is a negative cash flow, and when we sell it, we receive the market price, which is a positive cash flow.
    """

    if not position_list:
        position_shares = 0
        unrealized_pnl = 0.0
    else:
        # Calculate the number of shares owned
        num_shares = len(position_list)
        # Calculate the amount of shares owned (positive for long positions, negative for short positions)
        position_shares = -math.copysign(1, position_list[0]) * num_shares
        cost_basis = sum(position_list)  # Calculate the total cost basis
        # Calculate the unrealized P&L
        unrealized_pnl = (cost_basis + position_shares * current_price)

    return position_shares, unrealized_pnl

# End of calc_unrealized_pnl



# --------- EMA class for calculating the Exponential Moving Average --------

"""
EMACalculator: Calculate the Exponential Moving Average EMA with persistent state.

Methods:
    calc_ema(current_price, alpha): Calculate and update EMA
    calc_zscore(current_price, alpha, vol_floor): Calculate z-score with persistent state
    calc_zscorew(current_price, alpha, volume, vol_floor): Calculate z-score with EMA weighted by volumes
    reset(): Reset the EMA state

Args:
    current_price (float): The latest price value
    alpha (float): Smoothing factor (0 < alpha <= 1)
    volume (float): Trading volume for the current price
    vol_floor (float): Minimum volatility to avoid division by zero

Returns:
    float: Updated EMA value

Updating formulas:
EMA = α × EMA + (1-α) × current_price
Weighted EMA: EMAw = α × EMAw + (1-α) × volume × current_price
EMA volume: EMAvolume = α × EMAvolume + (1-α) × volume
EMA scaled: EMA = EMAw / EMAvolume

"""


class EMACalculator:

    def __init__(self):
        self.ema_price = None
        self.alpha1 = None
        self.price_var = None
        self.alpha_squared = None
        self.alpha2 = None
    
    def reset(self):
        """Reset the EMA state"""
        self.ema_price = None
        self.alpha1 = None
        self.price_var = None
        self.alpha_squared = None
        self.alpha2 = None


    """
    Calculate the EMA price using a persistent state.
    Returns: (ema_price)
    """
    def calc_ema(self, current_price, alpha):

        if self.ema_price is None:
            # Initialize EMA with first price
            self.ema_price = current_price
            self.alpha1 = 1 - alpha  # Store for efficiency
        else:
            # Update the EMA: EMA = alpha * previous_EMA + (1 - alpha) * current_price
            self.ema_price = alpha * self.ema_price + self.alpha1 * current_price
        
        return self.ema_price

    # end of calc_ema method


    """
    Calculate the Z-score from the EMA price and variance.
    Returns: (zscore, ema_price, price_vol)
    """
    def calc_zscore(self, current_price, alpha, vol_floor=0.01):

        if self.ema_price is None:
            # Initialize on first call
            self.ema_price = current_price  # Start with current price
            self.price_var = vol_floor  # Start with floor variance
            self.alpha1 = 1 - alpha
            self.alpha_squared = alpha * alpha
            self.alpha2 = 1 - self.alpha_squared
            # First call returns zero z-score
            return 0.0, self.ema_price, vol_floor

        else:
            # Calculate the price deviation from the current EMA
            price_deviation = current_price - self.ema_price
            
            # Calculate the volatility as the square root of variance with vol_floor
            price_vol = max(self.price_var ** 0.5, vol_floor)
            
            # Calculate the Z-score
            zscore = price_deviation / price_vol

            # Update the EMA variance
            self.price_var = self.alpha_squared * self.price_var + self.alpha2 * (price_deviation * price_deviation)

            # Update the EMA price
            self.ema_price = alpha * self.ema_price + self.alpha1 * current_price
            
            return zscore, self.ema_price, price_vol

    # end of calc_zscore method


    """
    Calculate the Z-score from the EMA price and variance weighted by the trading volumes.
    Returns: (zscore, ema_price, price_vol)
    """
    def calc_zscorew(self, current_price, volume, alpha, vol_floor=0.01):

        if self.ema_price is None:
            # Initialize on first call
            self.ema_price = volume * current_price  # Start with current price times volume
            self.price_var = volume * vol_floor * vol_floor  # Start with floor variance times volume
            self.alpha1 = 1 - alpha
            self.alpha_squared = alpha * alpha
            self.alpha2 = 1 - self.alpha_squared
            self.volume = volume  # Initialize the volume to avoid division by zero
            # First call returns zero z-score
            return 0.0, self.ema_price / self.volume, vol_floor

        else:
            # Calculate the price deviation from the current EMA
            price_deviation = current_price - self.ema_price / self.volume

            # Calculate the volatility as the square root of variance with vol_floor
            price_vol = max((self.price_var / self.volume) ** 0.5, vol_floor)  # Normalize by volume

            # Calculate the Z-score
            zscore = price_deviation / price_vol

            # Update the EMA volume
            self.volume = alpha * self.volume + self.alpha1 * volume

            # Update the EMA variance
            self.price_var = self.alpha_squared * self.price_var + self.alpha2 * volume * (price_deviation * price_deviation)

            # Update the EMA price
            self.ema_price = alpha * self.ema_price + self.alpha1 * volume * current_price
            ema_price = self.ema_price / self.volume  # Normalize by volume

            return zscore, ema_price, price_vol

    # end of calc_zscorew method


# end of EMACalculator class



# Convert all the nested datetime objects to NY timezone
def convert_to_nytzone(obj):

    tzone = ZoneInfo("America/New_York")
    if isinstance(obj, dict):
        return {k: convert_to_nytzone(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_nytzone(item) for item in obj]
    elif isinstance(obj, datetime):
        # Convert to NY timezone
        if obj.tzinfo is None:
            # If no timezone info, assume UTC
            obj = obj.replace(tzinfo=ZoneInfo("UTC"))
        return obj.astimezone(tzone)
    elif isinstance(obj, str):
        # Try to parse string as datetime if it looks like ISO format
        try:
            if 'T' in obj and ('Z' in obj or '+' in obj or obj.endswith('00')):
                dt = datetime.fromisoformat(obj.replace('Z', '+00:00'))
                return dt.astimezone(tzone).strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
        return obj
    else:
        return obj
# End of convert_to_nytzone function


# Disconnect any existing data_client websocket connections
# Run the function disconnect_data_client before subscribing to the price bars
def disconnect_data_client():
    try:
        # Check if stream client exists and has an active connection
        if hasattr(data_client, '_ws') and data_client._ws:
            if hasattr(data_client._ws, 'is_running') and data_client._ws.is_running:
                print("Disconnecting existing websocket connections...")
                data_client.stop()
                data_client._ws = None
                time.sleep(1)  # Give time for connection to fully close
                print("Successfully disconnected existing websockets")
            else:
                print("No active websocket connection found")
    except Exception as e:
        print(f"Error disconnecting websockets: {e}")
        # Ensure the websocket is cleared even if there's an error
        if hasattr(data_client, '_ws'):
            data_client._ws = None

# End of disconnect_data_client function



### Handle Ctrl-C interrupt

# Stop the stream when the user presses Ctrl-C
def ctrlc_handler(websocket):

    import signal
    def signal_handler(sig, frame):
        # Handle Ctrl-C (SIGINT) gracefully
        print("\n\nCtrl-C pressed! Exiting...")
        # Stop the stream client before exiting
        try:
            websocket.stop()
            print("Stream stopped by user.")
        except:
            pass
        sys.exit(0)

    # Set up signal handler for Ctrl-C
    print("Press Ctrl-C to stop the stream... \n")
    signal.signal(signal.SIGINT, signal_handler)




