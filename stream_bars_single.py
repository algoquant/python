### Streams real-time stock bar prices for a single symbol via the Alpaca websocket API, and saves them to a CSV file.
# https://wire.insiderfinance.io/alpaca-algorithmic-trading-api-in-python-part-1-getting-started-with-paper-trading-efbff8992836

# You can run this script in the terminal as follows:
# python3 stream_bars_single.py SPY


import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from alpaca.data import DataFeed, StockHistoricalDataClient
from alpaca.data.live.stock import StockDataStream
from dotenv import load_dotenv


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv(".env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

# Create the SDK data client for live stock prices
stream_client = StockDataStream(DATA_KEY, DATA_SECRET, feed=DataFeed.SIP)


# --------- Get the trading symbol from the command line arguments --------

# Define the trading symbol
# symbol = "SPY"
if len(sys.argv) > 1:
    symbol = sys.argv[1].strip().upper()
else:
    symbol = input("Enter symbol: ").strip().upper()

print(f"This script Streams real-time stock bar prices for {symbol} via the Alpaca websocket API, and saves them to a CSV file.\n")


# --------- Create the file names --------

# Create a file name with today's NY date
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
date_short = time_now.strftime("%Y%m%d")
dir_name = os.getenv("data_dir_name")
file_name = f"{dir_name}price_bars_{symbol}_{date_short}.csv"



# --------- Create the callback function --------

# Define the price bar handler callback function
async def handle_bar(bar):
    # print(f"Bar: {bar}")
    time_stamp = bar.timestamp.astimezone(tzone).strftime("%Y-%m-%d %H:%M:%S")
    print(f"Time: {time_stamp}, Symbol: {bar.symbol}, Open: {bar.open}, High: {bar.high}, Low: {bar.low}, Close: {bar.close}, Volume: {bar.volume}, Trade_count: {bar.trade_count}, VWAP: {bar.vwap}")
    # Prepare a dict with the price bar
    bar_dict = {
        "timestamp": time_stamp,
        "symbol": bar.symbol,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "trade_count": bar.trade_count,
        "vwap": bar.vwap
    }
    # Append the price bars to the CSV file for the symbol
    price_bar = pd.DataFrame([bar_dict])
    price_bar.to_csv(file_name, mode="a", header=not os.path.exists(file_name), index=False)
# End handle_bar callback
    


# --------- Run the websocket stream --------

# Subscribe to the websocket price bar updates
stream_client.subscribe_bars(handle_bar, symbol)


# Define the price quote handler callback function
# async def handle_quote(quote):
#     print(f"Quote: {quote}")
# Subscribe to the quote updates
# stream_client.subscribe_quotes(handle_quote, symbol)

# Define the price trade handler callback function
# async def handle_trade(trade):
#     print(f"Trade: {trade}")
# Subscribe to the trade updates
# stream_client.subscribe_trades(handle_trade, symbol)


# Run the stream with error handling and auto-restart
try:
    stream_client.run()
except Exception as e:
    time_stamp = datetime.now(tzone).strftime("%Y-%m-%d %H:%M:%S")
    error_text = f"{time_stamp} WebSocket error: {e}. Restarting connection in 5 seconds..."
    print(error_text)
    with open(file_name, "a") as f: f.write(error_text)
    time.sleep(5)


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


