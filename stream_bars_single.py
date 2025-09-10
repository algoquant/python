"""
Stream real-time stock bar prices for a single symbol via the Alpaca websocket API, and save them to a CSV file.
https://wire.insiderfinance.io/alpaca-algorithmic-trading-api-in-python-part-1-getting-started-with-paper-trading-efbff8992836

You can run this script in the terminal for SPY as follows:
    python3 stream_bars_single.py SPY

"""

import os
import sys
import asyncio
import signal
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from alpaca.data import DataFeed, StockHistoricalDataClient
from alpaca.data.live.stock import StockDataStream
from dotenv import load_dotenv

# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

# Create the SDK data client for live stock prices
data_client = StockDataStream(DATA_KEY, DATA_SECRET, feed=DataFeed.SIP)

# --------- Get the trading symbol from the command line arguments --------

# Define the trading symbol
# symbol = "SPY"
if len(sys.argv) > 1:
    symbol = sys.argv[1].strip().upper()
else:
    symbol = input("Enter symbol: ").strip().upper()


# --------- Create the file names --------

# Create a file name with today's NY date
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
date_short = time_now.strftime("%Y%m%d")
dir_name = os.getenv("DATA_DIR_NAME")
file_name = f"{dir_name}price_bars_{symbol}_{date_short}.csv"

print(f"This script streams real-time stock bar prices for {symbol} via the Alpaca websocket API, and saves them to the CSV file {file_name}\n")


# --------- Define the callback function for handling price bars --------

async def handle_bar(bar):

    # Convert timestamp to local time
    time_stamp = bar.timestamp.astimezone(tzone).strftime("%Y-%m-%d %H:%M:%S")

    # Extract other fields
    symbol = bar.symbol
    open = bar.open
    high = bar.high
    low = bar.low
    close = bar.close
    volume = bar.volume
    trade_count = bar.trade_count
    vwap = bar.vwap

    print(f"Time: {time_stamp}, Symbol: {symbol}, Open: {open}, High: {high}, Low: {low}, Close: {close}, Volume: {volume}, Trade_count: {trade_count}, VWAP: {vwap}")

    # Create a dictionary with the price bar data
    bar_dict = {
        "timestamp": time_stamp,
        "symbol": symbol,
        "open": open,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "trade_count": trade_count,
        "vwap": vwap
    }
    # Append the price bars to the CSV file for the symbol
    price_bar = pd.DataFrame([bar_dict])
    price_bar.to_csv(file_name, mode="a", header=not os.path.exists(file_name), index=False)

# End handle_bar callback


# --------- Main with subscribe_bars and robust Ctrl-C handling --------

def main():

    # Subscribe to the price bars for the selected symbol
    data_client.subscribe_bars(handle_bar, symbol)

    # Handle SIGINT/SIGTERM to shut down gracefully
    def shutdown():
        print("\nCaught interrupt, exiting immediately...")
        os._exit(0)  # Force immediate exit without cleanup

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: shutdown())

    print("Press Ctrl-C to stop the stream... \n")
    # This blocks until stream.stop() is called from shutdown()
    try:
        data_client.run()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt caught, exiting...")
        os._exit(0)
    except Exception as e:
        print(f"Stream error: {e}")
        shutdown()

if __name__ == '__main__':
    main()


# --------- Run the websocket stream --------

# Define the price quote handler callback function
# async def handle_quote(quote):
#     print(f"Quote: {quote}")
# Subscribe to the quote updates
# data_client.subscribe_quotes(handle_quote, symbol)

# Define the price trade handler callback function
# async def handle_trade(trade):
#     print(f"Trade: {trade}")
# Subscribe to the trade updates
# data_client.subscribe_trades(handle_trade, symbol)


# Run the stream with error handling and auto-restart
# The code below stops the stream when the user presses Ctrl-C


