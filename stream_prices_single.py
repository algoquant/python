### Stream real-time stock prices (quotes, trades) for a single symbol, via the Alpaca websocket API.
# Save the prices to a CSV file.
# https://wire.insiderfinance.io/alpaca-algorithmic-trading-api-in-python-part-1-getting-started-with-paper-trading-efbff8992836

import time
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from alpaca.data import DataFeed, StockHistoricalDataClient
from alpaca.data.live.stock import StockDataStream
from dotenv import load_dotenv
import os
import sys


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv(".env")
# Get API keys from environment
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

# Create the SDK data client for live stock prices
stream_client = StockDataStream(DATA_KEY, DATA_SECRET, feed=DataFeed.SIP)

# Get the trading symbol
if len(sys.argv) > 1:
    symbol = sys.argv[1].strip().upper()
else:
    symbol = input("Enter symbol: ").strip().upper()
# symbol = "SPY"

# Create a file name with today's NY date
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
date_short = time_now.strftime("%Y%m%d")
dir_name = os.getenv("data_dir_name")
file_name = f"{dir_name}price_trades_{symbol}_{date_short}.csv"


# The callback EMA function is called after each trade price update
async def handle_trade(latest_price):

    # Get the latest trade price and size
    # latest_price = latest_price[symbol]
    trade_price = latest_price.price
    trade_size = latest_price.size
    time_stamp = latest_price.timestamp.astimezone(tzone).strftime("%Y-%m-%d %H:%M:%S")
    print(f"Time: {time_stamp}, Symbol: {symbol}, Price: {trade_price}, Size: {trade_size}")

    # Prepare a dict with the price bar
    price_dict = {
        "timestamp": time_stamp,
        "symbol": symbol,
        "price": trade_price,
        "volume": trade_size,
    }
    # Append the price bars to the CSV file for the symbol
    price_frame = pd.DataFrame([price_dict])
    price_frame.to_csv(file_name, mode="a", header=not os.path.exists(file_name), index=False)

# End of callback function handle_trade


# Subscribe to the websocket trade price updates
stream_client.subscribe_trades(handle_trade, symbol)


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

