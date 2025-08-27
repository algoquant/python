### Stream real-time stock price bars for multiple symbols, via the Alpaca websocket API.
# Save the price bars to CSV files, one for each symbol.
# 
# https://wire.insiderfinance.io/alpaca-algorithmic-trading-api-in-python-part-1-getting-started-with-paper-trading-efbff8992836

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
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

# Create the SDK data client for live stock prices
data_client = StockDataStream(DATA_KEY, DATA_SECRET, feed=DataFeed.SIP)



# --------- Get the trading symbols from the command line arguments --------

# Get multiple symbols from command line arguments
if len(sys.argv) > 1:
    # Take all arguments after the script name as symbols
    symbols = [arg.strip().upper() for arg in sys.argv[1:]]
else:
    # If no arguments, prompt for symbols
    symbol_input = input("Enter symbols (comma-separated, e.g., SPY,AAPL,GOOGL): ").strip().upper()
    symbols = [s.strip() for s in symbol_input.split(',') if s.strip()]

print(f"This script streams real-time stock bar prices for {', '.join(symbols)} via the Alpaca websocket API, and saves them to CSV files.\n")



# --------- Create the file names --------

# Create today's NY date
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
date_short = time_now.strftime("%Y%m%d")

# Create a dictionary with file names for each symbol
dir_name = os.getenv("DATA_DIR_NAME")
file_dict = {
    symbol: f"{dir_name}price_bars_{symbol}_{date_short}.csv"
    for symbol in symbols
}


# --------- Define the callback function --------

# Define the bar handler callback function
async def handle_bar(bar):
    # print(f"Bar: {bar}")
    time_stamp = bar.timestamp.astimezone(tzone).strftime("%Y-%m-%d %H:%M:%S")
    print(f"Time: {time_stamp}, Symbol: {bar.symbol}, Open: {bar.open}, High: {bar.high}, Low: {bar.low}, Close: {bar.close}, Volume: {bar.volume}, Trade_count: {bar.trade_count}, VWAP: {bar.vwap}")
    # print(f"Symbol: {bar.symbol}, Open: {bar.open}, High: {bar.high}, Low: {bar.low}, Close: {bar.close}, Volume: {bar.volume}, Trade_count: {bar.trade_count}, VWAP: {bar.vwap}")
    # Prepare a dict for the bar
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
    file_name = file_dict[bar.symbol]
    price_bar.to_csv(file_name, mode="a", header=not os.path.exists(file_name), index=False)
# End bar handler callback function



# --------- Run the websocket stream --------

# Subscribe to the websocket price bar updates for all the symbols
for symbol in symbols:
    data_client.subscribe_bars(handle_bar, symbol)


# Run the stream with error handling and auto-restart
while True:
    try:
        data_client.run()
    except Exception as e:
        time_stamp = datetime.now(tzone).strftime("%Y-%m-%d %H:%M:%S")
        error_text = f"{time_stamp} WebSocket error: {e}. Restarting connection in 5 seconds..."
        print(error_text)
        for symbol, file_name in file_dict.items():
            with open(file_name, "a") as f: f.write(error_text)
        time.sleep(5)



# --------- Handle Ctrl-C interrupt --------

# The code below stops the stream when the user presses Ctrl-C

def signal_handler(sig, frame):
    """Handle Ctrl-C (SIGINT) gracefully"""
    print("\n\nCtrl-C pressed! Exiting gracefully...")
    # Stop the stream client before exiting
    try:
        data_client.stop()
    except:
        pass
    sys.exit(0)

# Set up signal handler for Ctrl-C
print("Press Ctrl-C to stop the stream... \n")
signal.signal(signal.SIGINT, signal_handler)


