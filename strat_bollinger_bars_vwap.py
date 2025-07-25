# Strategy trades a single stock using the streaming real-time stock price bars from the Alpaca API.
# The strategy is based on the z-score, equal to the difference between the stock's closing price minus its Moving Average Price (EMA), divided by the volatility.
# If the z-score is below -1, then it buys the stock.
# If the z-score is above 1, then it sells the stock.
# It uses the VWAP as the EMA price for simplicity.

# You can submit a trade order by running this script in the terminal:
# python3 strat_bollinger_bars_vwap.py symbol, type, side, num_shares, delta
#
# The delta is the adjustment to the limit price, compared to the ask or bid price.
# For example, if the ask price is $100, and the delta is $0.5,
# the limit price will be set to $99.5 for a buy order, or $100.5 for a sell order.
# 
# Example:
# python3 strat_bollinger_bars_vwap.py SPY limit buy 1 0.5

# This is only an illustration how to use the streaming real-time data, using the Alpaca websocket. 
# This is only for illustration purposes, and not a real trading strategy.



import os
import sys
import signal
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.data.live.stock import StockDataStream
from dotenv import load_dotenv
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import get_position, cancel_orders, submit_trade


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv(".env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")
# Trade keys
TRADE_KEY = os.getenv("TRADE_KEY")
TRADE_SECRET = os.getenv("TRADE_SECRET")

# Create the SDK data client for live stock prices
stream_client = StockDataStream(DATA_KEY, DATA_SECRET)
# Create the SDK trading client
trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)


# --------- Get the trading parameters from the command line arguments --------

# Get the symbol, type, side, shares_per_trade, and delta from the command line arguments
if len(sys.argv) > 5:
    symbol = sys.argv[1].strip().upper()
    type = sys.argv[2].strip().lower()
    side_input = sys.argv[3].strip().lower()
    shares_per_trade = float(sys.argv[4])
    delta = float(sys.argv[5])
else:
    # If not provided, prompt the user for input
    symbol = input("Enter symbol: ").strip().upper()
    type = input("Enter order type (market/limit): ").strip().lower()
    side_input = input("Enter side (buy/sell): ").strip().lower()
    shares_input = input("Enter number of shares to trade (default 1): ").strip()
    shares_per_trade = float(shares_input) if shares_input else 1
    delta_input = input("Enter price adjustment (default 0.5): ").strip()
    delta = float(delta_input) if delta_input else 0.5


# --------- Specify the strategy parameters --------

# symbol = "SPY"
# Specify the strategy name
strategy_name = "StratBoll001"
# Specify the trading parameters
# shares_per_trade = 1  # Number of shares to trade per each order
shares_owned = 0  # Number of shares currently owned
# type = "market"
# type = "limit"
# side = OrderSide.BUY  # Set to BUY or SELL as needed
# Adjustment to the limit price to make it below the ask or above the bid
# delta = 0.1  # The delta price adjustment for the limit order
vol_floor = 0.05  # The volatility floor
price_vol = vol_floor  # The price volatility, used to calculate the z-score

# Initialize the strategy state variables
position = 0  # The current position - the number of shares owned
shares_available = 0  # The number of available shares to trade, according to the broker
pnl_real = 0  # The realized PnL of the strategy
pnl_unreal = 0  # The unrealized PnL of the strategy


# --------- Create the file names --------

# Create file names with today's NY date
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
date_short = time_now.strftime("%Y%m%d")
dir_name = os.getenv("data_dir_name")
# Create file name for the state variables
state_file = f"{dir_name}" + "state_" + f"{strategy_name}_{symbol}_{date_short}.csv"
# Create file name for the submitted trade orders
submits_file = f"{dir_name}" + "submits_" + f"{strategy_name}_{symbol}_{date_short}.csv"
# Create file name for the canceled trade orders
canceled_file = f"{dir_name}" + "canceled_" + f"{strategy_name}_{symbol}_{date_short}.csv"
# Create file name for the websocket errors
error_file = f"{dir_name}" + "error_" + f"{strategy_name}_{symbol}_{date_short}.csv"



# --------- Create the callback function --------

# The callback trading function is called after each price bar update
async def trade_bars(bar):
    # print(f"Bar price: {bar}")
    # print(f"Symbol: {bar.symbol}, Open: {bar.open}, High: {bar.high}, Low: {bar.low}, Close: {bar.close}, Volume: {bar.volume}, Trade_count: {bar.trade_count}, VWAP: {bar.vwap}")
    close_price = bar.close
    price_ema = bar.vwap  # The EMA price is the VWAP price
    timestamp = bar.timestamp.astimezone(ZoneInfo("America/New_York"))
    date_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    print(f"Time: {date_time}, Symbol: {bar.symbol}, Close: {close_price}, VWAP: {price_ema}")

    # Get the current position and the number of available shares to trade for the symbol
    position = get_position(trading_client, symbol)
    if position is None:
        # There is no open position - set the available shares to the number of shares traded per each order
        shares_available = shares_per_trade
        shares_owned = 0
    else:
        # Get the number of available shares to trade from the broker
        shares_available = float(position.qty_available)
        shares_owned = float(position.qty)


    # Calculate the z-score of the price relative to the EMA price
    zscore = (close_price - price_ema) / price_vol  # Z-score of the price relative to the EMA price
    # Initialize the side variable
    side = None

    # If the absolute value of z-score is greater than 1, then submit a trade order
    if abs(zscore) > (1): # If the price is significantly different from the EMA price
        # If the available shares is greater than or equal to the shares traded per order
        if (shares_available >= shares_per_trade):
            # Define the order parameters
            if zscore > 1:
                # Submit a sell order
                side = OrderSide.SELL
                # Limit price is equal to the last price plus a small adjustment
                limit_price = round(close_price + delta, 2)
            elif zscore < (-1):
                # If the price is significantly below the EMA price
                # Submit a buy order
                side = OrderSide.BUY
                # Limit price is equal to the last price minus a small adjustment
                limit_price = round(close_price - delta, 2)
            # Submit the trade order
            order_data = submit_trade(trading_client, symbol, shares_per_trade, side, type, limit_price, submits_file)
            if order_data is None:
                # If the order submission failed, cancel all the open orders
                print(f"Trade order submission failed for {symbol}")
                print(f"Cancelling all open orders for {symbol}")
                # Cancel all open orders for the symbol
                cancel_orders(trading_client, symbol)
                # Submit the trade order again
                order_data = submit_trade(trading_client, symbol, shares_per_trade, side, type, limit_price, submits_file)
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



# --------- Run the websocket stream --------

# Subscribe to OHLCV bar updates and pass them to the callback function
stream_client.subscribe_bars(trade_bars, symbol)

# Run the websocket stream_client stream with error handling and auto-restart
try:
    stream_client.run()
except Exception as e:
    time_stamp = datetime.now(tzone).strftime("%Y-%m-%d %H:%M:%S")
    error_text = f"{time_stamp} WebSocket error: {e}. Restarting connection in 5 seconds..."
    print(error_text)
    with open(error_file, "a") as f: f.write(error_text)
    time.sleep(5)

print("Stream stopped by user.")



# --------- Handle Ctrl-C interrupt --------

# The code below stops the stream when the user presses Ctrl-C

def signal_handler(sig, frame):
    """Handle Ctrl-C (SIGINT) gracefully"""
    print("\n\nCtrl-C pressed! Exiting gracefully...")
    # Stop the stream client before exiting
    try:
        stream_client.stop()
    except:
        pass
    sys.exit(0)

# Set up signal handler for Ctrl-C
print("Press Ctrl-C to stop the stream... \n")
signal.signal(signal.SIGINT, signal_handler)


