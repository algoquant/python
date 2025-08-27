### Strategy to trade a single stock using the streaming real-time stock prices from the Alpaca API.
# The strategy uses the z-score, equal to the difference between the stock's trade price minus its Moving Average Price (EMA), divided by the volatility.
# If the z-score is below -1, then it buys the stock.
# If the z-score is above 1, then it sells the stock.

# This is only an illustration how to use the streaming real-time data, using the Alpaca websocket. 
# This is only for illustration purposes, and not a real trading strategy.

import time
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.data.live.stock import StockDataStream
from dotenv import load_dotenv
import os
import sys
import signal
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import get_position, cancel_orders, submit_order


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")
# Trade keys
ALPACA_TRADE_KEY = os.getenv("ALPACA_TRADE_KEY")
ALPACA_TRADE_SECRET = os.getenv("ALPACA_TRADE_SECRET")

# Create the SDK data client for live stock prices
data_client = StockDataStream(DATA_KEY, DATA_SECRET)
# Create the SDK trading client
trading_client = TradingClient(ALPACA_TRADE_KEY, ALPACA_TRADE_SECRET)


# Create the strategy name
strategy_name = "StratBoll001"


# Define the trading parameters
symbol = "SPY"
shares_per_trade = 1  # Number of shares to trade per each order
shares_owned = 0  # Number of shares currently owned
# type = "market"
type = "limit"
# side = OrderSide.BUY  # Set to BUY or SELL as needed
# Adjustment to the limit price to make it below the ask or above the bid
deltap = 0.1  # The delta price adjustment for the limit order
vol_floor = 0.05  # The volatility floor
price_vol = vol_floor  # The price volatility, used to calculate the z-score


# Create file names with today's NY date
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
date_short = time_now.strftime("%Y%m%d")
dir_name = os.getenv("DATA_DIR_NAME")
# Create file name for the state variables
state_file = f"{dir_name}" + "state_" + f"{strategy_name}_{symbol}_{date_short}.csv"
# Create file name for the submitted trade orders
orders_file = f"{dir_name}" + "orders_" + f"{strategy_name}_{symbol}_{date_short}.csv"
# Create file name for the canceled trade orders
canceled_file = f"{dir_name}" + "canceled_" + f"{strategy_name}_{symbol}_{date_short}.csv"
# Create file name for the websocket errors
error_file = f"{dir_name}" + "error_" + f"{strategy_name}_{symbol}_{date_short}.csv"
print(f"The state file is: {state_file}\n")
print(f"The order submits file is: {submits_file}\n")
print(f"The order fills file is: {fills_file}\n")
print(f"The order errors file is: {error_file}\n")

# Initialize the strategy state variables
position = 0  # The current position - the number of shares owned
shares_available = 0  # The number of available shares to trade, according to the broker
pnl_real = 0  # The realized PnL of the strategy
pnl_unreal = 0  # The unrealized PnL of the strategy



# The callback trading function is called after each price bar is received
async def trade_bars(bar):
    # print(f"Bar price: {bar}")
    # print(f"Symbol: {bar.symbol}, Open: {bar.open}, High: {bar.high}, Low: {bar.low}, Close: {bar.close}, Volume: {bar.volume}, Trade_count: {bar.trade_count}, VWAP: {bar.vwap}")
    close_price = bar.close
    price_ema = bar.vwap  # The EMA price is the VWAP price
    timestamp = bar.timestamp.astimezone(tzone)
    date_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    print(f"Time: {date_time}, Symbol: {bar.symbol}, Close: {close_price}, VWAP: {price_ema}")

    # Get the current position and the number of available shares to trade for the symbol
    position = get_position(trading_client, symbol)
    if position is None:
        # There is no open position - set the available shares to the number of shares traded per each order
        shares_available = shares_per_trade
        # Check if there are any open limit orders for the symbol
    else:
        # Get the number of available shares to trade from the broker
        shares_available = position.qty_available
        shares_owned = position.qty


    # Calculate the z-score of the price relative to the EMA price
    zscore = (close_price - price_ema) / price_vol  # Z-score of the price relative to the EMA price

    # If the absolute value of the z-score is greater than 1, then submit a trade order
    if abs(zscore) > (1): # If the price is significantly different from the EMA price
        # If the available shares is greater than or equal to the shares traded per order
        if (shares_available >= shares_per_trade):
            # Define the order parameters
            if zscore > 1:
                # Submit a sell order
                side = OrderSide.SELL
                # Limit price is equal to the last price plus a small adjustment
                limit_price = round(close_price + deltap, 2)
            elif zscore < (-1):
                # If the price is significantly below the EMA price
                # Submit a buy order
                side = OrderSide.BUY
                # Limit price is equal to the last price minus a small adjustment
                limit_price = round(close_price - deltap, 2)
            # Submit the trade order
            order_data = submit_order(trading_client, symbol, shares_per_trade, side, type, limit_price, orders_file)
            if order_data is None:
                # If the order submission failed, cancel all the open orders
                print(f"Trade order submission failed for {symbol}")
                print(f"Cancelling all open orders for {symbol}")
                # Cancel all open orders for the symbol
                cancel_orders(trading_client, symbol, canceled_file)
                # Submit the trade order again
                order_data = submit_order(trading_client, symbol, shares_per_trade, side, type, limit_price, orders_file)
        else:
            print(f"Available shares {shares_available} are less than the number of shares traded per order {shares_per_trade}. No trade executed.")
    else:
        print(f"Last price {close_price} is too close to the EMA price {price_ema} - no trade executed for {symbol}")
        side = None


    # Save the strategy state to a CSV file
    state_data = {
        "date_time": date_time,
        "symbol": bar.symbol,
        "price": bar.close,
        "volatility": (bar.high - bar.low),
        "zscore": zscore,
        "order": side,
        "shares_owned": shares_owned,
        "pnlReal": 0,
        "pnlUnreal": 0,
    }
    state_data = pd.DataFrame([state_data])
    state_data.to_csv(state_file, mode="a", header=not os.path.exists(state_file), index=False)
    print("Done\n")

# End of callback function trade_bars



# Subscribe to quote or trade updates
# data_client.subscribe_quotes(handle_quote, symbol)
# data_client.subscribe_trades(handle_trade, symbol)

# Subscribe to OHLCV bar updates and pass them to the callback function
data_client.subscribe_bars(trade_bars, symbol)

# Run the websocket data_client stream with error handling and auto-restart
try:
    data_client.run()
except Exception as e:
    time_stamp = datetime.now(tzone).strftime("%Y-%m-%d %H:%M:%S")
    error_text = f"{time_stamp} WebSocket error: {e}. Restarting connection in 5 seconds..."
    print(error_text)
    with open(error_file, "a") as f: f.write(error_text)
    time.sleep(5)



# --------- Handle Ctrl-C interrupt --------

# The code below stops the stream when the user presses Ctrl-C

def signal_handler(sig, frame):
    # Handle Ctrl-C (SIGINT) gracefully
    print("\n\nCtrl-C pressed! Exiting...")
    # Stop the stream client before exiting
    try:
        data_client.stop()
        print("Stream stopped by user.")
    except:
        pass
    sys.exit(0)

# Set up signal handler for Ctrl-C
print("Press Ctrl-C to stop the stream... \n")
signal.signal(signal.SIGINT, signal_handler)


