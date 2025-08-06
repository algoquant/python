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
        print(f"Open position for {symbol}: {position.qty} shares at {position.avg_entry_price}")
    else:
        print(f"No open position for {symbol}.")
    return position
# End of get_position


# Cancel all open orders for the symbol
def cancel_orders(trading_client, symbol, canceled_file):

    # Get all open orders for the symbol
    request_params = GetOrdersRequest(
                        status=QueryOrderStatus.OPEN,
                        symbols=[symbol],
                    )
    open_orders = trading_client.get_orders(filter=request_params)

    # Cancel the open orders one at a time
    if not open_orders:
        print(f"No open orders found for {symbol}.")
    else:
        print(f"Found {len(open_orders)} open orders for {symbol}.")
        for order in open_orders:
            order_id = str(order.id)
            # print(f"Cancelling order: {order_id} for {symbol}")
            try:
                # Cancel the order
                trading_client.cancel_order_by_id(order_id=order_id)
                # Get the canceled order details
                order = trading_client.get_order_by_id(order_id=order_id)
                # Append the canceled order to CSV file (write header only if file does not exist)
                canceled_frame = pd.DataFrame([order.model_dump()])
                canceled_frame.to_csv(canceled_file, mode="a", header=not os.path.exists(canceled_file), index=False)
                print(f"Cancelled order: {order_id} for {symbol}")
            except Exception as e:
                print(f"Error cancelling order {order.id} for {symbol}: {e}")
        print(f"Canceled orders saved to {canceled_file}")

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
        return order_frame
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



class EMACalculator:
    def __init__(self, alpha_param):
        self.alpha_param = alpha_param
        self.alpha1 = 1 - alpha_param
        self.alpha_squared = alpha_param ** 2
        self.alpha2 = 1 - alpha_param
        self.symbol = symbol
        self.price_ema = price_ema
        self.volume_ema = volume_ema
        self.price_var = price_var
        self.price_vol = price_vol
        self.price_frame = pd.DataFrame(columns=["timestamp", "symbol", "price", "volume", "ema_price", "volatility"])
        self.max_frame_size = 1000

    def calc_ema(self, trade_price, trade_size, time_stamp):
        # Use self.alpha_param, self.alpha1, etc.
        # ...existing code...
        # Update the EMA price using the latest trade price
        # global price_emav
        # price_emav = alpha_param * price_emav + alpha1 * trade_size * trade_price
        # Update the EMA volume using the latest trade size
        # global volume_ema
        # volume_ema = alpha_param * volume_ema + alpha1 * trade_size
        # The EMA price is the price-volume divided by the EMA volume
        global symbol, alpha_param, alpha1, alpha_squared, alpha2
        global price_ema, date_pretty, price_var
        global data_file, error_file, plot_file
        global price_frame, max_frame_size
        # price_ema = price_emav / volume_ema
        price_ema = alpha_param * price_ema + alpha1 * trade_price
        # Update the price variance using the latest prices
        # global price_varv
        # price_varv = alpha_squared * price_varv + alpha2 * trade_size * (trade_price - price_ema) ** 2
        # price_var = price_varv / volume_ema
        global price_var
        price_var = alpha_squared * price_var + alpha2 * (trade_price - price_ema) ** 2
        # Print the updated EMA price and volume
        # time_stamp = datetime.now(tzone).strftime("%Y-%m-%d %H:%M:%S")
        price_vol = np.sqrt(price_var) # The price volatility is the square root of the price variance
        print(f"{time_stamp} {symbol} Price: {round(trade_price, ndigits=2)}, Size: {trade_size}, EMA price: {round(price_ema, ndigits=2)}, Volatility: {round(price_vol, ndigits=4)}")

        # Append the price data to the CSV file
        price_dict = {
            "timestamp": time_stamp,
            "symbol": symbol,
            "price": trade_price,
            "volume": trade_size,
            "ema_price": price_ema,
            "volatility": price_vol,
        }
        single_frame = pd.DataFrame([price_dict])
        # Append single_frame to data_file
        single_frame.to_csv(data_file, mode="a", header=not os.path.exists(data_file), index=False)
        # Append single_frame to price_frame
        global price_frame
        price_frame = pd.concat([price_frame, single_frame], ignore_index=True)
        # Keep only last max_frame_size records to limit memory usage
        if len(price_frame) > max_frame_size:
            price_frame = price_frame.tail(max_frame_size).reset_index(drop=True)
        return price_frame

# End of function calc_ema


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




