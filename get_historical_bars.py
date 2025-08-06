### Get historical OHLCV stock bar prices using the Alpaca API.

import pandas as pd
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from alpaca.data import StockHistoricalDataClient
# from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from dotenv import load_dotenv
import os


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)


### Get historical OHLCV bars of prices

# Get the current UTC time
time_utc = datetime.now(timezone.utc)
# time_utc = datetime(2025, 6, 20, 15, 0, 0, tzinfo=timezone.utc)
# Get the current New_York time
time_now = time_utc.astimezone(ZoneInfo("America/New_York"))
# Print current date and time
print("UTC date and time: ", time_utc.strftime("%Y-%m-%d %H:%M:%S"))
print("New York date and time: ", time_now.strftime("%Y-%m-%d %H:%M:%S %Z"))

# Run only between allowed hours (4 AM - 8 PM EST)
# if time_now.hour < 4 or time_now.hour >= 20:
#     print("Current time is outside of trading hours. Exiting script.")
#     exit()
                                    
# Calculate UTC start time (10 minutes ago)
start_time = time_utc - timedelta(minutes=10)
# start_time = (datetime.utcnow() - timedelta(minutes=20)).isoformat()
start_time = start_time.strftime("%Y-%m-%d %H:%M:%S")
# print("Start time: ", start_time)
end_time = time_utc.strftime("%Y-%m-%d %H:%M:%S")
# print("End time:", end_time)

# Define the trading symbol
symbol = "SPY"
symbols = ["SPY", "AAPL", "GOOGL"]  # Example list of symbols
# Define the request parameters for historical stock bars
request_params = StockBarsRequest(
    symbol_or_symbols = symbols,
    timeframe = TimeFrame.Minute,
    start = start_time,
    end = end_time,
    limit = 100,
    feed = "iex",  # Use "iex" for IEX data - if you don't have access to SIP data
) # end StockBarsRequest

price_bars = data_client.get_stock_bars(request_params)
# print(f"Fetched {len(price_bars['SPY'])} bars for SPY from {start_time} to {end_time}")
type(price_bars)
# print(price_bars)
# price_bars = pd.DataFrame([bar.model_dump() for bar in price_bars[symbol]])

# Save data frame to CSV
date_short = time_now.strftime("%Y%m%d")
# filename = "price_bars_" + date_short + ".csv"
# price_bars.to_csv(filename, index=False)

# Loop and save each symbol's bars to a separate CSV file
for symbol in symbols:
    # Check if bars are returned for the symbol
    if price_bars[symbol]:
        price_bars_df = pd.DataFrame([bar.model_dump() for bar in price_bars[symbol]])
        # Save data frame to CSV
        filename = f"price_bars_{symbol}_{date_short}.csv"
        price_bars_df.to_csv(filename, index=False)
        print(f"Saved historical OHLCV prices for {symbol} and saved to {filename}")
    else:
        print(f"No bars were returned for {symbol} in the requested time range.")

print("Finished getting historical OHLCV stock prices.")
